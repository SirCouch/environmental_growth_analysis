from __future__ import annotations

import pandas as pd

from environmental_growth.selection import apply_coverage_rule, build_country_universe


def _metadata():
    return pd.DataFrame(
        [
            {
                "country": "AAA",
                "country_name": "Alpha",
                "income_level_code": "HIC",
                "income_level_name": "High income",
                "region_code": "R1",
                "region_name": "Region",
                "is_aggregate": False,
            },
            {
                "country": "BBB",
                "country_name": "Beta",
                "income_level_code": "LMC",
                "income_level_name": "Lower middle income",
                "region_code": "R1",
                "region_name": "Region",
                "is_aggregate": False,
            },
            {
                "country": "AGG",
                "country_name": "Aggregate",
                "income_level_code": "HIC",
                "income_level_name": "High income",
                "region_code": "NA",
                "region_name": "Aggregates",
                "is_aggregate": True,
            },
            {
                "country": "UNK",
                "country_name": "Unclassified",
                "income_level_code": "INX",
                "income_level_name": "Not classified",
                "region_code": "R1",
                "region_name": "Region",
                "is_aggregate": False,
            },
        ]
    )


def test_aggregates_and_unsupported_income_codes_are_excluded(analysis_config):
    universe = build_country_universe(_metadata(), analysis_config, "2026-08-05")
    reasons = universe.set_index("country")["eligibility_reason"].to_dict()
    assert reasons == {
        "AAA": "eligible",
        "AGG": "aggregate",
        "BBB": "eligible",
        "UNK": "unsupported_income_code",
    }


def test_coverage_boundary_excludes_14_and_includes_15_years(analysis_config):
    universe = build_country_universe(_metadata(), analysis_config, "2026-08-05")
    rows = []
    for country, years in (("AAA", 14), ("BBB", 15)):
        for offset in range(years):
            rows.append(
                {
                    "country": country,
                    "year": 1990 + offset,
                    "GDP_per_capita": 1000 + offset,
                    "CO2_per_capita": 1 + offset,
                    "Education_Tertiary": 10 + offset,
                    "Rule_of_Law": 0.1 + offset,
                }
            )
    panel = pd.DataFrame(rows)
    audit, retained = apply_coverage_rule(panel, universe, analysis_config)
    decisions = audit.set_index("country")["included"].to_dict()
    assert decisions == {"AAA": False, "BBB": True}
    assert retained["country"].unique().tolist() == ["BBB"]
