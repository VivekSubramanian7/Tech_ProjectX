# PII Detection Scope — Bosch GDPR Data Discovery

Tiered catalog of personal-data attributes the engine detects. P1 is the canonical
must-detect set from the case study; P2/P3 are GDPR-recognized extensions.
This is the backbone of the detection functional requirements.

## Priority 1 — Canonical (from case study; must-detect)
| # | Attribute | Modality | Detection approach |
|---|-----------|----------|--------------------|
| 1 | First name, last name | text | NER + dictionary |
| 2 | Username / login name | text | regex + context |
| 3 | Email address | text | regex |
| 4 | Signature | image | image / handwriting detection |
| 5 | Photo / video of a person | image/video | face / person detection |
| 6 | Phone number (mobile/landline) | text | regex + validation |
| 7 | Fax number | text | regex |
| 8 | Home address | text | NER + pattern |
| 9 | Billing / shipping address | text | NER + pattern |
| 10 | Passport number | text/OCR | regex + checksum |
| 11 | ID card number | text/OCR | regex + checksum |
| 12 | Driver's license number | text/OCR | regex + checksum |
| 13 | Travel history | text | NER + context |

## Priority 2 — Additional common identifiers (GDPR Art. 4, general personal data)
Bank account / IBAN [MVP]; credit/debit card PAN [MVP]; IP address [MVP, low risk weight];
employee ID / personnel number [MVP — needs Bosch format]; vehicle registration / license
plate [MVP — promoted to image path]; German national personal-ID family [all MVP, DE-scoped, checksum-validated]:
Personalausweisnummer (national ID card no. — = the "ID card number" detector, DE format),
Sozialversicherungsnummer (social security / pension insurance no., 12-char + check digit),
Steuer-Identifikationsnummer (Tax-ID, 11-digit + check digit);
date of birth [deferred — high FP]; place of birth
[deferred]; device / location data [deferred]; health-insurance number [deferred];
nationality [deferred]; gender [deferred]; marital status [deferred].

### MVP attribute set (final)
Locale = GERMANY-FIRST (Bosch HQ + bulk of estate); other-country formats are Growth.
All canonical P1 fully detectable (names, username, email, phone, fax, home addr, billing/
shipping addr, passport, ID card [DE format], driver's licence, signature[image], face/photo
of person [image]) + travel history [best-effort via LLM] + license plate [image] + IBAN +
credit card PAN + IP address + employee ID [pending Bosch format] + German social security no.
+ German Tax-ID.
Deferred: video modality; non-DE region formats; semantic P2 (DOB, place of birth, nationality,
gender, marital status, device/location, health-insurance no.); ALL P3 special categories.
Rule for MVP inclusion: deterministic pattern/checksum, no semantic inference, DE-scoped.

