from __future__ import annotations

import pandas as pd

from environmental_growth.diagnostics import (
    missingness_by_variable,
    missingness_patterns,
    sample_composition,
)


def _toy_panel():
    return pd.DataFrame(
        {
            "country": ["AAA", "AAA", "BBB", "BBB"],
            "year": [2000, 2001, 2000, 2002],
            "income_group": ["High Income"] * 2 + ["Low and Middle Income"] * 2,
            "GDP_per_capita": [1.0, 2.0, 3.0, 4.0],
            "CO2_per_capita": [1.0, None, 2.0, None],
            "Education_Tertiary": [None, None, 3.0, 4.0],
            "Rule_of_Law": [0.1, 0.2, None, 0.4],
        }
    )


def test_sample_statistics_match_toy_panel(analysis_config):
    analysis_config["samples"] = [{"id": "full_sample", "label": "Full sample"}]
    composition = sample_composition(_toy_panel(), analysis_config).iloc[0]
    assert composition["n_observations"] == 4
    assert composition["n_countries"] == 2
    assert composition["n_observed_years"] == 3
    assert composition["mean_observations_per_country"] == 2
    assert composition["min_observations_per_country"] == 2
    assert composition["max_observations_per_country"] == 2


def test_missingness_counts_and_patterns_reconcile():
    panel = _toy_panel()
    variables = [
        "GDP_per_capita",
        "CO2_per_capita",
        "Education_Tertiary",
        "Rule_of_Law",
    ]
    scopes = {"toy": panel}
    by_variable = missingness_by_variable(scopes, variables).set_index("variable")
    assert by_variable.loc["CO2_per_capita", "missing_count"] == 2
    assert by_variable.loc["Education_Tertiary", "missing_count"] == 2
    patterns = missingness_patterns(scopes, variables)
    assert patterns["n_country_years"].sum() == len(panel)
    assert abs(patterns["percentage"].sum() - 100) < 1e-9
