"""Deterministic artifact serialization, plotting, hashing, and manifests."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
import seaborn as sns  # noqa: E402

from .models import ModelFit, deterministic_model_summaries
from .panel import sha256_file


CANONICAL_CSV_FILES = [
    "country_universe.csv",
    "country_coverage.csv",
    "sample_flow.csv",
    "sample_composition.csv",
    "missingness_by_variable.csv",
    "missingness_patterns.csv",
    "coefficients.csv",
    "model_diagnostics.csv",
    "turning_points.csv",
]
REQUIRED_OUTPUTS = [
    *CANONICAL_CSV_FILES,
    "figures/ekc_plot.png",
    "model_summaries.txt",
    "results_report.md",
    *(f"tables/{Path(name).stem}.md" for name in CANONICAL_CSV_FILES),
]
ENVIRONMENT_PACKAGES = [
    "linearmodels",
    "matplotlib",
    "numpy",
    "pandas",
    "PyYAML",
    "requests",
    "scipy",
    "seaborn",
    "statsmodels",
    "tabulate",
]


def stable_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_csv(frame: pd.DataFrame, path: str | Path) -> None:
    """Write a platform-independent CSV with stable numeric precision."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(
        destination,
        index=False,
        lineterminator="\n",
        float_format="%.12g",
        na_rep="",
    )