## Priority 3 — Special categories (GDPR Art. 9, highest sensitivity)
Racial/ethnic origin; political opinions; religious/philosophical beliefs;
trade-union membership; genetic data; biometric data (facial recognition, fingerprints —
overlaps P1 #5); health data; sex life / sexual orientation.

## Design notes
- Art. 9 special-category data carries a HIGHER default legal-risk weight → feeds risk-scoring.
- IP address and location data are GENERAL personal data (Art. 6), NOT Art. 9 special category.
- Engine architecture must allow adding/tuning attribute detectors (AI generates rules offline;
  deterministic detectors run at scan time).

## Classification Enum — COMPLETE mapping (single source of truth)
Every detectable attribute MUST appear here. Engine emits `machine_code`; UI renders `display_label`.
Risk weight: Critical > High > Medium > Low (feeds risk score). GDPR focus = design-time principle.
MVP = in 48h scope; Growth/Vision = deferred (enum reserved so data model is stable).

### Priority 1 — canonical (all MVP)
| machine_code | display_label | modality | MVP | risk | GDPR focus |
|--------------|---------------|----------|-----|------|-----------|
| PERSON_NAME | Full name | text | ✅ | Medium | Art.5/17 |
| USERNAME | Username / login | text | ✅ | Low | Art.5/17 |
| EMAIL | Email address | text | ✅ | Medium | Art.5/17 |
| SIGNATURE | Signature | image | ✅ | High | Art.5/17/9-adj |
| FACE | Photo of a person | image/video | ✅ (image) | High | Art.9 (biometric) |
<!-- Detection: FACE + LICENSE_PLATE + person via YOLO (Ultralytics), Tier-1 DETERMINISTIC (fixed weights+NMS).
     OCR (EasyOCR/Tesseract) reads plate numbers / text-in-images. RetinaFace optional Tier-2 face fallback for
     low-confidence/small/occluded faces (FN is highest cost). SIGNATURE = no standard YOLO class → small custom
     model/heuristic; lowest image priority on de-scope ladder. -->
| PHONE_NUMBER | Phone number | text | ✅ | Medium | Art.5/17 |
| FAX_NUMBER | Fax number | text | ✅ | Low | Art.5/17 |
| HOME_ADDRESS | Home address | text | ✅ | High | Art.5/17 |
| BILLING_SHIPPING_ADDRESS | Billing / shipping address | text | ✅ | Medium | Art.5/17 |
| PASSPORT_NUMBER | Passport number | text/OCR | ✅ | Critical | Art.5/17/32 |
| DE_PERSONALAUSWEIS | German ID card number | text/OCR | ✅ | Critical | Art.5/17/32 |
| DRIVERS_LICENSE_NUMBER | Driver's licence number | text/OCR | ✅ | High | Art.5/17/32 |
| TRAVEL_HISTORY | Travel history | text | ✅ (best-effort/LLM) | Medium | Art.5/17 |

### Priority 2 — general identifiers (Art.4)
| machine_code | display_label | modality | MVP | risk | GDPR focus |
|--------------|---------------|----------|-----|------|-----------|
| IBAN | Bank account (IBAN) | text | ✅ | High | Art.5/17/32 |
| CREDIT_CARD_NUMBER | Payment card number | text | ✅ | Critical | Art.5/17/32 |
| IP_ADDRESS | IP address | text | ✅ | Low | Art.5/17 |
| EMPLOYEE_ID | Employee / personnel ID | text | ✅ (pending Bosch format) | Medium | Art.5/17 |
| LICENSE_PLATE | Vehicle licence plate | image | ✅ | Medium | Art.5/17 |
| DE_SOZIALVERSICHERUNGSNR | German social security number | text/OCR | ✅ | Critical | Art.5/17/32 |
| DE_STEUER_ID | German tax ID | text/OCR | ✅ | High | Art.5/17/32 |
| DATE_OF_BIRTH | Date of birth | text | Growth | Medium | Art.5/17 |
| PLACE_OF_BIRTH | Place of birth | text | Growth | Low | Art.5/17 |
| NATIONALITY | Nationality | text | Growth | Medium | Art.5/17 |
| GENDER | Gender | text | Growth | Low | Art.5/17 |
| MARITAL_STATUS | Marital status | text | Growth | Low | Art.5/17 |
| HEALTH_INSURANCE_NUMBER | Health insurance number | text | Growth | High | Art.9-adj |
| DEVICE_LOCATION | Device / location data | text | Growth | Medium | Art.5/17 |
| NON_DE_NATIONAL_ID | National ID (non-DE) | text/OCR | Growth | High | Art.5/17/32 |
| NON_DE_TAX_ID | Tax ID (non-DE) | text/OCR | Growth | High | Art.5/17/32 |

### Priority 3 — special categories (Art.9, all Critical, all Vision)
| machine_code | display_label | modality | MVP | risk | GDPR focus |
|--------------|---------------|----------|-----|------|-----------|
| RACIAL_ETHNIC_ORIGIN | Racial / ethnic origin | text | Vision | Critical | Art.9 |
| POLITICAL_OPINION | Political opinion | text | Vision | Critical | Art.9 |
| RELIGIOUS_BELIEF | Religious / philosophical belief | text | Vision | Critical | Art.9 |
| TRADE_UNION_MEMBERSHIP | Trade-union membership | text | Vision | Critical | Art.9 |
| GENETIC_DATA | Genetic data | text | Vision | Critical | Art.9 |
| BIOMETRIC_DATA | Biometric data | image | Vision | Critical | Art.9 |
| HEALTH_DATA | Health data | text | Vision | Critical | Art.9 |
| SEX_LIFE_ORIENTATION | Sex life / sexual orientation | text | Vision | Critical | Art.9 |

Enum governance: the engine MUST NOT emit a classification absent from this table. Adding a detector
requires adding its enum row (code + label + risk + GDPR focus) first. This is a hard architecture rule.

## Sources
- https://gdpr-info.eu/art-9-gdpr/
- https://ico.org.uk/for-organisations/uk-gdpr-guidance-and-resources/lawful-basis/special-category-data/
