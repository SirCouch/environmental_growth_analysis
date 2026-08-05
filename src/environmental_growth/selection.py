"""Country-universe and coverage selection rules."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pandas as pd


def _eligibility_reason(row: pd.Series, config: dict[str, Any]) -> str:
    universe = config["country_universe"]
    if universe["exclude_aggregates"] and bool(row["is_aggregate"]):
        return "aggregate"
    if row["income_level_code"] not in universe["income_codes"]:
        return "unsupported_income_code"
    return "eligible"


def build_country_universe(
    metadata: pd.DataFrame,
    config: dict[str, Any],
    classification_snapshot_date: str,
) -> pd.DataFrame:
    """Apply the declared universe rule to a frozen metadata snapshot."""
    required = {
        "country",
        "country_name",
        "income_level_code",
        "income_level_name",
        "region_code",
        "region_name",
        "is_aggregate",
    }
    if not required.issubset(metadata.columns):
        raise ValueError(f"Country metadata is missing: {sorted(required - set(metadata.columns))}")
    if metadata["country"].duplicated().any():
        raise ValueError("Country metadata contains duplicate country codes")

    universe = metadata.loc[:, sorted(required)].copy()
    aggregate_text = universe["is_aggregate"].astype(str).str.lower()
    universe["is_aggregate"] = aggregate_text.isin({"true", "1", "yes"})
    universe["eligibility_reason"] = universe.apply(
        _eligibility_reason, axis=1, config=config
    )
    universe["eligible"] = universe["eligibility_reason"].eq("eligible")
    group_map = config["country_universe"]["income_groups"]
    universe["income_group"] = universe["income_level_code"].map(group_map)
    universe["classification_mode"] = config["country_universe"][
        "classification_mode"
    ]
    universe["classification_snapshot_date"] = classification_snapshot_date
    columns = [
        "country",
        "country_name",
        "income_level_code",
        "income_level_name",
        "income_group",
        "region_code",
        "region_name",
        "is_aggregate",
        "eligible",
        "eligibility_reason",
        "classification_mode",
        "classification_snapshot_date",
    ]
    return universe.loc[:, columns].sort_values("country", kind="stable").reset_index(drop=True)


def hash_country_set(country_codes: list[str]) -> str:
    payload = "\n".join(sorted(country_codes)).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def apply_coverage_rule(
    panel: pd.DataFrame,
    country_universe: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply the complete-year boundary and return its audit and retained panel."""
    required = config["coverage"]["required_variables"]
    minimum = config["coverage"]["minimum_complete_years"]
    start_year = config["period"]["start_year"]
    end_year = config["period"]["end_year"]
    complete = panel[required].notna().all(axis=1)
    coverage = (
        panel.loc[complete]
        .groupby("country", sort=True)
        .agg(
            complete_years=("year", "nunique"),
            first_complete_year=("year", "min"),
            last_complete_year=("year", "max"),
        )
        .reset_index()
    )
    eligible = country_universe.loc[
        country_universe["eligible"],
        ["country", "country_name", "income_level_code", "income_group"],
    ]
    audit = eligible.merge(coverage, on="country", how="left", validate="one_to_one")
    audit["complete_years"] = audit["complete_years"].fillna(0).astype(int)
    audit["first_complete_year"] = audit["first_complete_year"].astype("Int64")
    audit["last_complete_year"] = audit["last_complete_year"].astype("Int64")
    audit["included"] = audit["complete_years"].ge(minimum)
    audit["exclusion_reason"] = audit["included"].map(
        {True: "included", False: "insufficient_complete_years"}
    )
    rule = {
        "minimum_complete_years": minimum,
        "period": [start_year, end_year],
        "required_variables": required,
    }
    audit["coverage_rule"] = json.dumps(rule, sort_keys=True, separators=(",", ":"))
    retained_codes = audit.loc[audit["included"], "country"].tolist()
    audit["selected_country_set_sha256"] = hash_country_set(retained_codes)
    retained = panel[panel["country"].isin(retained_codes)].copy()
    retained = retained.sort_values(["country", "year"], kind="stable").reset_index(drop=True)
    return audit, retained