def create_ekc_plot(analytic_panel: pd.DataFrame, path: str | Path) -> None:
    """Render the descriptive pooled quadratic figure."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    plot_data = analytic_panel.sort_values(["country", "year"], kind="stable")
    sns.set_theme(style="whitegrid")
    figure, axis = plt.subplots(figsize=(10, 6), dpi=100)
    sns.scatterplot(
        data=plot_data,
        x="GDP_per_capita",
        y="CO2_per_capita",
        hue="income_group",
        hue_order=sorted(plot_data["income_group"].dropna().unique()),
        alpha=0.6,
        ax=axis,
    )
    sns.regplot(
        data=plot_data,
        x="GDP_per_capita",
        y="CO2_per_capita",
        scatter=False,
        order=2,
        ci=None,
        color="black",
        label="Pooled quadratic fit",
        ax=axis,
    )
    axis.set_title("Environmental Kuznets Curve Analysis\nGDP vs CO2 per capita")
    axis.set_xlabel("GDP per capita (constant 2015 US$)")
    axis.set_ylabel("CO2 emissions (metric tons per capita)")
    axis.legend()
    figure.tight_layout()
    figure.savefig(
        destination,
        metadata={"Software": "environmental-growth-analysis"},
    )
    plt.close(figure)


def _code_hashes(repository_root: Path) -> dict[str, str]:
    candidates = [
        *sorted((repository_root / "src" / "environmental_growth").glob("*.py")),
        repository_root / "config" / "analysis.yaml",
        repository_root / "reports" / "README.template.md",
        repository_root / "pyproject.toml",
        repository_root / "uv.lock",
        repository_root / "Makefile",
    ]
    return {
        path.relative_to(repository_root).as_posix(): sha256_file(path)
        for path in candidates
        if path.is_file()
    }


def _environment() -> dict[str, Any]:
    packages = {}
    for package in ENVIRONMENT_PACKAGES:
        try:
            packages[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            packages[package] = None
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "system": platform.system(),
        "packages": packages,
    }


def _output_hashes(output_dir: Path) -> dict[str, dict[str, Any]]:
    outputs = {}
    for path in sorted(output_dir.rglob("*")):
        if not path.is_file() or path.name == "run_manifest.json":
            continue
        relative = path.relative_to(output_dir).as_posix()
        outputs[relative] = {
            "sha256": sha256_file(path),
            "bytes": path.stat().st_size,
            "canonical": relative != "model_summaries.txt",
        }
    return outputs


def build_manifest(
    output_dir: Path,
    repository_root: Path,
    source_lock: dict[str, Any],
    source_lock_path: Path,
    config: dict[str, Any],
    selected_country_set_sha256: str,
) -> dict[str, Any]:
    code = _code_hashes(repository_root)
    environment = _environment()
    basis = {
        "source_snapshot_sha256": source_lock["content_sha256"],
        "source_lock_sha256": sha256_file(source_lock_path),
        "resolved_config_sha256": stable_json_hash(config),
        "code_sha256": stable_json_hash(code),
        "environment_sha256": stable_json_hash(environment),
        "selected_country_set_sha256": selected_country_set_sha256,
    }
    return {
        "schema_version": 1,
        "run_id": stable_json_hash(basis)[:16],
        "source_snapshot_id": source_lock["snapshot_id"],
        "source_snapshot_created_at": source_lock["created_at"],
        "source_snapshot_sha256": source_lock["content_sha256"],
        "source_lock_sha256": basis["source_lock_sha256"],
        "selected_country_set_sha256": selected_country_set_sha256,
        "resolved_config_sha256": basis["resolved_config_sha256"],
        "resolved_config": config,
        "code": code,
        "code_sha256": basis["code_sha256"],
        "environment": environment,
        "environment_sha256": basis["environment_sha256"],
        "outputs": _output_hashes(output_dir),
    }


def write_manifest(manifest: dict[str, Any], path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def refresh_manifest_outputs(output_dir: str | Path) -> dict[str, Any]:
    artifact_dir = Path(output_dir)
    manifest_path = artifact_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["outputs"] = _output_hashes(artifact_dir)
    write_manifest(manifest, manifest_path)
    return manifest


def write_analysis_artifacts(
    frames: dict[str, pd.DataFrame],
    analytic_panel: pd.DataFrame,
    fits: dict[tuple[str, str], ModelFit],
    output_dir: str | Path,
    repository_root: str | Path,
    source_lock: dict[str, Any],
    source_lock_path: str | Path,
    config: dict[str, Any],
    selected_country_set_sha256: str,
) -> dict[str, Any]:
    artifact_dir = Path(output_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    # Report-derived files belong to the report command. Removing only the known
    # contract paths prevents a new structured run from carrying stale Markdown.
    report_paths = [
        artifact_dir / "results_report.md",
        *(
            artifact_dir / "tables" / f"{Path(filename).stem}.md"
            for filename in CANONICAL_CSV_FILES
        ),
    ]
    for report_path in report_paths:
        report_path.unlink(missing_ok=True)
    for filename in CANONICAL_CSV_FILES:
        key = Path(filename).stem
        if key not in frames:
            raise KeyError(f"No frame supplied for required artifact {filename}")
        write_csv(frames[key], artifact_dir / filename)
    create_ekc_plot(analytic_panel, artifact_dir / "figures" / "ekc_plot.png")
    (artifact_dir / "model_summaries.txt").write_text(
        deterministic_model_summaries(fits), encoding="utf-8", newline="\n"
    )
    manifest = build_manifest(
        artifact_dir,
        Path(repository_root),
        source_lock,
        Path(source_lock_path),
        config,
        selected_country_set_sha256,
    )
    write_manifest(manifest, artifact_dir / "run_manifest.json")
    return manifest


def verify_manifest(output_dir: str | Path) -> list[str]:
    """Return all missing or hash-mismatched committed outputs."""
    artifact_dir = Path(output_dir)
    manifest_path = artifact_dir / "run_manifest.json"
    if not manifest_path.is_file():
        return ["run_manifest.json is missing"]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    errors = []
    for relative in REQUIRED_OUTPUTS:
        if relative not in manifest.get("outputs", {}):
            errors.append(f"required output absent from manifest: {relative}")
    for relative, metadata in manifest.get("outputs", {}).items():
        path = artifact_dir / relative
        if not path.is_file():
            errors.append(f"manifest output is missing: {relative}")
        elif sha256_file(path) != metadata["sha256"]:
            errors.append(f"manifest hash mismatch: {relative}")
    return errors
