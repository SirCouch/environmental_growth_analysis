from io import BytesIO
from zipfile import ZipFile

import pandas as pd
import requests


START_YEAR = 1990
END_YEAR = 2020
MIN_COMPLETE_YEARS = 15

INDICATORS = {
    "NY.GDP.PCAP.KD": "GDP_per_capita",
    "SE.TER.ENRR": "Education_Tertiary",
    "RL.EST": "Rule_of_Law",
}
MODEL_COLUMNS = [
    "GDP_per_capita",
    "CO2_per_capita",
    "Education_Tertiary",
    "Rule_of_Law",
]
INCOME_GROUPS = {
    "HIC": "High Income",
    "LIC": "Low and Middle Income",
    "LMC": "Low and Middle Income",
    "UMC": "Low and Middle Income",
}


def get_eligible_countries():
    """Return every non-aggregate economy in a modeled income group."""
    print("Fetching country list...")
    url = "https://api.worldbank.org/v2/country?format=json&per_page=400"
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    payload = response.json()
    if len(payload) < 2 or payload[1] is None:
        raise RuntimeError("World Bank country metadata response was empty.")

    countries = []
    for country in payload[1]:
        income_code = country["incomeLevel"]["id"]
        if country["region"]["value"] == "Aggregates" or income_code not in INCOME_GROUPS:
            continue
        countries.append(
            {
                "country": country["id"],
                "country_name": country["name"],
                "income_level_code": income_code,
                "Income_Group": INCOME_GROUPS[income_code],
            }
        )

    country_frame = (
        pd.DataFrame(countries).sort_values("country").reset_index(drop=True)
    )
    counts = country_frame.groupby("Income_Group")["country"].nunique()
    print(
        f"Found {len(country_frame)} eligible economies before applying coverage: "
        f"{counts.to_dict()}"
    )
    return country_frame


def fetch_indicator(country_codes, indicator):
    """Download one World Bank indicator in bulk and reshape it to long form."""
    url = f"https://api.worldbank.org/v2/en/indicator/{indicator}?downloadformat=csv"
    print(f"Downloading bulk data for {indicator}...")
    response = requests.get(url, timeout=180)
    response.raise_for_status()
    with ZipFile(BytesIO(response.content)) as archive:
        data_files = [
            name
            for name in archive.namelist()
            if name.startswith("API_") and name.endswith(".csv")
        ]
        if len(data_files) != 1:
            raise RuntimeError(f"Could not identify the data CSV for {indicator}.")
        wide = pd.read_csv(archive.open(data_files[0]), skiprows=4, low_memory=False)

    year_columns = [str(year) for year in range(START_YEAR, END_YEAR + 1)]
    long = wide.melt(
        id_vars=["Country Code"],
        value_vars=year_columns,
        var_name="year",
        value_name=indicator,
    )
    long = long.rename(columns={"Country Code": "country"})
    long = long[long["country"].isin(country_codes)].copy()
    long[indicator] = pd.to_numeric(long[indicator], errors="coerce")
    long = long.dropna(subset=[indicator])
    long["year"] = long["year"].astype(int)
    return long


def build_coverage_audit(panel, countries):
    """Apply the declared complete-case rule and record every decision."""
    complete_rows = panel[MODEL_COLUMNS].notna().all(axis=1)
    coverage = (
        panel.loc[complete_rows]
        .groupby("country")
        .agg(
            complete_years=("year", "nunique"),
            first_complete_year=("year", "min"),
            last_complete_year=("year", "max"),
        )
        .reset_index()
    )
    audit = countries.merge(coverage, on="country", how="left")
    audit["complete_years"] = audit["complete_years"].fillna(0).astype(int)
    audit["included"] = audit["complete_years"] >= MIN_COMPLETE_YEARS
    audit["coverage_rule"] = (
        f"at least {MIN_COMPLETE_YEARS} complete years, {START_YEAR}-{END_YEAR}"
    )
    audit.to_csv("sample_coverage.csv", index=False)
    return audit


def process_data():
    countries = get_eligible_countries()
    country_codes = countries["country"].tolist()

    merged = None
    for indicator_code, indicator_name in INDICATORS.items():
        indicator_data = fetch_indicator(country_codes, indicator_code)
        if indicator_data.empty:
            raise RuntimeError(f"No data returned for required indicator {indicator_name}.")
        indicator_data = indicator_data.rename(columns={indicator_code: indicator_name})
        if merged is None:
            merged = indicator_data
        else:
            merged = pd.merge(merged, indicator_data, on=["country", "year"], how="outer")

    print("Fetching CO2 data from Our World in Data...")
    owid_url = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"
    co2 = pd.read_csv(owid_url, usecols=["iso_code", "year", "co2_per_capita"])
    co2 = co2.rename(columns={"iso_code": "country", "co2_per_capita": "CO2_per_capita"})
    co2 = co2[
        co2["country"].isin(country_codes)
        & co2["year"].between(START_YEAR, END_YEAR)
    ]
    merged = pd.merge(merged, co2, on=["country", "year"], how="left")
    merged = merged.merge(
        countries[["country", "income_level_code", "Income_Group"]],
        on="country",
        how="inner",
    )

    audit = build_coverage_audit(merged, countries)
    included_countries = audit.loc[audit["included"], "country"]
    filtered = merged[merged["country"].isin(included_countries)].copy()
    filtered = filtered.sort_values(["country", "year"]).reset_index(drop=True)

    included_counts = (
        audit.loc[audit["included"]]
        .groupby("Income_Group")["country"]
        .nunique()
    )
    print(
        f"Coverage rule retained {len(included_countries)} countries: "
        f"{included_counts.to_dict()}"
    )
    if filtered.empty:
        raise RuntimeError("No countries met the declared coverage rule.")
    return filtered


if __name__ == "__main__":
    data = process_data()
    print(data.head())
    data.info()
    data.to_csv("environmental_data.csv", index=False)
