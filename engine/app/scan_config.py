"""Load engine scan directory from config/scan.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class ScanOptions:
    """Runtime scan behaviour (Tier-2 / OneDrive remain stubbed when disabled)."""

    use_spacy: bool = False
    use_ml_image: bool = True
    # Bounded parallelism. cpu_budget_pct caps how much of the machine a scan may
    # use (workers ≈ that fraction of cores). max_workers > 0 clamps further;
    # max_workers == 1 forces the sequential path.
    cpu_budget_pct: int = 30
    max_workers: int = 0


@dataclass(frozen=True)
class ScanConfig:
    path: Path
    scope_id: str | None
    mode: str = "full"
    tier2: bool = False
    reapply_ruleset: bool = False
    source: str = "local"
    onedrive_fixture: Path | None = None
    use_spacy: bool = False
    use_ml_image: bool = True
    cpu_budget_pct: int = 30
    max_workers: int = 0


def repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def default_config_path() -> Path:
    return repo_root() / "config" / "scan.yaml"


def load_scan_config(config_path: Path | None = None) -> ScanConfig:
    """Load scan target from YAML. Relative paths resolve against repo root."""
    cfg_file = (config_path or default_config_path()).resolve()
    if not cfg_file.is_file():
        raise FileNotFoundError(f"scan config not found: {cfg_file}")

    raw = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"scan config must be a mapping: {cfg_file}")

    path_raw = raw.get("path")
    if not path_raw or not isinstance(path_raw, str):
        raise ValueError(f"scan config missing required 'path' string: {cfg_file}")

    path = Path(path_raw)
    if not path.is_absolute():
        path = (repo_root() / path).resolve()

    scope_id = raw.get("scope_id")
    if scope_id is not None and not isinstance(scope_id, str):
        raise ValueError(f"scan config 'scope_id' must be a string: {cfg_file}")

    mode = raw.get("mode", "full")
    if mode not in {"full", "delta"}:
        raise ValueError(f"scan config 'mode' must be 'full' or 'delta': {cfg_file}")

    tier2 = bool(raw.get("tier2", False))
    reapply_ruleset = bool(raw.get("reapply_ruleset", False))
    source = raw.get("source", "local")
    if source not in {"local", "onedrive_fixture"}:
        raise ValueError(f"scan config 'source' must be 'local' or 'onedrive_fixture': {cfg_file}")

    fixture_raw = raw.get("onedrive_fixture")
    onedrive_fixture: Path | None = None
    if fixture_raw:
        onedrive_fixture = Path(fixture_raw)
        if not onedrive_fixture.is_absolute():
            onedrive_fixture = (repo_root() / onedrive_fixture).resolve()

    use_spacy = bool(raw.get("use_spacy", False))
    use_ml_image = bool(raw.get("use_ml_image", True))
    cpu_budget_pct = int(raw.get("cpu_budget_pct", 30))
    max_workers = int(raw.get("max_workers", 0))

    return ScanConfig(
        path=path,
        scope_id=scope_id,
        mode=mode,
        tier2=tier2,
        reapply_ruleset=reapply_ruleset,
        source=source,
        onedrive_fixture=onedrive_fixture,
        use_spacy=use_spacy,
        use_ml_image=use_ml_image,
        cpu_budget_pct=cpu_budget_pct,
        max_workers=max_workers,
    )


def scan_options_from_config(cfg: ScanConfig) -> ScanOptions:
    return ScanOptions(
        use_spacy=cfg.use_spacy,
        use_ml_image=cfg.use_ml_image,
        cpu_budget_pct=cfg.cpu_budget_pct,
        max_workers=cfg.max_workers,
    )


def resolve_worker_count(options: ScanOptions) -> int:
    """Worker threads for a scan: a bounded fraction of cores (the CPU ceiling).

    workers ≈ floor(cpu_budget_pct/100 * cores); max_workers > 0 clamps it; the
    result is always >= 1 so a scan never stalls.
    """
    import math
    import os

    cores = os.cpu_count() or 1
    pct = max(1, min(100, int(getattr(options, "cpu_budget_pct", 30) or 30)))
    budget = max(1, math.floor(pct / 100.0 * cores))
    cap = int(getattr(options, "max_workers", 0) or 0)
    if cap > 0:
        return max(1, min(cap, budget))
    return budget


def resolve_scan_source(cfg: ScanConfig) -> Path | object:
    """Return scan target: local Path or OneDriveGraphSource."""
    if cfg.source == "onedrive_fixture":
        from app.sources.onedrive_graph import OneDriveGraphSource

        fixture = cfg.onedrive_fixture or (repo_root() / "data" / "onedrive_fixture.json")
        return OneDriveGraphSource.from_fixture(fixture)
    return cfg.path
