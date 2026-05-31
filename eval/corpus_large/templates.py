"""Realistic German corporate document templates with offset-tracking.

A template is a function `(b, fkr, rng) -> None` that writes a document by
appending to a `DocBuilder`. PII is injected through `b.pii(code, value)`, which
records the exact `[start, end)` character span as it writes — so ground-truth
spans are correct by construction, never searched for after the fact.

Decoy templates write realistic PII-free documents that include *hard near-misses*
(order numbers, version strings, invalid-checksum IDs) to exercise false positives.
"""
from __future__ import annotations

import random
import string
import sys
from dataclasses import dataclass, field
from pathlib import Path

from faker import Faker

# work whether imported as a package submodule or run as a loose script
sys.path.insert(0, str(Path(__file__).resolve().parent))
import pii_providers as P  # noqa: E402


@dataclass
class DocBuilder:
    """Accumulates text and records exact PII spans as it is written."""

    _parts: list[str] = field(default_factory=list)
    _pos: int = 0
    labels: list[tuple[str, int, int]] = field(default_factory=list)  # (code, start, end)

    def text(self, s: str) -> None:
        self._parts.append(s)
        self._pos += len(s)

    def line(self, s: str = "") -> None:
        self.text(s + "\n")

    def pii(self, code: str, value: str) -> None:
        """Write a PII value and label its exact span."""
        start = self._pos
        self.text(value)
        self.labels.append((code, start, start + len(value)))

    def build(self) -> str:
        return "".join(self._parts)


# ---------------------------------------------------------------------------
# small shared helpers
# ---------------------------------------------------------------------------

def _addr(fkr: Faker) -> str:
    return f"{fkr.street_address()}, {fkr.postcode()} {fkr.city()}"


def _emp_id(rng: random.Random) -> str:
    return f"PNR-{rng.randint(10_000_000, 99_999_999)}"


_CITIES = ["Paris", "Madrid", "Mailand", "Wien", "Zürich", "Amsterdam",
           "London", "Prag", "Lyon", "Barcelona", "Brüssel", "Kopenhagen"]
_MONTHS = ["01", "02", "03", "04", "05", "06", "09", "10", "11"]


def _travel_phrase(rng: random.Random) -> str:
    c1, c2 = rng.sample(_CITIES, 2)
    d1 = rng.randint(1, 12)
    d2 = d1 + rng.randint(2, 6)
    mm = rng.choice(_MONTHS)
    yy = rng.randint(22, 25)
    return f"{c1} ({d1}.–{d2}.{mm}.20{yy}) und anschließend {c2}"


# ===========================================================================
# PII-bearing templates
# ===========================================================================

