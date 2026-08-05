import pandas as pd
import pytest

from environmental_growth.panel import validate_unique_country_year


def test_duplicate_country_year_rows_are_rejected():
    frame = pd.DataFrame(
        {"country": ["AAA", "AAA"], "year": [2000, 2000], "value": [1, 2]}
    )
    with pytest.raises(ValueError, match="duplicate country-year"):
        validate_unique_country_year(frame, "fixture")
