
# Environmental Growth Analysis

A panel data analysis investigating the relationship between economic growth and CO2 emissions, testing the Environmental Kuznets Curve (EKC) hypothesis.

## Overview
This project performs a longitudinal study (1990-2020) of 40 countries, stratified into High Income and Low-Middle Income groups. It uses Fixed Effects regression to determine if environmental damage is an unavoidable cost of prosperity or if wealth eventually funds its own cleanup.

## Hypotheses
1. **EKC Hypothesis**: The relationship between GDP per capita and CO2 emissions is non-linear (inverted U-shape).
2. **Divergence of Drivers**: High-income countries have decoupled growth from emissions more effectively than developing nations.

## Methodology
- **Data Sources**: 
  - World Bank API (GDP, Rule of Law, Tertiary Education)
  - Our World in Data (CO2 Emissions)
- **Model**: Fixed Effects (Entity Effects) Quadratic Regression, standard errors clustered by country.
- **Implementation**: Python (pandas, linearmodels, requests)

## Sample Composition
After listwise deletion on the four regressors, the analytic sample is an unbalanced panel covering 1996-2020 (30-year target window, but CO2 coverage starts 1996 in the merged data):

- **Full sample**: 538 observations, 35 countries, avg 15.4 obs/country, min 3.
- **High Income**: 222 observations, 16 countries, avg 13.9 obs/country, min 3.
- **Low-Middle Income**: 316 observations, 19 countries, avg 16.6 obs/country, min 7.

Missingness is driven primarily by `Rule_of_Law` (WGI) and `Education_Tertiary` coverage. The HIC subsample is notably thin — several high-income countries contribute only a handful of annual observations.

## Findings
Results differ sharply across income groups; **the EKC is not a single story**.

- **Full sample: null.** With SEs clustered by country, neither the linear nor quadratic GDP term is distinguishable from zero (GDP_k p=0.97; GDP_sq p=0.95). Pooling HIC and LMIC obscures the heterogeneity documented below.
- **High Income: inconclusive.** Coefficients have the sign pattern expected of an EKC past its turning point (negative linear, positive quadratic), but neither term clears conventional significance (GDP_k p=0.07; GDP_sq p=0.06). With only 222 observations across 16 entities — averaging 13.9 obs/entity and as few as 3 for some countries — the subsample lacks the within-country variation needed to identify a quadratic shape. The result here is best read as *uninformative*, not as evidence against the EKC.
- **Low-Middle Income: EKC supported.** Both GDP terms are significant with the expected inverted-U pattern (GDP_k β=0.77, p=0.002; GDP_sq β=-0.022, p=0.047). The implied turning point, computed by the delta method, is **GDP per capita ≈ $17,465 (95% CI: $10,287 – $24,642)**. The within-country R² of 0.69 indicates the model captures most of the year-to-year variation in LMIC emissions once country fixed effects are absorbed. The quadratic term is marginal under clustering (p=0.047), so the turning point estimate should be read as directional evidence rather than a precise dollar figure.

## Limitations
Several caveats qualify the conclusions above. **Missingness is non-random**: `Rule_of_Law` and `Education_Tertiary` coverage is patchier for smaller and poorer countries, so the analytic sample under-represents exactly the entities where early-stage EKC dynamics should be most visible — the LMIC estimates are conditional on the countries that report WGI and UNESCO data consistently. **Country selection is not random either**: the HIC/LMIC lists are the first 20 country IDs returned by the World Bank API in each income tier, which likely correlates with country size, reporting capacity, and alphabetic ordering; stable-unit-treatment (SUTVA-style) assumptions about a representative panel should not be made from this sample, and results may not generalize to excluded countries. **The positive sign on tertiary education** in the full sample (β=0.030) is counterintuitive and likely reflects omitted-variable bias: education correlates with urbanization and industrial-maturity transitions that are themselves emission-intensive and are not separately controlled for. Under clustered SEs this coefficient is no longer statistically significant (p=0.18), so the point estimate should not be over-interpreted, but the sign warrants the caveat. Remedies worth exploring in follow-up work include adding urbanization and industrial-share controls, instrumenting GDP to address simultaneity between growth and emissions, and broadening the panel to reduce the dependence on API-ordering.

## Project Structure
- `src/data_loader.py`: Fetches and merges data from World Bank and OWID.
- `src/analysis.py`: Runs the econometric models and generates plots.
- `main.py`: Orchestrates the full workflow.
- `environmental_data.csv`: The processed dataset.
- `regression_results.txt`: Detailed statistical outputs.

## Usage
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the analysis:
   ```bash
   python main.py
   ```
3. View results in `regression_results.txt` and `ekc_plot.png`.
