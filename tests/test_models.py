from __future__ import annotations

import pandas as pd

from environmental_growth.models import ModelFit, coefficients_table


class FakeResult:
    params = pd.Series({"const": 1.0, "GDP_k": 2.0})
    std_errors = pd.Series({"const": 0.2, "GDP_k": 0.4})
    tstats = pd.Series({"const": 5.0, "GDP_k": 5.0})
    pvalues = pd.Series({"const": 0.001, "GDP_k": 0.002})
    nobs = 4

    def conf_int(self, level):
        assert level == 0.95
        return pd.DataFrame({"lower": [0.6, 1.2], "upper": [1.4, 2.8]}, index=self.params.index)


def test_coefficient_extraction_from_fixed_fixture():
    sample = pd.DataFrame({"country": ["AAA", "AAA", "BBB", "BBB"]})
    fit = ModelFit(
        sample_id="full_sample",
        sample_label="Full sample",
        model_id="entity_fe",
        model_label="Entity FE",
        entity_effects=True,
        year_effects=False,
        covariance_type="clustered_entity",
        sample=sample,
        result=FakeResult(),
    )
    table = coefficients_table({("full_sample", "entity_fe"): fit}, 0.95)
    gdp = table.set_index("term").loc["GDP_k"]
    assert gdp["estimate"] == 2.0
    assert gdp["ci_lower"] == 1.2
    assert gdp["n_countries"] == 2
    assert bool(gdp["entity_effects"])
    assert not bool(gdp["year_effects"])
