<!-- GENERATED FILE: edit reports/README.template.md, then run `make report`. -->
<!-- run-id: 3962cd88a1c8c051 -->

# Environmental Growth Analysis

This study tests the Environmental Kuznets Curve (EKC) hypothesis with a country-year panel of GDP per capita, CO2 emissions, tertiary enrollment, and rule of law. It compares high-income economies with a combined low- and middle-income sample.

The analysis is designed so that source refresh and reproduction are separate operations. Run `make refresh-data` only when intentionally contacting live providers; `make reproduce`, `make report`, and `make verify` consume snapshot `snapshot-f8168d697265` without network access.

## Sample selection

Retain eligible countries with at least 15 complete years from 1990–2020 across `GDP_per_capita`, `CO2_per_capita`, `Education_Tertiary`, `Rule_of_Law`.

The 15-year minimum is fixed before estimation to require a sustained within-country trajectory. It is not tuned to coefficient significance. Present-day World Bank income classification is retained during this reproducibility refactor so that classification changes are not conflated with pipeline changes; historical or baseline-year classification belongs in a separately named sensitivity analysis.

| sample_id         | n_observations   | n_countries   | n_observed_years   | first_year   | last_year   | mean_observations_per_country   | min_observations_per_country   | max_observations_per_country   |
|:------------------|:-----------------|:--------------|:-------------------|:-------------|:------------|:--------------------------------|:-------------------------------|:-------------------------------|
| full_sample       | 2009             | 104           | 22                 | 1996         | 2020        | 19.3173                         | 15                             | 22                             |
| high_income       | 784              | 41            | 22                 | 1996         | 2020        | 19.122                          | 15                             | 22                             |
| low_middle_income | 1225             | 63            | 22                 | 1996         | 2020        | 19.4444                         | 15                             | 22                             |

## Methodology

The dependent variable is `CO2_per_capita`. Regressors are GDP per capita in thousands of constant 2015 US dollars (`GDP_k`), its square (`GDP_sq`), `Rule_of_Law`, and `Education_Tertiary`.

Each sample has a country fixed-effects reference model and a preferred country-plus-year fixed-effects model. Standard errors are clustered by country. Year effects absorb common annual shocks and global trends; neither specification eliminates simultaneity or omitted time-varying confounding, so results remain associational rather than causal.

## Preferred-model results

| sample_id         | term               | estimate    | std_error   | p_value    | ci_lower    | ci_upper    |
|:------------------|:-------------------|:------------|:------------|:-----------|:------------|:------------|
| full_sample       | const              | 3.09342     | 1.10032     | 0.00498402 | 0.935445    | 5.25139     |
| full_sample       | GDP_k              | 0.145409    | 0.105629    | 0.168801   | -0.0617539  | 0.352571    |
| full_sample       | GDP_sq             | -0.00194837 | 0.00113826  | 0.0871142  | -0.00418075 | 0.000284009 |
| full_sample       | Rule_of_Law        | -0.0131392  | 0.0425371   | 0.757441   | -0.096564   | 0.0702856   |
| full_sample       | Education_Tertiary | 0.0230476   | 0.0138641   | 0.0966008  | -0.00414307 | 0.0502383   |
| high_income       | const              | 3.52476     | 3.53108     | 0.318514   | -3.40771    | 10.4572     |
| high_income       | GDP_k              | 0.220911    | 0.208296    | 0.289247   | -0.188032   | 0.629853    |
| high_income       | GDP_sq             | -0.00218877 | 0.00173324  | 0.207064   | -0.0055916  | 0.00121405  |
| high_income       | Rule_of_Law        | -0.0295064  | 0.1316      | 0.822656   | -0.287873   | 0.22886     |
| high_income       | Education_Tertiary | 0.0389359   | 0.0275043   | 0.157318   | -0.0150626  | 0.0929344   |
| low_middle_income | const              | -1.04779    | 1.419       | 0.460426   | -3.83194    | 1.73637     |
| low_middle_income | GDP_k              | 1.08444     | 0.494375    | 0.0284691  | 0.114451    | 2.05443     |
| low_middle_income | GDP_sq             | -0.047102   | 0.0292054   | 0.107069   | -0.104405   | 0.0102006   |
| low_middle_income | Rule_of_Law        | -0.0324972  | 0.0264589   | 0.21962    | -0.084411   | 0.0194165   |
| low_middle_income | Education_Tertiary | 0.00890269  | 0.00734733  | 0.225882   | -0.00551314 | 0.0233185   |