def hr_record(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("BOSCH GmbH — Personalakte (vertraulich)")
    b.line("=" * 42)
    b.text("Mitarbeiter:in: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Personalnummer: "); b.pii("EMPLOYEE_ID", _emp_id(rng)); b.line()
    b.text("Anschrift: "); b.pii("HOME_ADDRESS", _addr(fkr)); b.line()
    b.text("Sozialversicherungsnummer: "); b.pii("DE_SOZIALVERSICHERUNGSNR", P.sozialversicherungsnr(rng)); b.line()
    b.text("Steuer-ID: "); b.pii("DE_STEUER_ID", P.steuer_id(rng)); b.line()
    if rng.random() < 0.5:
        b.text("Ausweisnummer: "); b.pii("DE_PERSONALAUSWEIS", P.personalausweis(rng)); b.line()
    b.line()
    b.line(f"Eintrittsdatum: {rng.randint(1,28):02d}.{rng.choice(_MONTHS)}.20{rng.randint(10,23)}")
    b.line(f"Abteilung: {rng.choice(['Einkauf','Fertigung','Forschung','Vertrieb','IT'])}")


def onboarding(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    name = fkr.name()
    b.line("Onboarding-Checkliste")
    b.text("Neue Kollegin/Kollege: "); b.pii("PERSON_NAME", name); b.line()
    b.text("E-Mail-Konto: "); b.pii("EMAIL", fkr.email()); b.line()
    b.text("Benutzername (Login): "); b.pii("USERNAME", fkr.user_name()); b.line()
    b.text("Personalnummer: "); b.pii("EMPLOYEE_ID", _emp_id(rng)); b.line()
    b.text("Diensttelefon: "); b.pii("PHONE_NUMBER", fkr.phone_number()); b.line()
    b.line()
    b.line("[ ] Laptop ausgegeben   [ ] Badge aktiviert   [ ] VPN eingerichtet")


def leave_request(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("Urlaubsantrag")
    b.line("-" * 20)
    b.text("Antragsteller:in: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Personalnummer: "); b.pii("EMPLOYEE_ID", _emp_id(rng)); b.line()
    b.line(f"Zeitraum: {rng.randint(1,20):02d}.{rng.choice(_MONTHS)} bis {rng.randint(21,28):02d}.{rng.choice(_MONTHS)}.20{rng.randint(24,25)}")
    b.line(f"Resturlaub: {rng.randint(2,28)} Tage")
    b.text("Genehmigt durch: "); b.pii("PERSON_NAME", fkr.name()); b.line()


def payslip(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("Entgeltabrechnung")
    b.text("Name: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Personalnummer: "); b.pii("EMPLOYEE_ID", _emp_id(rng)); b.line()
    b.text("SV-Nummer: "); b.pii("DE_SOZIALVERSICHERUNGSNR", P.sozialversicherungsnr(rng)); b.line()
    b.text("Steuer-ID: "); b.pii("DE_STEUER_ID", P.steuer_id(rng)); b.line()
    b.text("Auszahlung auf IBAN: "); b.pii("IBAN", fkr.iban()); b.line()
    b.line(f"Bruttobezug: {rng.randint(3,9)}.{rng.randint(100,999)},00 EUR")


def invoice(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line(f"RECHNUNG Nr. {rng.randint(2024,2025)}-{rng.randint(1000,9999)}")
    b.line("=" * 36)
    b.text("Rechnungsempfänger: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Lieferanschrift: "); b.pii("BILLING_SHIPPING_ADDRESS", _addr(fkr)); b.line()
    b.line(f"Bestell-Nr.: ORD-{rng.randint(100000,999999)}")  # near-miss decoy id
    b.text("Zahlbar auf IBAN: "); b.pii("IBAN", fkr.iban()); b.line()
    if rng.random() < 0.4:
        b.text("Kartenzahlung: "); b.pii("CREDIT_CARD_NUMBER", fkr.credit_card_number()); b.line()
    b.line(f"Gesamtbetrag: {rng.randint(50,9000)},{rng.randint(0,99):02d} EUR")


def expense_report(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("Reisekostenabrechnung")
    b.text("Mitarbeiter:in: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Personalnummer: "); b.pii("EMPLOYEE_ID", _emp_id(rng)); b.line()
    b.text("Reiseverlauf: "); b.pii("TRAVEL_HISTORY", _travel_phrase(rng)); b.line()
    b.text("Erstattung auf IBAN: "); b.pii("IBAN", fkr.iban()); b.line()
    if rng.random() < 0.5:
        b.text("Firmenkreditkarte: "); b.pii("CREDIT_CARD_NUMBER", fkr.credit_card_number()); b.line()


def purchase_order(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line(f"BESTELLUNG PO-{rng.randint(100000,999999)}")
    b.text("Besteller: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Kontakt: "); b.pii("EMAIL", fkr.email()); b.line()
    b.text("Lieferadresse: "); b.pii("BILLING_SHIPPING_ADDRESS", _addr(fkr)); b.line()
    b.line(f"Artikel: {rng.randint(1,40)}x Material SKU-{rng.randint(10000,99999)}")


def customer_email(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    name = fkr.name()
    b.text("Von: "); b.pii("EMAIL", fkr.email()); b.line()
    b.line(f"Betreff: Anfrage Auftrag {rng.randint(100000,999999)}")
    b.line()
    b.text("Sehr geehrte Damen und Herren,\n\nmein Name ist "); b.pii("PERSON_NAME", name)
    b.line(", ich habe eine Rückfrage zu meiner Bestellung.")
    b.text("Sie erreichen mich telefonisch unter "); b.pii("PHONE_NUMBER", fkr.phone_number()); b.line(".")
    b.line("\nMit freundlichen Grüßen")
    b.pii("PERSON_NAME", name); b.line()


def vendor_email(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("Lieferanten-Korrespondenz")
    b.text("Ansprechpartner: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("E-Mail: "); b.pii("EMAIL", fkr.email()); b.line()
    b.text("Telefon: "); b.pii("PHONE_NUMBER", fkr.phone_number()); b.line()
    b.text("Fax: "); b.pii("FAX_NUMBER", fkr.phone_number()); b.line()


def support_ticket(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line(f"[Ticket #{rng.randint(100000,999999)}] Status: offen")
    b.text("Gemeldet von: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Rückmeldung an: "); b.pii("EMAIL", fkr.email()); b.line()
    b.text("Telefon: "); b.pii("PHONE_NUMBER", fkr.phone_number()); b.line()
    if rng.random() < 0.5:
        b.text("Client-IP aus Log: "); b.pii("IP_ADDRESS", fkr.ipv4()); b.line()
    b.line("Beschreibung: Login schlägt nach Update fehl.")


def employment_contract(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("ARBEITSVERTRAG")
    b.line("zwischen der Robert Bosch GmbH und")
    b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("wohnhaft: "); b.pii("HOME_ADDRESS", _addr(fkr)); b.line()
    b.text("Reisepass-Nr.: "); b.pii("PASSPORT_NUMBER", P.passport(rng)); b.line()
    b.text("Steuer-ID: "); b.pii("DE_STEUER_ID", P.steuer_id(rng)); b.line()
    b.line(f"\n§1 Beginn: {rng.randint(1,28):02d}.{rng.choice(_MONTHS)}.20{rng.randint(24,25)}")


def consent_form(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("Einwilligungserklärung Datenverarbeitung (Art. 6 DSGVO)")
    b.text("Name: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Anschrift: "); b.pii("HOME_ADDRESS", _addr(fkr)); b.line()
    b.text("E-Mail: "); b.pii("EMAIL", fkr.email()); b.line()
    b.text("Ausweisnummer: "); b.pii("DE_PERSONALAUSWEIS", P.personalausweis(rng)); b.line()
    b.text("Führerschein-Nr.: "); b.pii("DRIVERS_LICENSE_NUMBER", P.drivers_license(rng)); b.line()


def trip_notes(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("Reisenotizen")
    b.text("Reisende:r: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Reisepass: "); b.pii("PASSPORT_NUMBER", P.passport(rng)); b.line()
    b.text("Route: "); b.pii("TRAVEL_HISTORY", _travel_phrase(rng)); b.line()


def id_verification(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("Identitätsprüfung (KYC)")
    b.text("Person: "); b.pii("PERSON_NAME", fkr.name()); b.line()
    b.text("Personalausweis: "); b.pii("DE_PERSONALAUSWEIS", P.personalausweis(rng)); b.line()
    b.text("Reisepass: "); b.pii("PASSPORT_NUMBER", P.passport(rng)); b.line()
    b.text("Führerschein: "); b.pii("DRIVERS_LICENSE_NUMBER", P.drivers_license(rng)); b.line()


def access_log_pii(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("# auth service access log")
    for _ in range(rng.randint(3, 6)):
        b.text(f"{rng.randint(1,28):02d}/{rng.choice(_MONTHS)}/2025:{rng.randint(0,23):02d}:{rng.randint(0,59):02d} user=")
        b.pii("USERNAME", fkr.user_name())
        b.text(" from ")
        b.pii("IP_ADDRESS", fkr.ipv4())
        b.line(" status=200")


# ===========================================================================
# decoy templates (no PII; contain hard near-misses)
# ===========================================================================

def release_notes(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line(f"Release Notes — v{rng.randint(1,9)}.{rng.randint(0,20)}.{rng.randint(0,9)}")
    b.line("=" * 30)
    for _ in range(rng.randint(3, 6)):
        b.line(f"- [JIRA-{rng.randint(1000,9999)}] {fkr.catch_phrase()}")
    b.line(f"Build-Hash: {''.join(rng.choice(string.hexdigits.lower()) for _ in range(12))}")


def product_spec(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("Technische Spezifikation")
    b.line(f"Artikel-Nr.: SKU-{rng.randint(100000,999999)}")
    b.line(f"Maße: {rng.randint(10,200)} x {rng.randint(10,200)} x {rng.randint(10,200)} mm")
    b.line(f"Toleranz: ±{rng.randint(1,9)/10:.1f} mm")
    b.line(f"Materialcharge: LOT-{rng.randint(100000,999999)}")
    # invalid-checksum near-miss (looks like a Steuer-ID, fails the check digit)
    b.line(f"Interne Referenz: {P.make_invalid_digits(P.steuer_id(rng), rng)}")


def faq(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("Häufige Fragen (FAQ)")
    for _ in range(rng.randint(3, 5)):
        b.line(f"F: {fkr.sentence()}")
        b.line(f"A: {fkr.paragraph(nb_sentences=2)}")
        b.line()


def meeting_notes(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line(f"Protokoll Produktmeeting {rng.randint(1,28):02d}.{rng.choice(_MONTHS)}.2025")
    b.line("Themen:")
    for _ in range(rng.randint(3, 5)):
        b.line(f"  * {fkr.bs()}")
    b.line(f"Nächstes Review: KW{rng.randint(1,52)}")


def server_log_clean(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("# application log (anonymised)")
    for _ in range(rng.randint(4, 8)):
        lvl = rng.choice(["INFO", "WARN", "DEBUG", "ERROR"])
        b.line(f"2025-{rng.choice(_MONTHS)}-{rng.randint(1,28):02d} {lvl} worker-{rng.randint(1,16)} processed batch {rng.randint(1000,9999)}")


def app_config(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("# service configuration")
    b.line(f"timeout_ms = {rng.choice([500,1000,2000,5000])}")
    b.line(f"max_retries = {rng.randint(1,5)}")
    b.line(f"region = eu-central-{rng.randint(1,3)}")
    b.line(f"feature_flag_x = {rng.choice(['true','false'])}")
    b.line(f"cache_size_mb = {rng.choice([64,128,256,512])}")


def changelog(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line("CHANGELOG")
    for _ in range(rng.randint(4, 7)):
        b.line(f"v{rng.randint(1,9)}.{rng.randint(0,30)} — {fkr.catch_phrase()}")


def marketing_blurb(b: DocBuilder, fkr: Faker, rng: random.Random) -> None:
    b.line(fkr.catch_phrase())
    b.line()
    b.line(fkr.paragraph(nb_sentences=4))
    b.line(f"Mehr unter www.example-bosch-demo.invalid/{fkr.word()}")


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Template:
    name: str
    folder: str
    fn: object
    kind: str  # "pii" | "decoy"


PII_TEMPLATES: list[Template] = [
    Template("hr_record", "hr", hr_record, "pii"),
    Template("onboarding", "hr", onboarding, "pii"),
    Template("leave_request", "hr", leave_request, "pii"),
    Template("payslip", "hr", payslip, "pii"),
    Template("invoice", "finance", invoice, "pii"),
    Template("expense_report", "finance", expense_report, "pii"),
    Template("purchase_order", "finance", purchase_order, "pii"),
    Template("customer_email", "email", customer_email, "pii"),
    Template("vendor_email", "email", vendor_email, "pii"),
    Template("support_ticket", "support", support_ticket, "pii"),
    Template("employment_contract", "legal", employment_contract, "pii"),
    Template("consent_form", "legal", consent_form, "pii"),
    Template("trip_notes", "travel", trip_notes, "pii"),
    Template("id_verification", "legal", id_verification, "pii"),
    Template("access_log_pii", "logs", access_log_pii, "pii"),
]

DECOY_TEMPLATES: list[Template] = [
    Template("release_notes", "product", release_notes, "decoy"),
    Template("product_spec", "product", product_spec, "decoy"),
    Template("faq", "product", faq, "decoy"),
    Template("meeting_notes", "product", meeting_notes, "decoy"),
    Template("server_log_clean", "logs", server_log_clean, "decoy"),
    Template("app_config", "config", app_config, "decoy"),
    Template("changelog", "product", changelog, "decoy"),
    Template("marketing_blurb", "marketing", marketing_blurb, "decoy"),
]
