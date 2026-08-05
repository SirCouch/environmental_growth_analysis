"""Configuration loading and validation."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


REQUIRED_TOP_LEVEL_KEYS = {
    "period",
    "sources",
    "country_universe",
    "coverage",
    "samples",
    "model",
    "turning_point",
    "confidence_level",
}


def load_config(path: str | Path = "config/analysis.yaml") -> dict[str, Any]:
    """Load and validate the resolved analysis configuration."""
    config_path = Path(path)
    with config_path.open(encoding="utf-8") as stream:
        raw = yaml.safe_load(stream)
    if not isinstance(raw, dict):
        raise ValueError(f"Configuration {config_path} must contain a mapping.")

    config = deepcopy(raw)
    missing = REQUIRED_TOP_LEVEL_KEYS.difference(config)
    if missing:
        raise ValueError(f"Configuration is missing keys: {sorted(missing)}")

    start_year = int(config["period"]["start_year"])
    end_year = int(config["period"]["end_year"])
    if start_year > end_year:
        raise ValueError("period.start_year must not exceed period.end_year")
    config["period"] = {"start_year": start_year, "end_year": end_year}

    minimum_years = int(config["coverage"]["minimum_complete_years"])
    period_length = end_year - start_year + 1
    if not 1 <= minimum_years <= period_length:
        raise ValueError("coverage.minimum_complete_years must fall within the period")
    config["coverage"]["minimum_complete_years"] = minimum_years

    confidence_level = float(config["confidence_level"])
    if not 0 < confidence_level < 1:
        raise ValueError("confidence_level must be strictly between zero and one")
    config["confidence_level"] = confidence_level

    sample_ids = [sample["id"] for sample in config["samples"]]
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("Sample IDs must be unique")
    model_ids = [spec["id"] for spec in config["model"]["specifications"]]
    if len(model_ids) != len(set(model_ids)):
        raise ValueError("Model specification IDs must be unique")
    if config["model"]["preferred_model_id"] not in model_ids:
        raise ValueError("model.preferred_model_id must name a declared specification")

    required = set(config["coverage"]["required_variables"])
    source_variables = set(config["sources"]["world_bank"]["indicators"].values())
    source_variables.add(config["sources"]["owid"]["output_column"])
    if not required.issubset(source_variables):
        unknown = sorted(required.difference(source_variables))
        raise ValueError(f"Coverage variables have no declared source: {unknown}")
    return config
