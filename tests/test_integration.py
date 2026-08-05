from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from environmental_growth.artifacts import write_analysis_artifacts
from environmental_growth.diagnostics import (
    missingness_by_variable,
    missingness_patterns,
    sample_composition,
    sample_flow,
)
from environmental_growth.estimands import turning_points_table
from environmental_growth.models import (
    coefficients_table,
    fit_declared_models,
    model_diagnostics_table,
)
from environmental_growth.panel import transform_analysis_panel
from environmental_growth.report import render_reports
from environmental_growth.selection import hash_country_set


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def _integration_inputs(analysis_config):
    config = analysis_config
    config["period"] = {"start_year": 2000, "end_year": 2007}
    config["coverage"]["minimum_complete_years"] = 5
    config["samples"] = [{"id": "full_sample", "label": "Full sample"}]
    config["turning_point"]["sample_id"] = "full_sample"

    retained = pd.read_csv(REPOSITORY_ROOT / "tests" / "fixtures" / "toy_panel.csv")
    analytic = transform_analysis_panel(retained, config)
    fits = fit_declared_models(analytic, config)
    country_codes = sorted(retained["country"].unique())
    country_hash = hash_country_set(country_codes)
    universe = (
        retained[
            ["country", "income_level_code", "income_group"]
        ]
        .drop_duplicates()
        .assign(
            country_name=lambda frame: frame["country"],
            income_level_name="Fixture income level",
            region_code="FIX",
            region_name="Fixture region",
            is_aggregate=False,
            eligible=True,
            eligibility_reason="eligible",
            classification_mode="fixture",
            classification_snapshot_date="2008-01-01",
        )
    )
    required = config["coverage"]["required_variables"]
    coverage = universe[["country", "country_name", "income_level_code", "income_group"]].assign(
        complete_years=8,
        first_complete_year=2000,
        last_complete_year=2007,
        included=True,
        exclusion_reason="included",
        coverage_rule="fixture",
        selected_country_set_sha256=country_hash,
    )
    scopes = {
        "eligible_universe": retained,
        "retained_country_panel": retained,
        "analytic_sample": analytic,
    }
    frames = {
        "country_universe": universe,
        "country_coverage": coverage,
        "sample_flow": sample_flow(retained, retained, analytic),
        "sample_composition": sample_composition(analytic, config),
        "missingness_by_variable": missingness_by_variable(scopes, required),
        "missingness_patterns": missingness_patterns(scopes, required),
        "coefficients": coefficients_table(fits, config["confidence_level"]),
        "model_diagnostics": model_diagnostics_table(fits, config),
        "turning_points": turning_points_table(fits, config),
    }
    return config, analytic, fits, frames, country_hash


def _render_fixture_run(
    destination, source_lock, source_lock_path, analysis_config
):
    config, analytic, fits, frames, country_hash = _integration_inputs(analysis_config)
    artifacts = destination / "artifacts"
    readme = destination / "README.md"
    write_analysis_artifacts(
        frames,
        analytic,
        fits,
        artifacts,
        REPOSITORY_ROOT,
        source_lock,
        source_lock_path,
        config,
        country_hash,
    )
    manifest = render_reports(
        artifacts,
        REPOSITORY_ROOT / "reports" / "README.template.md",
        readme,
    )
    hashes = {
        relative: metadata["sha256"]
        for relative, metadata in manifest["outputs"].items()
    }
    return hashes, readme.read_bytes()


def test_frozen_integration_fixture_has_deterministic_artifact_hashes(
    tmp_path, analysis_config
):
    source_lock = {
        "snapshot_id": "fixture-snapshot",
        "created_at": "2008-01-01T00:00:00Z",
        "content_sha256": "0" * 64,
    }
    source_lock_path = tmp_path / "sources.lock.json"
    source_lock_path.write_text(
        json.dumps(source_lock, sort_keys=True) + "\n", encoding="utf-8"
    )
    first_hashes, first_readme = _render_fixture_run(
        tmp_path / "first", source_lock, source_lock_path, analysis_config
    )
    second_hashes, second_readme = _render_fixture_run(
        tmp_path / "second", source_lock, source_lock_path, analysis_config
    )
    assert first_hashes == second_hashes
    assert first_readme == second_readme
