from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pandas as pd

from environmental_growth.estimands import delta_turning_point


class FakeResult:
    def __init__(self, linear, quadratic, covariance, quadratic_interval, support=(1, 3)):
        self.params = pd.Series({"GDP_k": linear, "GDP_sq": quadratic})
        self.cov = pd.DataFrame(
            covariance,
            index=["GDP_k", "GDP_sq"],
            columns=["GDP_k", "GDP_sq"],
        )
        self._quadratic_interval = quadratic_interval
        exog = pd.DataFrame({"GDP_k": list(support), "GDP_sq": np.square(support)})
        self.model = SimpleNamespace(exog=SimpleNamespace(dataframe=exog))

    def conf_int(self, level):
        return pd.DataFrame(
            {"lower": [-10.0, self._quadratic_interval[0]], "upper": [10.0, self._quadratic_interval[1]]},
            index=["GDP_k", "GDP_sq"],
        )


def test_delta_method_matches_manual_covariance_calculation():
    result = FakeResult(4.0, -1.0, [[0.04, 0.01], [0.01, 0.09]], (-1.5, -0.5))
    turning = delta_turning_point(result)
    assert turning.estimate_usd == 2000
    assert np.isclose(turning.delta_standard_error_usd, np.sqrt(0.39) * 1000)
    assert turning.identification_status == "finite_turning_point_identified"


def test_quadratic_interval_crossing_zero_triggers_nonidentification():
    result = FakeResult(4.0, -1.0, [[0.04, 0.0], [0.0, 0.25]], (-2.0, 0.1))
    turning = delta_turning_point(result)
    assert turning.quadratic_ci_contains_zero
    assert turning.identification_status == "finite_turning_point_not_identified"


def test_turning_point_outside_observed_support_is_flagged():
    result = FakeResult(10.0, -1.0, [[0.04, 0.0], [0.0, 0.01]], (-1.2, -0.8))
    turning = delta_turning_point(result)
    assert turning.estimate_usd == 5000
    assert turning.within_observed_gdp_support is False
    assert turning.identification_status == "turning_point_outside_observed_support"
