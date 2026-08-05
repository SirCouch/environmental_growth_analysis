"""Structured sample-flow, composition, and missingness diagnostics."""

from __future__ import annotations

from typing import Any

import pandas as pd


def filter_sample(frame: pd.DataFrame, sample: dict[str, Any]) -> pd.DataFrame:
    groups = sample.get("income_groups")
    if not groups:
        return frame.copy()
    return frame[frame["income_group"].isin(groups)].copy()


def sample_composition(
    analytic_panel: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    """Produce every sample-size claim consumed by the reports."""
    rows = []
    for sample in config["samples"]:
        frame = filter_sample(analytic_panel, sample)
        counts = frame.groupby("country", sort=True).size()
        if frame.empty:
            row = {
                "sample_id": sample["id"],
                "n_observations": 0,
                "n_countries": 0,
                "n_observed_years": 0,
                "first_year": pd.NA,
                "last_year": pd.NA,
                "mean_observations_per_country": pd.NA,
                "min_observations_per_country": pd.NA,
                "max_observations_per_country": pd.NA,
            }
        else:
            row = {
                "sample_id": sample["id"],
                "n_observations": len(frame),
                "n_countries": frame["country"].nunique(),
                "n_observed_years": frame["year"].nunique(),
                "first_year": int(frame["year"].min()),
                "last_year": int(frame["year"].max()),
                "mean_observations_per_country": counts.mean(),
                "min_observations_per_country": int(counts.min()),
                "max_observations_per_country": int(counts.max()),
            }
        rows.append(row)
    return pd.DataFrame(rows)


def sample_flow(
    eligible_panel: pd.DataFrame,
    retained_panel: pd.DataFrame,
    analytic_panel: pd.DataFrame,
) -> pd.DataFrame:
    stages = [
        ("eligible_universe", "Eligible country-year grid", eligible_panel),
        ("retained_country_panel", "Countries meeting coverage rule", retained_panel),
        ("analytic_sample", "Complete cases used for estimation", analytic_panel),
    ]
    rows = []
    previous_rows = previous_countries = None
    for stage_id, description, frame in stages:
        n_rows = len(frame)
        n_countries = frame["country"].nunique()
        rows.append(
            {
                "stage_id": stage_id,
                "description": description,
                "n_rows": n_rows,
                "n_countries": n_countries,
                "rows_removed_from_previous": (
                    0 if previous_rows is None else previous_rows - n_rows
                ),
                "countries_removed_from_previous": (
                    0 if previous_countries is None else previous_countries - n_countries
                ),
            }
        )
        previous_rows, previous_countries = n_rows, n_countries
    return pd.DataFrame(rows)


def missingness_by_variable(
    scopes: dict[str, pd.DataFrame], required_variables: list[str]
) -> pd.DataFrame:
    rows = []
    for scope, frame in scopes.items():
        expected_rows = len(frame)
        missing = frame[required_variables].isna()
        for variable in required_variables:
            missing_count = int(missing[variable].sum())
            other_variables = [name for name in required_variables if name != variable]
            unique_count = int(
                (missing[variable] & ~missing[other_variables].any(axis=1)).sum()
            )
            rows.append(
                {
                    "scope": scope,
                    "variable": variable,
                    "expected_rows": expected_rows,
                    "observed_rows": expected_rows - missing_count,
                    "missing_count": missing_count,
                    "missing_percentage": (
                        100.0 * missing_count / expected_rows if expected_rows else 0.0
                    ),
                    "uniquely_excluded_rows": unique_count,
                }
            )
    return pd.DataFrame(rows)


def missingness_patterns(
    scopes: dict[str, pd.DataFrame], required_variables: list[str]
) -> pd.DataFrame:
    """Count overlapping combinations rather than over-reading marginal totals."""
    rows = []
    for scope, frame in scopes.items():
        if frame.empty:
            continue
        pattern = frame[required_variables].isna().apply(
            lambda row: ";".join(
                variable for variable in required_variables if bool(row[variable])
            )
            or "<none>",
            axis=1,
        )
        working = frame.loc[:, ["country"]].assign(missing_variables=pattern)
        grouped = (
            working.groupby("missing_variables", sort=True)
            .agg(n_country_years=("country", "size"), n_countries=("country", "nunique"))
            .reset_index()
        )
        grouped.insert(0, "scope", scope)
        grouped["percentage"] = 100.0 * grouped["n_country_years"] / len(frame)
        rows.append(grouped)
    if not rows:
        return pd.DataFrame(
            columns=[
                "scope",
                "missing_variables",
                "n_country_years",
                "n_countries",
                "percentage",
            ]
        )
    return pd.concat(rows, ignore_index=True).loc[
        :, ["scope", "missing_variables", "n_country_years", "percentage", "n_countries"]
    ]
