"""Checksummed German PII generators the Faker library does not provide.

Each generator takes a seeded `random.Random` so the whole corpus stays
reproducible. Every value carries a *real* check digit (the same standard
algorithm a production detector would validate), so the corpus is a fair test of
checksum-based detection. `make_invalid_*` helpers produce near-miss decoys that
look right but fail the checksum — these go into PII-free files to exercise the
false-positive rate.

Algorithms implemented:
- Steuer-ID (tax ID)         : ISO 7064 MOD 11,10
- Sozialversicherungsnummer  : weighted cross-sum mod 10 (Versicherungsnummer)
- Personalausweis (ID card)  : ICAO 7-3-1 MRZ check digit
- Reisepass (passport)       : ICAO 7-3-1 MRZ check digit
- Führerschein (driving lic.): base-36 weighted mod 11
"""
from __future__ import annotations

import random
import string

# ---------------------------------------------------------------------------
# check-digit primitives
# ---------------------------------------------------------------------------

_MRZ_VALUES = {**{str(d): d for d in range(10)},
               **{c: 10 + i for i, c in enumerate(string.ascii_uppercase)}}


def _iso7064_mod11_10(body: str) -> int:
    """ISO 7064 MOD 11,10 check digit over a string of digits (Steuer-ID)."""
    product = 10
    for ch in body:
        s = (int(ch) + product) % 10
        if s == 0:
            s = 10
        product = (s * 2) % 11
    return (11 - product) % 10


def _mrz_check(body: str) -> int:
    """ICAO 9303 check digit (weights 7,3,1) over digits and A-Z."""
    weights = (7, 3, 1)
    total = sum(_MRZ_VALUES[ch] * weights[i % 3] for i, ch in enumerate(body))
    return total % 10


def _b36(ch: str) -> int:
    return _MRZ_VALUES[ch]


# ---------------------------------------------------------------------------
# Steuerliche Identifikationsnummer (tax ID) — 11 digits
# ---------------------------------------------------------------------------

def steuer_id(rng: random.Random) -> str:
    """Valid German tax ID: first digit non-zero, exactly one repeated digit in
    the leading 10, ISO 7064 MOD 11,10 check digit appended."""
    while True:
        first = str(rng.randint(1, 9))
        # nine more digits, then enforce the "exactly one digit twice" rule
        rest = [str(rng.randint(0, 9)) for _ in range(9)]
        body = [first, *rest]
        counts = {d: body.count(d) for d in set(body)}
        twos = [d for d, c in counts.items() if c == 2]
        if len(twos) == 1 and all(c <= 2 for c in counts.values()) and body.count(twos[0]) == 2:
            # one digit appears twice, the rest at most once -> valid body shape
            if len([d for d, c in counts.items() if c == 1]) == 8:
                break
    s = "".join(body)
    return s + str(_iso7064_mod11_10(s))


def is_valid_steuer_id(value: str) -> bool:
    v = value.replace(" ", "")
    return (
        len(v) == 11
        and v.isdigit()
        and v[0] != "0"
        and _iso7064_mod11_10(v[:10]) == int(v[10])
    )


# ---------------------------------------------------------------------------
# Sozialversicherungsnummer (social security) — 12 chars: AA DDMMYY L SS C
# ---------------------------------------------------------------------------

_SVNR_WEIGHTS = (2, 1, 2, 5, 7, 1, 2, 1, 2, 1, 2, 1)


def _digit_sum(n: int) -> int:
    return sum(int(c) for c in str(n))


