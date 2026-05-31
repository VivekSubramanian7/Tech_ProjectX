#!/usr/bin/env python3
"""Generate engine enums and SQL seed from classification_enum.yaml."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
YAML_PATH = ROOT / "enum" / "classification_enum.yaml"
ENUM_PY = ROOT / "engine" / "app" / "enums.py"
SEED_SQL = ROOT / "data" / "enum_seed.sql"


@dataclass(frozen=True)
class EnumEntry:
    machine_code: str
    display_label: str
    modality: str
    mvp: bool
    risk_weight: str
    gdpr_focus: str


def load_entries() -> list[EnumEntry]:
    raw = yaml.safe_load(YAML_PATH.read_text(encoding="utf-8"))
    return [
        EnumEntry(
            machine_code=e["machine_code"],
            display_label=e["display_label"],
            modality=e["modality"],
            mvp=bool(e["mvp"]),
            risk_weight=e["risk_weight"],
            gdpr_focus=e["gdpr_focus"],
        )
        for e in raw["entries"]
    ]


def emit_enums_py(entries: list[EnumEntry]) -> str:
    lines = [
        '"""Generated from enum/classification_enum.yaml — do not edit by hand."""',
        "from __future__ import annotations",
        "",
        "from dataclasses import dataclass",
        "",
        "",
        "@dataclass(frozen=True)",
        "class ClassificationEntry:",
        "    machine_code: str",
        "    display_label: str",
        "    modality: str",
        "    mvp: bool",
        "    risk_weight: str",
        "    gdpr_focus: str",
        "",
        "",
        "ENTRIES: dict[str, ClassificationEntry] = {",
    ]
    for e in entries:
        lines.append(
            f'    "{e.machine_code}": ClassificationEntry('
            f'machine_code="{e.machine_code}", '
            f'display_label={e.display_label!r}, '
            f'modality="{e.modality}", '
            f"mvp={e.mvp!r}, "
            f'risk_weight="{e.risk_weight}", '
            f"gdpr_focus={e.gdpr_focus!r}),"
        )
    lines.append("}")
    lines.append("")
    lines.append("MVP_TEXT_CODES = frozenset(")
    lines.append(
        "    e.machine_code for e in ENTRIES.values() if e.mvp and e.modality == 'text'"
    )
    lines.append(")")
    lines.append("")
    lines.append("")
    lines.append("def lookup(machine_code: str) -> ClassificationEntry:")
    lines.append('    """Resolve a machine_code to its enum row."""')
    lines.append("    return ENTRIES[machine_code]")
    lines.append("")
    return "\n".join(lines) + "\n"


def emit_seed_sql(entries: list[EnumEntry]) -> str:
    lines = [
        "-- Generated from enum/classification_enum.yaml",
        "DELETE FROM classification_enum;",
    ]
    for e in entries:
        lines.append(
            "INSERT INTO classification_enum "
            "(machine_code, display_label, modality, mvp_flag, risk_weight, gdpr_focus) "
            f"VALUES ('{e.machine_code}', {e.display_label!r}, '{e.modality}', "
            f"{1 if e.mvp else 0}, '{e.risk_weight}', {e.gdpr_focus!r});"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    entries = load_entries()
    ENUM_PY.parent.mkdir(parents=True, exist_ok=True)
    SEED_SQL.parent.mkdir(parents=True, exist_ok=True)
    ENUM_PY.write_text(emit_enums_py(entries), encoding="utf-8")
    SEED_SQL.write_text(emit_seed_sql(entries), encoding="utf-8")
    print(f"Wrote {ENUM_PY} and {SEED_SQL} ({len(entries)} rows)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
