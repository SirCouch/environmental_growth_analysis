"""Declared PanelOLS specifications and structured result extraction."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

import pandas as pd
import statsmodels.api as sm
from linearmodels.panel import PanelOLS

from .diagnostics import filter_sample


@dataclass
class ModelFit:
    sample_id: str
    sample_label: str
    model_id: str
    model_label: str
    entity_effects: bool
    year_effects: bool
    covariance_type: str
    sample: pd.DataFrame
    result: Any


def fit_model(
    frame: pd.DataFrame,
    dependent_variable: str,
    regressors: list[str],
    entity_effects: bool,
    year_effects: bool,
    covariance_type: str,
) -> Any:
    """Fit one fixed-effects model exactly as declared in configuration."""
    if covariance_type != "clustered_entity":
        raise ValueError(f"Unsupported covariance type: {covariance_type}")
    indexed = frame.set_index(["country", "year"]).sort_index()
    exogenous = sm.add_constant(indexed[regressors], has_constant="add")
    model = PanelOLS(
        indexed[dependent_variable],
        exogenous,
        entity_effects=entity_effects,
        time_effects=year_effects,
    )
    return model.fit(cov_type="clustered", cluster_entity=True)


def fit_declared_models(
    analytic_panel: pd.DataFrame, config: dict[str, Any]
) -> dict[tuple[str, str], ModelFit]:
    model_config = config["model"]
    fits: dict[tuple[str, str], ModelFit] = {}
    for sample_config in config["samples"]:
        sample = filter_sample(analytic_panel, sample_config)
        if sample.empty:
            raise RuntimeError(f"Declared sample {sample_config['id']} is empty")
        for specification in model_config["specifications"]:
            result = fit_model(
                sample,
                model_config["dependent_variable"],
                model_config["regressors"],
                bool(specification["entity_effects"]),
                bool(specification["year_effects"]),
                model_config["covariance_type"],
            )
            fit = ModelFit(
                sample_id=sample_config["id"],
                sample_label=sample_config["label"],
                model_id=specification["id"],
                model_label=specification["label"],
                entity_effects=bool(specification["entity_effects"]),
                year_effects=bool(specification["year_effects"]),
                covariance_type=model_config["covariance_type"],
                sample=sample,
                result=result,
            )
            fits[(fit.sample_id, fit.model_id)] = fit
    return fits


def coefficients_table(
    fits: dict[tuple[str, str], ModelFit], confidence_level: float
) -> pd.DataFrame:
    rows = []
    for key in sorted(fits):
        fit = fits[key]
        result = fit.result
        intervals = result.conf_int(level=confidence_level)
        for term in result.params.index:
            rows.append(
                {
                    "sample_id": fit.sample_id,
                    "model_id": fit.model_id,
                    "term": term,
                    "estimate": float(result.params[term]),
                    "std_error": float(result.std_errors[term]),
                    "statistic": float(result.tstats[term]),
                    "p_value": float(result.pvalues[term]),
                    "ci_lower": float(intervals.loc[term].iloc[0]),
                    "ci_upper": float(intervals.loc[term].iloc[1]),
                    "n_observations": int(result.nobs),
                    "n_countries": int(fit.sample["country"].nunique()),
                    "entity_effects": fit.entity_effects,
                    "year_effects": fit.year_effects,
                    "covariance_type": fit.covariance_type,
                }
            )
    return pd.DataFrame(rows)


def _statistic_value(statistic: Any, attribute: str) -> float | None:
    value = getattr(statistic, attribute, None)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def model_diagnostics_table(
    fits: dict[tuple[str, str], ModelFit], config: dict[str, Any]
) -> pd.DataFrame:
    preferred = config["model"]["preferred_model_id"]
    regressors = ";".join(config["model"]["regressors"])
    rows = []
    for key in sorted(fits):
        fit = fits[key]
        result = fit.result
        years = fit.sample["year"]
        robust_f = getattr(result, "f_statistic_robust", None)
        rows.append(
            {
                "sample_id": fit.sample_id,
                "model_id": fit.model_id,
                "dependent_variable": config["model"]["dependent_variable"],
                "regressors": regressors,
                "n_observations": int(result.nobs),
                "n_countries": int(fit.sample["country"].nunique()),
                "n_observed_years": int(years.nunique()),
                "first_year": int(years.min()),
                "last_year": int(years.max()),
                "r_squared": float(result.rsquared),
                "r_squared_within": float(result.rsquared_within),
                "r_squared_between": float(result.rsquared_between),
                "r_squared_overall": float(result.rsquared_overall),
                "robust_f_statistic": _statistic_value(robust_f, "stat"),
                "robust_f_p_value": _statistic_value(robust_f, "pval"),
                "log_likelihood": float(result.loglik),
                "df_model": int(result.df_model),
                "df_resid": int(result.df_resid),
                "entity_effects": fit.entity_effects,
                "year_effects": fit.year_effects,
                "covariance_type": fit.covariance_type,
                "preferred_specification": fit.model_id == preferred,
            }
        )
    return pd.DataFrame(rows)


def deterministic_model_summaries(
    fits: dict[tuple[str, str], ModelFit]
) -> str:
    """Keep PanelOLS text as a convenience artifact without clock-time churn."""
    sections = []
    for key in sorted(fits):
        fit = fits[key]
        summary = str(fit.result)
        summary = re.sub(
            r"Date:\s+\w{3},\s+\w{3}\s+\d{1,2}\s+\d{4}",
            "Date:                <reproduced>",
            summary,
        )
        summary = re.sub(
            r"Time:\s+\d{1,2}:\d{2}:\d{2}",
            "Time:                        <reproduced>",
            summary,
        )
        summary = "\n".join(line.rstrip() for line in summary.splitlines())
        sections.append(
            f"{fit.sample_label} | {fit.model_label}\n{'=' * 79}\n{summary.rstrip()}"
        )
    return "\n\n".join(sections) + "\n"
