<!-- GENERATED FILE: edit reports/README.template.md, then run `make report`. -->
<!-- run-id: {{RUN_ID}} -->

# Environmental Growth Analysis

This study tests the Environmental Kuznets Curve (EKC) hypothesis with a country-year panel of GDP per capita, CO2 emissions, tertiary enrollment, and rule of law. It compares high-income economies with a combined low- and middle-income sample.

The analysis is designed so that source refresh and reproduction are separate operations. Run `make refresh-data` only when intentionally contacting live providers; `make reproduce`, `make report`, and `make verify` consume snapshot `{{SNAPSHOT_ID}}` without network access.

## Sample selection

{{COVERAGE_RULE}}

The 15-year minimum is fixed before estimation to require a sustained within-country trajectory. It is not tuned to coefficient significance. Present-day World Bank income classification is retained during this reproducibility refactor so that classification changes are not conflated with pipeline changes; historical or baseline-year classification belongs in a separately named sensitivity analysis.

{{SAMPLE_COMPOSITION_TABLE}}

## Methodology

The dependent variable is `CO2_per_capita`. Regressors are GDP per capita in thousands of constant 2015 US dollars (`GDP_k`), its square (`GDP_sq`), `Rule_of_Law`, and `Education_Tertiary`.

Each sample has a country fixed-effects reference model and a preferred country-plus-year fixed-effects model. Standard errors are clustered by country. Year effects absorb common annual shocks and global trends; neither specification eliminates simultaneity or omitted time-varying confounding, so results remain associational rather than causal.

## Preferred-model results

{{PREFERRED_COEFFICIENTS_TABLE}}

Statistical non-significance is treated as limited information, not evidence that an effect is absent.

## Turning point

{{TURNING_POINT_NARRATIVE}}

{{TURNING_POINT_TABLE}}

The turning point is a coefficient ratio. Its delta-method variance uses the full covariance matrix, and the identification guard prevents a finite threshold claim when the quadratic denominator is weakly identified. A Fieller or parametric-bootstrap interval would be a useful sensitivity analysis, but would supplement rather than replace this artifact.

## Limitations

Fixed effects do not resolve reverse causality between growth, institutions, education, and emissions, nor do they absorb omitted confounders that change differently across countries. Cross-country emissions, enrollment, governance, and national-accounts measures also contain error and may not be comparable across reporting systems or over time. Complete-case and coverage selection favor economies with stronger reporting systems, while retrospective use of a current income classification can misclassify countries' earlier development status. These constraints limit causal and population-wide interpretation.

## Missingness

Marginal missingness counts do not establish which variable “drives” complete-case loss because missing values overlap. The pipeline therefore emits both variable-level counts and joint missingness patterns. These facts can support a discussion of reporting-system selection, but do not by themselves establish its cause.

{{MISSINGNESS_TABLE}}

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

Run ID: `{{RUN_ID}}`

{{ARTIFACT_LINKS}}
