"""Command-line orchestration for refresh, reproduction, reporting, and verification."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any, Sequence

from .artifacts import verify_manifest, write_analysis_artifacts
from .config import load_config
from .diagnostics import (
    missingness_by_variable,
    missingness_patterns,
    sample_composition,
    sample_flow,
)
from .estimands import turning_points_table
from .models import coefficients_table, fit_declared_models, model_diagnostics_table
from .panel import build_panel, load_locked_sources, transform_analysis_panel
from .report import readme_matches_run, render_reports
from .selection import apply_coverage_rule, build_country_universe


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def reproduce(
    config_path: str | Path,
    lock_path: str | Path,
    output_dir: str | Path,
    repository_root: str | Path = REPOSITORY_ROOT,
) -> dict[str, Any]:
    """Run the complete structured analysis using only the locked snapshot."""
    config = load_config(config_path)
    source_lock, country_metadata, sources = load_locked_sources(lock_path)
    country_universe = build_country_universe(
        country_metadata,
        config,
        source_lock["classification_snapshot_date"],
    )
    eligible_panel = build_panel(country_universe, sources, config)
    country_coverage, retained_panel = apply_coverage_rule(
        eligible_panel, country_universe, config
    )
    analytic_panel = transform_analysis_panel(retained_panel, config)
    if analytic_panel.empty:
        raise RuntimeError("The locked snapshot produces an empty analytic sample")

    scopes = {
        "eligible_universe": eligible_panel,
        "retained_country_panel": retained_panel,
        "analytic_sample": analytic_panel,
    }
    required_variables = config["coverage"]["required_variables"]
    fits = fit_declared_models(analytic_panel, config)
    frames = {
        "country_universe": country_universe,
        "country_coverage": country_coverage,
        "sample_flow": sample_flow(eligible_panel, retained_panel, analytic_panel),
        "sample_composition": sample_composition(analytic_panel, config),
        "missingness_by_variable": missingness_by_variable(
            scopes, required_variables
        ),
        "missingness_patterns": missingness_patterns(scopes, required_variables),
        "coefficients": coefficients_table(fits, config["confidence_level"]),
        "model_diagnostics": model_diagnostics_table(fits, config),
        "turning_points": turning_points_table(fits, config),
    }
    country_hashes = country_coverage["selected_country_set_sha256"].unique()
    if len(country_hashes) != 1:
        raise RuntimeError("Coverage audit did not resolve one selected-country hash")
    manifest = write_analysis_artifacts(
        frames,
        analytic_panel,
        fits,
        output_dir,
        repository_root,
        source_lock,
        lock_path,
        config,
        str(country_hashes[0]),
    )
    composition = frames["sample_composition"].set_index("sample_id")
    full = composition.loc["full_sample"]
    print(
        f"Reproduced run {manifest['run_id']}: "
        f"{int(full['n_observations'])} observations, "
        f"{int(full['n_countries'])} countries."
    )
    return manifest


def report(
    output_dir: str | Path,
    template_path: str | Path,
    readme_path: str | Path,
) -> dict[str, Any]:
    manifest = render_reports(output_dir, template_path, readme_path)
    print(f"Rendered reports for run {manifest['run_id']}.")
    return manifest


def _tree_hashes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def verify(
    config_path: str | Path,
    lock_path: str | Path,
    output_dir: str | Path,
    template_path: str | Path,
    readme_path: str | Path,
    repository_root: str | Path = REPOSITORY_ROOT,
) -> None:
    """Regenerate offline and fail on stale, missing, mixed-run, or altered outputs."""
    artifact_dir = Path(output_dir)
    errors = verify_manifest(artifact_dir)
    manifest_path = artifact_dir / "run_manifest.json"
    committed_manifest = None
    if manifest_path.is_file():
        committed_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not readme_matches_run(readme_path, committed_manifest):
            errors.append("README refers to a different run ID")

    with tempfile.TemporaryDirectory(prefix="environmental-growth-verify-") as temp:
        temp_root = Path(temp)
        regenerated_artifacts = temp_root / "artifacts" / "current"
        regenerated_readme = temp_root / "README.md"
        reproduce(
            config_path,
            lock_path,
            regenerated_artifacts,
            repository_root=repository_root,
        )
        report(regenerated_artifacts, template_path, regenerated_readme)

        committed_files = _tree_hashes(artifact_dir) if artifact_dir.is_dir() else {}
        regenerated_files = _tree_hashes(regenerated_artifacts)
        for relative in sorted(set(committed_files) | set(regenerated_files)):
            if relative not in committed_files:
                errors.append(f"committed artifact is missing: {relative}")
            elif relative not in regenerated_files:
                errors.append(f"unexpected committed artifact: {relative}")
            elif committed_files[relative] != regenerated_files[relative]:
                errors.append(f"committed artifact is stale: {relative}")
        if not Path(readme_path).is_file():
            errors.append("README.md is missing")
        elif Path(readme_path).read_bytes() != regenerated_readme.read_bytes():
            errors.append("README-generated content is stale")

    if errors:
        unique_errors = list(dict.fromkeys(errors))
        raise RuntimeError("Verification failed:\n- " + "\n- ".join(unique_errors))
    if committed_manifest is None:
        raise RuntimeError("Verification failed: run manifest is missing")
    print(f"Verified run {committed_manifest['run_id']} against locked inputs.")


def _resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=str(REPOSITORY_ROOT))
    parser.add_argument("--config", default="config/analysis.yaml")
    parser.add_argument("--lock", default="data/sources.lock.json")
    parser.add_argument("--output", default="artifacts/current")
    parser.add_argument("--template", default="reports/README.template.md")
    parser.add_argument("--readme", default="README.md")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("refresh-data", help="Contact live sources and update the lock")
    subparsers.add_parser("reproduce", help="Run analysis from the locked snapshot")
    subparsers.add_parser("report", help="Render Markdown and README from artifacts")
    subparsers.add_parser("verify", help="Check a clean offline regeneration")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = Path(args.root).resolve()
    config_path = _resolve(root, args.config)
    lock_path = _resolve(root, args.lock)
    output_dir = _resolve(root, args.output)
    template_path = _resolve(root, args.template)
    readme_path = _resolve(root, args.readme)

    if args.command == "refresh-data":
        from .sources import refresh_sources

        lock = refresh_sources(load_config(config_path), root / "data")
        print(f"Locked source snapshot {lock['snapshot_id']}.")
    elif args.command == "reproduce":
        reproduce(config_path, lock_path, output_dir, repository_root=root)
    elif args.command == "report":
        report(output_dir, template_path, readme_path)
    elif args.command == "verify":
        verify(
            config_path,
            lock_path,
            output_dir,
            template_path,
            readme_path,
            repository_root=root,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
