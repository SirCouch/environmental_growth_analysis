"""Turning-point estimands and uncertainty guards."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd
from scipy.stats import norm

from .models import ModelFit


@dataclass(frozen=True)
class TurningPointResult:
    estimate_usd: float
    delta_standard_error_usd: float
    delta_ci_lower_usd: float
    delta_ci_upper_usd: float
    linear_estimate: float
    quadratic_estimate: float
    quadratic_ci_lower: float
    quadratic_ci_upper: float
    quadratic_ci_contains_zero: bool
    inverted_u_signs: bool
    observed_gdp_min_usd: float | None
    observed_gdp_max_usd: float | None
    within_observed_gdp_support: bool | None
    identification_status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _observed_linear_support(result: Any, linear_term: str) -> tuple[float, float] | None:
    try:
        exogenous = result.model.exog.dataframe
        values = pd.to_numeric(exogenous[linear_term], errors="coerce").dropna()
    except (AttributeError, KeyError, TypeError):
        return None
    if values.empty:
        return None
    return float(values.min()), float(values.max())


def delta_turning_point(
    result: Any,
    linear_term: str = "GDP_k",
    quadratic_term: str = "GDP_sq",
    scale: float = 1000,
    alpha: float = 0.05,
) -> TurningPointResult:
    """Estimate -beta1/(2 beta2) and its delta-method uncertainty.

    A finite delta interval is emitted even when the denominator interval crosses
    zero, but the identification status prevents renderers from presenting that
    mechanical interval as an identified threshold.
    """
    if not 0 < alpha < 1:
        raise ValueError("alpha must be strictly between zero and one")
    beta_1 = float(result.params[linear_term])
    beta_2 = float(result.params[quadratic_term])
    covariance = result.cov.loc[
        [linear_term, quadratic_term], [linear_term, quadratic_term]
    ].to_numpy(dtype=float)
    critical = float(norm.ppf(1 - alpha / 2))
    intervals = result.conf_int(level=1 - alpha)
    quadratic_lower = float(intervals.loc[quadratic_term].iloc[0])
    quadratic_upper = float(intervals.loc[quadratic_term].iloc[1])
    quadratic_contains_zero = quadratic_lower <= 0 <= quadratic_upper
    inverted_u = beta_1 > 0 and beta_2 < 0

    if beta_2 == 0:
        estimate = standard_error = lower = upper = float("nan")
    else:
        estimate_unscaled = -beta_1 / (2 * beta_2)
        gradient = np.array(
            [-1 / (2 * beta_2), beta_1 / (2 * beta_2**2)], dtype=float
        )
        variance = float(gradient.T @ covariance @ gradient)
        if variance < 0 and abs(variance) < 1e-12:
            variance = 0.0
        standard_error_unscaled = float(np.sqrt(variance)) if variance >= 0 else float("nan")
        estimate = estimate_unscaled * scale
        standard_error = standard_error_unscaled * scale
        lower = estimate - critical * standard_error
        upper = estimate + critical * standard_error

    support = _observed_linear_support(result, linear_term)
    if support is None:
        support_min = support_max = None
        within_support = None
    else:
        support_min = support[0] * scale
        support_max = support[1] * scale
        within_support = bool(
            isfinite(estimate) and support_min <= estimate <= support_max
        )

    if not isfinite(estimate):
        status = "finite_turning_point_not_identified"
    elif quadratic_contains_zero:
        status = "finite_turning_point_not_identified"
    elif not inverted_u:
        status = "inverted_u_not_supported"
    elif within_support is False:
        status = "turning_point_outside_observed_support"
    elif within_support is None:
        status = "observed_support_unavailable"
    else:
        status = "finite_turning_point_identified"

    return TurningPointResult(
        estimate_usd=estimate,
        delta_standard_error_usd=standard_error,
        delta_ci_lower_usd=lower,
        delta_ci_upper_usd=upper,
        linear_estimate=beta_1,
        quadratic_estimate=beta_2,
        quadratic_ci_lower=quadratic_lower,
        quadratic_ci_upper=quadratic_upper,
        quadratic_ci_contains_zero=quadratic_contains_zero,
        inverted_u_signs=inverted_u,
        observed_gdp_min_usd=support_min,
        observed_gdp_max_usd=support_max,
        within_observed_gdp_support=within_support,
        identification_status=status,
    )


def turning_points_table(
    fits: dict[tuple[str, str], ModelFit], config: dict[str, Any]
) -> pd.DataFrame:
    declared = config["turning_point"]
    key = (declared["sample_id"], declared["model_id"])
    if key not in fits:
        raise KeyError(f"Turning-point model was not fitted: {key}")
    estimate = delta_turning_point(
        fits[key].result,
        linear_term=declared["linear_term"],
        quadratic_term=declared["quadratic_term"],
        scale=float(declared["scale"]),
        alpha=1 - float(config["confidence_level"]),
    )
    row = {
        "sample_id": declared["sample_id"],
        "model_id": declared["model_id"],
        "confidence_level": float(config["confidence_level"]),
        **estimate.to_dict(),
    }
    return pd.DataFrame([row])