Statistical non-significance is treated as limited information, not evidence that an effect is absent.

## Turning point

The coefficient ratio implies $11,512, but the quadratic confidence interval includes zero. The finite turning point is therefore not statistically identified; the delta interval is recorded only as a mechanical diagnostic.

| sample_id         | model_id       | confidence_level   | estimate_usd   | delta_standard_error_usd   | delta_ci_lower_usd   | delta_ci_upper_usd   | linear_estimate   | quadratic_estimate   | quadratic_ci_lower   | quadratic_ci_upper   | quadratic_ci_contains_zero   | inverted_u_signs   | observed_gdp_min_usd   | observed_gdp_max_usd   | within_observed_gdp_support   | identification_status               |
|:------------------|:---------------|:-------------------|:---------------|:---------------------------|:---------------------|:---------------------|:------------------|:---------------------|:---------------------|:---------------------|:-----------------------------|:-------------------|:-----------------------|:-----------------------|:------------------------------|:------------------------------------|
| low_middle_income | entity_year_fe | 0.95               | 11511.6        | 2127.07                    | 7342.65              | 15680.6              | 1.08444           | -0.047102            | -0.104405            | 0.0102006            | True                         | True               | 227.198                | 14040.6                | True                          | finite_turning_point_not_identified |

The turning point is a coefficient ratio. Its delta-method variance uses the full covariance matrix, and the identification guard prevents a finite threshold claim when the quadratic denominator is weakly identified. A Fieller or parametric-bootstrap interval would be a useful sensitivity analysis, but would supplement rather than replace this artifact.

## Limitations

Fixed effects do not resolve reverse causality between growth, institutions, education, and emissions, nor do they absorb omitted confounders that change differently across countries. Cross-country emissions, enrollment, governance, and national-accounts measures also contain error and may not be comparable across reporting systems or over time. Complete-case and coverage selection favor economies with stronger reporting systems, while retrospective use of a current income classification can misclassify countries' earlier development status. These constraints limit causal and population-wide interpretation.

## Missingness

Marginal missingness counts do not establish which variable “drives” complete-case loss because missing values overlap. The pipeline therefore emits both variable-level counts and joint missingness patterns. These facts can support a discussion of reporting-system selection, but do not by themselves establish its cause.

| scope                  | variable           | expected_rows   | observed_rows   | missing_count   | missing_percentage   | uniquely_excluded_rows   |
|:-----------------------|:-------------------|:----------------|:----------------|:----------------|:---------------------|:-------------------------|
| retained_country_panel | GDP_per_capita     | 3224            | 3208            | 16              | 0.496278             | 0                        |
| retained_country_panel | CO2_per_capita     | 3224            | 3223            | 1               | 0.0310174            | 0                        |
| retained_country_panel | Education_Tertiary | 3224            | 2462            | 762             | 23.6352              | 278                      |
| retained_country_panel | Rule_of_Law        | 3224            | 2287            | 937             | 29.0633              | 453                      |

## Figure

![Environmental Kuznets Curve](artifacts/current/figures/ekc_plot.png)

## Reproduction

```bash
uv sync --all-extras
make reproduce
make report
make verify
```

On systems without Make, invoke the matching commands directly with `uv run environmental-growth <command>`.

`make verify` regenerates the run in a temporary directory and checks committed outputs, generated README content, required files, and manifest hashes. CI verifies locked inputs; it does not contact live APIs.

## Artifact index

Run ID: `3962cd88a1c8c051`

- [Run manifest](artifacts/current/run_manifest.json)
- [Country universe](artifacts/current/country_universe.csv)
- [Coverage audit](artifacts/current/country_coverage.csv)
- [Sample flow](artifacts/current/sample_flow.csv)
- [Coefficients](artifacts/current/coefficients.csv)
- [Model diagnostics](artifacts/current/model_diagnostics.csv)
- [Turning points](artifacts/current/turning_points.csv)
- [Missingness by variable](artifacts/current/missingness_by_variable.csv)
- [Missingness patterns](artifacts/current/missingness_patterns.csv)
- [Complete results report](artifacts/current/results_report.md)
