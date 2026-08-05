"""Render Markdown views, the results report, and the repository README."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from .artifacts import CANONICAL_CSV_FILES, refresh_manifest_outputs
from .panel import sha256_file


def markdown_table(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.select_dtypes(include="float").columns:
        display[column] = display[column].map(
            lambda value: "" if pd.isna(value) else f"{value:.6g}"
        )
    display = display.fillna("")
    return display.to_markdown(index=False, disable_numparse=True)


def _preferred_coefficients(
    coefficients: pd.DataFrame, manifest: dict[str, Any]
) -> pd.DataFrame:
    preferred = manifest["resolved_config"]["model"]["preferred_model_id"]
    columns = [
        "sample_id",
        "term",
        "estimate",
        "std_error",
        "p_value",
        "ci_lower",
        "ci_upper",
    ]
    return coefficients.loc[coefficients["model_id"].eq(preferred), columns]


def _turning_point_narrative(turning_points: pd.DataFrame) -> str:
    row = turning_points.iloc[0]
    estimate = float(row["estimate_usd"])
    status = row["identification_status"]
    if status == "finite_turning_point_identified":
        return (
            f"The preferred specification estimates a turning point of "
            f"${estimate:,.0f}, within observed GDP support."
        )
    if status == "finite_turning_point_not_identified":
        return (
            f"The coefficient ratio implies ${estimate:,.0f}, but the quadratic "
            "confidence interval includes zero. The finite turning point is therefore "
            "not statistically identified; the delta interval is recorded only as a "
            "mechanical diagnostic."
        )
    if status == "turning_point_outside_observed_support":
        return (
            f"The coefficient ratio implies ${estimate:,.0f}, outside observed GDP "
            "support, so it is not interpreted as an in-sample turning point."
        )
    return f"Turning-point status: `{status}`."


def _coverage_text(manifest: dict[str, Any]) -> str:
    config = manifest["resolved_config"]
    period = config["period"]
    coverage = config["coverage"]
    variables = ", ".join(f"`{name}`" for name in coverage["required_variables"])
    return (
        f"Retain eligible countries with at least "
        f"{coverage['minimum_complete_years']} complete years from "
        f"{period['start_year']}–{period['end_year']} across {variables}."
    )


def _artifact_links() -> str:
    links = [
        ("Run manifest", "artifacts/current/run_manifest.json"),
        ("Country universe", "artifacts/current/country_universe.csv"),
        ("Coverage audit", "artifacts/current/country_coverage.csv"),
        ("Sample flow", "artifacts/current/sample_flow.csv"),
        ("Coefficients", "artifacts/current/coefficients.csv"),
        ("Model diagnostics", "artifacts/current/model_diagnostics.csv"),
        ("Turning points", "artifacts/current/turning_points.csv"),
        ("Missingness by variable", "artifacts/current/missingness_by_variable.csv"),
        ("Missingness patterns", "artifacts/current/missingness_patterns.csv"),
        ("Complete results report", "artifacts/current/results_report.md"),
    ]
    return "\n".join(f"- [{label}]({path})" for label, path in links)


def _replace_placeholders(template: str, values: dict[str, str]) -> str:
    rendered = template
    for name, value in values.items():
        rendered = rendered.replace("{{" + name + "}}", value)
    if "{{" in rendered or "}}" in rendered:
        raise ValueError("README template contains an unresolved placeholder")
    return rendered


def build_results_report(
    manifest: dict[str, Any],
    sample_table: str,
    coefficient_table: str,
    turning_table: str,
    turning_narrative: str,
    missingness_table: str,
) -> str:
    return f"""# Generated Results Report

<!-- run-id: {manifest['run_id']} -->

Run `{manifest['run_id']}` uses locked source snapshot `{manifest['source_snapshot_id']}`.

## Resolved selection rule

{_coverage_text(manifest)}

## Sample composition

{sample_table}

## Preferred-model coefficients

{coefficient_table}

## Turning point

{turning_narrative}

{turning_table}

## Missingness in the retained-country panel

{missingness_table}

## Figure

![Environmental Kuznets Curve](figures/ekc_plot.png)
"""


def render_reports(
    output_dir: str | Path,
    template_path: str | Path,
    readme_path: str | Path,
) -> dict[str, Any]:
    artifact_dir = Path(output_dir)
    manifest_path = artifact_dir / "run_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_template_hash = manifest.get("code", {}).get(
        "reports/README.template.md"
    )
    if expected_template_hash is None:
        raise ValueError("Run manifest does not bind the README template")
    if sha256_file(template_path) != expected_template_hash:
        raise RuntimeError("README template changed; run reproduce before report")
    frames = {
        Path(filename).stem: pd.read_csv(artifact_dir / filename)
        for filename in CANONICAL_CSV_FILES
    }

    table_dir = artifact_dir / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in frames.items():
        (table_dir / f"{name}.md").write_text(
            markdown_table(frame) + "\n", encoding="utf-8", newline="\n"
        )

    sample_table = markdown_table(frames["sample_composition"])
    preferred = _preferred_coefficients(frames["coefficients"], manifest)
    coefficient_table = markdown_table(preferred)
    turning_table = markdown_table(frames["turning_points"])
    turning_narrative = _turning_point_narrative(frames["turning_points"])
    retained_missingness = frames["missingness_by_variable"].loc[
        frames["missingness_by_variable"]["scope"].eq("retained_country_panel")
    ]
    missingness_table = markdown_table(retained_missingness)

    results_report = build_results_report(
        manifest,
        sample_table,
        coefficient_table,
        turning_table,
        turning_narrative,
        missingness_table,
    )
    (artifact_dir / "results_report.md").write_text(
        results_report, encoding="utf-8", newline="\n"
    )

    template = Path(template_path).read_text(encoding="utf-8")
    readme = _replace_placeholders(
        template,
        {
            "RUN_ID": manifest["run_id"],
            "SNAPSHOT_ID": manifest["source_snapshot_id"],
            "COVERAGE_RULE": _coverage_text(manifest),
            "SAMPLE_COMPOSITION_TABLE": sample_table,
            "PREFERRED_COEFFICIENTS_TABLE": coefficient_table,
            "TURNING_POINT_NARRATIVE": turning_narrative,
            "TURNING_POINT_TABLE": turning_table,
            "MISSINGNESS_TABLE": missingness_table,
            "ARTIFACT_LINKS": _artifact_links(),
        },
    )
    Path(readme_path).write_text(readme, encoding="utf-8", newline="\n")
    return refresh_manifest_outputs(artifact_dir)


def readme_matches_run(readme_path: str | Path, manifest: dict[str, Any]) -> bool:
    marker = f"<!-- run-id: {manifest['run_id']} -->"
    return marker in Path(readme_path).read_text(encoding="utf-8")
