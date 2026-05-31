"""CLI entrypoints."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.repositories import CatalogRepository
from app.scan_config import ScanConfig, default_config_path, load_scan_config, resolve_scan_source, scan_options_from_config
from app.services.scan_orchestrator import ScanOrchestrator

ROOT = Path(__file__).resolve().parents[2]


def _resolve_scan_target(
    path: str | None,
    config: str | None,
    *,
    mode: str | None,
    tier2: bool | None,
    reapply_ruleset: bool | None,
) -> tuple[object, ScanConfig]:
    cfg_path = Path(config).resolve() if config else None

    if path:
        cfg_file = cfg_path or default_config_path()
        if cfg_file.is_file():
            loaded = load_scan_config(cfg_file)
            folder = Path(path).resolve()
            cfg = ScanConfig(
                path=folder,
                scope_id=loaded.scope_id,
                mode=mode or loaded.mode,
                tier2=tier2 if tier2 is not None else loaded.tier2,
                reapply_ruleset=reapply_ruleset if reapply_ruleset is not None else loaded.reapply_ruleset,
                source="local",
                onedrive_fixture=loaded.onedrive_fixture,
                use_spacy=loaded.use_spacy,
                use_ml_image=loaded.use_ml_image,
            )
        else:
            cfg = ScanConfig(
                path=Path(path).resolve(),
                scope_id=None,
                mode=mode or "full",
                tier2=bool(tier2),
                reapply_ruleset=bool(reapply_ruleset),
            )
    else:
        cfg = load_scan_config(cfg_path)
        if mode:
            cfg = ScanConfig(
                path=cfg.path,
                scope_id=cfg.scope_id,
                mode=mode,
                tier2=tier2 if tier2 is not None else cfg.tier2,
                reapply_ruleset=reapply_ruleset if reapply_ruleset is not None else cfg.reapply_ruleset,
                source=cfg.source,
                onedrive_fixture=cfg.onedrive_fixture,
                use_spacy=cfg.use_spacy,
                use_ml_image=cfg.use_ml_image,
            )

    target = resolve_scan_source(cfg)
    if isinstance(target, Path) and not target.is_dir():
        raise SystemExit(f"scan path is not a directory: {target}")
    return target, cfg


def main(argv: list[str] | None = None) -> int:
    from app.scan_config import ScanConfig

    parser = argparse.ArgumentParser(prog="gdpr-engine")
    sub = parser.add_subparsers(dest="command", required=True)
    scan_p = sub.add_parser("scan", help="Run GDPR scan (full or delta)")
    scan_p.add_argument("--path", default=None, help="Directory to scan (overrides config path)")
    scan_p.add_argument("--config", default=None, help="Path to scan YAML")
    scan_p.add_argument(
        "--mode",
        choices=("full", "delta"),
        default=None,
        help="Scan mode (default from config or full)",
    )
    scan_p.add_argument(
        "--reapply-ruleset",
        action="store_true",
        help="Re-evaluate unchanged files when ruleset version bumped (delta only)",
    )
    scan_p.add_argument(
        "--tier2",
        action="store_true",
        help="Run Tier-2 escalation on low-confidence text findings",
    )
    args = parser.parse_args(argv)

    if args.command == "scan":
        try:
            target, cfg = _resolve_scan_target(
                args.path,
                args.config,
                mode=args.mode,
                tier2=args.tier2 if args.tier2 else None,
                reapply_ruleset=args.reapply_ruleset if args.reapply_ruleset else None,
            )
        except FileNotFoundError as exc:
            print(str(exc), file=sys.stderr)
            print("Provide --path or create config/scan.yaml with a 'path' entry.", file=sys.stderr)
            return 1
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 1

        db = ROOT / "data" / "catalog.sqlite"
        seed = ROOT / "data" / "enum_seed.sql"
        repo = CatalogRepository(db)
        repo.init_db(seed if seed.is_file() else None)
        orch = ScanOrchestrator(repo, default_options=scan_options_from_config(cfg))
        result = orch.run_scan(
            target,
            scope_id=cfg.scope_id,
            mode=cfg.mode,
            reapply_ruleset=cfg.reapply_ruleset,
            tier2=cfg.tier2,
            options=scan_options_from_config(cfg),
        )

        if cfg.mode == "delta":
            print(
                f"Delta scan: processed {result['files_processed']} files, "
                f"skipped {result['files_skipped']}, "
                f"{len(result['findings'])} new findings"
            )
        else:
            print(
                f"Full scan: {result['files_scanned']} files, "
                f"{len(result['findings'])} findings"
            )
        if result.get("tier2_applied"):
            print(f"Tier-2 applied to {result['tier2_applied']} findings")
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