def sozialversicherungsnr(rng: random.Random) -> str:
    area = f"{rng.randint(2, 89):02d}"
    dd = f"{rng.randint(1, 28):02d}"
    mm = f"{rng.randint(1, 12):02d}"
    yy = f"{rng.randint(40, 99):02d}"
    letter = rng.choice(string.ascii_uppercase)
    serial = f"{rng.randint(0, 99):02d}"
    letter_val = f"{_MRZ_VALUES[letter] - 9:02d}"  # A->01 .. Z->26
    digits = area + dd + mm + yy + letter_val + serial  # 12 digits
    total = sum(_digit_sum(int(d) * w) for d, w in zip(digits, _SVNR_WEIGHTS))
    check = total % 10
    return f"{area}{dd}{mm}{yy}{letter}{serial}{check}"


def is_valid_sozialversicherungsnr(value: str) -> bool:
    v = value.replace(" ", "")
    if len(v) != 12 or not v[:8].isdigit() or not v[8].isalpha() or not v[9:].isdigit():
        return False
    letter_val = f"{_MRZ_VALUES[v[8].upper()] - 9:02d}"
    digits = v[:8] + letter_val + v[9:11]
    total = sum(_digit_sum(int(d) * w) for d, w in zip(digits, _SVNR_WEIGHTS))
    return total % 10 == int(v[11])


# ---------------------------------------------------------------------------
# Personalausweis (ID card) — 9-char serial + MRZ check digit
# ---------------------------------------------------------------------------

# real cards never use O, only the letters below appear in the serial
_AUSWEIS_ALPHABET = "CFGHJKLMNPRTVWXYZ0123456789"


def personalausweis(rng: random.Random) -> str:
    serial = "".join(rng.choice(_AUSWEIS_ALPHABET) for _ in range(9))
    return serial + str(_mrz_check(serial))


def is_valid_personalausweis(value: str) -> bool:
    v = value.replace(" ", "")
    if len(v) != 10:
        return False
    try:
        return _mrz_check(v[:9]) == int(v[9])
    except KeyError:
        return False


# ---------------------------------------------------------------------------
# Reisepass (passport) — letter + 8 alphanumerics + MRZ check digit
# ---------------------------------------------------------------------------

_PASSPORT_LEADS = "CFGHJK"


def passport(rng: random.Random) -> str:
    lead = rng.choice(_PASSPORT_LEADS)
    body = lead + "".join(rng.choice(string.digits) for _ in range(8))
    return body + str(_mrz_check(body))


def is_valid_passport(value: str) -> bool:
    v = value.replace(" ", "")
    if len(v) != 10:
        return False
    try:
        return _mrz_check(v[:9]) == int(v[9])
    except KeyError:
        return False


# ---------------------------------------------------------------------------
# Führerschein (driving licence) — base-36 weighted mod 11
# ---------------------------------------------------------------------------

def drivers_license(rng: random.Random) -> str:
    """11-char German licence number with a mod-11 check character (X == 10).

    Layout: 10 base-36 body characters + 1 check character, where the check is a
    position-weighted (10..1) mod-11 sum over the body.
    """
    body = "".join(rng.choice(string.digits + string.ascii_uppercase) for _ in range(10))
    weighted = sum(_b36(ch) * (10 - i) for i, ch in enumerate(body))
    rem = weighted % 11
    check = "X" if rem == 10 else str(rem)
    return body + check


def is_valid_drivers_license(value: str) -> bool:
    v = value.replace(" ", "")
    if len(v) != 11:
        return False
    try:
        weighted = sum(_b36(ch) * (10 - i) for i, ch in enumerate(v[:10]))
    except KeyError:
        return False
    rem = weighted % 11
    expected = "X" if rem == 10 else str(rem)
    return v[10] == expected


# ---------------------------------------------------------------------------
# near-miss decoys: right shape, wrong checksum
# ---------------------------------------------------------------------------

def make_invalid_digits(value: str, rng: random.Random) -> str:
    """Flip the final check digit so a shape match still fails the checksum."""
    last = value[-1]
    if last.isdigit():
        bad = str((int(last) + rng.randint(1, 8)) % 10)
    else:  # 'X' check char
        bad = str(rng.randint(0, 9))
    return value[:-1] + bad
