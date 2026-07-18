# Environmental Growth Analysis

This project tests the Environmental Kuznets Curve (EKC) hypothesis with a country-year panel of GDP per capita, CO2 emissions, tertiary enrollment, and rule of law. It compares high-income economies with the combined low- and middle-income group.

## Sample Selection

Country inclusion follows a declared coverage rule rather than World Bank API order:

1. Start with every non-aggregate economy classified by the World Bank as HIC, LIC, LMC, or UMC.
2. Fetch all four model variables for 1990-2020.
3. Count years in which every model variable is observed.
4. Retain countries with at least 15 complete years; apply no fixed country cap.

The 15-year minimum is fixed before estimation to require a sustained within-country trajectory; it is not tuned to coefficient significance.

`sample_coverage.csv` records the income code, complete-year count, observed range, and inclusion decision for all 217 eligible economies. The current extract retains 104 countries: 41 high income and 63 low/middle income. The analytic sample contains 2,009 complete observations over 1996-2020 (22 observed years):

- **Full sample:** 2,009 observations, 104 countries, 15-22 observations per country.
- **High income:** 784 observations, 41 countries, average 19.1 per country.
- **Low and middle income:** 1,225 observations, 63 countries, average 19.4 per country.

## Methodology

The dependent variable is `CO2_per_capita`. Regressors are GDP per capita in thousands of constant 2015 US dollars (`GDP_k`), its square (`GDP_sq`), `Rule_of_Law`, and `Education_Tertiary`.

For each sample, the analysis reports two matched specifications with standard errors clustered by country:

- Country fixed effects only, retained as a reference specification.
- Country and year fixed effects, the preferred specification, which absorbs common annual shocks and global trends.

## Findings

The expanded, coverage-selected sample does **not** provide conventional 5% evidence of an EKC.

- **Full sample, preferred model:** `GDP_k` is positive (beta=0.145, p=0.169) and `GDP_sq` is negative (beta=-0.0019, p=0.087); neither clears 5% significance.
- **High income, preferred model:** neither GDP term is significant (`GDP_k` p=0.289; `GDP_sq` p=0.207).
- **Low and middle income, preferred model:** the linear term is positive (beta=1.084, p=0.029), but the negative quadratic term is not significant (beta=-0.047, p=0.107). The signs imply a descriptive turning point near $11,512, but the curvature interval includes zero, so a finite threshold is not statistically identified.

The entity-only results lead to the same substantive conclusion: the low/middle-income quadratic term remains above 5% significance (p=0.091).

## Limitations

The coverage rule removes API-order arbitrariness but selects for countries with stronger reporting systems. Income groups use the classification returned by the World Bank at refresh time rather than time-varying historical classifications. Complete-case deletion remains substantial, chiefly because governance and tertiary enrollment are sparsely reported. Fixed effects address time-invariant country differences and common year shocks, but not simultaneity or omitted time-varying confounders; results are associational, not causal.

## Project Structure

- `src/data_loader.py`: downloads official source data, applies the coverage rule, and writes the panel and audit.
- `src/analysis.py`: estimates both fixed-effects specifications and generates the results and plot.
- `main.py`: runs acquisition only when the panel is absent, then runs analysis.
- `environmental_data.csv`: retained-country panel.
- `sample_coverage.csv`: country inclusion audit.
- `regression_results.txt` and `ekc_plot.png`: generated analysis outputs.

## Usage

```bash
pip install -r requirements.txt
python src/data_loader.py  # refresh data and coverage audit
python src/analysis.py     # rerun models and plot
python main.py             # use cached data when available
```
