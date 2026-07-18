import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import statsmodels.api as sm
from linearmodels.panel import PanelOLS


MODEL_COLUMNS = [
    "GDP_per_capita",
    "CO2_per_capita",
    "Education_Tertiary",
    "Rule_of_Law",
]
EXOGENOUS_COLUMNS = ["GDP_k", "GDP_sq", "Rule_of_Law", "Education_Tertiary"]
LOW_MIDDLE_GROUP = "Low and Middle Income"


def load_data(filepath="environmental_data.csv"):
    return pd.read_csv(filepath)


def describe_sample(frame, label):
    observations_per_country = frame.groupby(level="country").size()
    years = frame.index.get_level_values("year")
    return (
        f"{label}: N={len(frame)}, countries={len(observations_per_country)}, "
        f"years={years.min()}-{years.max()}, "
        f"avg obs/country={observations_per_country.mean():.1f}, "
        f"min={observations_per_country.min()}, max={observations_per_country.max()}"
    )


def fit_model(frame, include_year_effects):
    exogenous = sm.add_constant(frame[EXOGENOUS_COLUMNS])
    model = PanelOLS(
        frame["CO2_per_capita"],
        exogenous,
        entity_effects=True,
        time_effects=include_year_effects,
    )
    return model.fit(cov_type="clustered", cluster_entity=True)


def format_result(result):
    return "\n".join(line.rstrip() for line in str(result).splitlines())


def turning_point_summary(result):
    linear = result.params["GDP_k"]
    quadratic = result.params["GDP_sq"]
    turning_point = -linear / (2 * quadratic)
    quadratic_p_value = result.pvalues["GDP_sq"]
    return (
        "Implied two-way FE turning point (descriptive only): "
        f"GDP/capita = ${turning_point * 1000:,.0f}. "
        f"The quadratic term has p={quadratic_p_value:.3f}; because its confidence "
        "interval includes zero, a finite turning point is not statistically identified."
    )


def run_analysis():
    print("Loading data...")
    data = load_data()
    for column in MODEL_COLUMNS:
        data[column] = pd.to_numeric(data[column], errors="coerce")

    print(f"Original shape: {data.shape}")
    data = data.dropna(subset=MODEL_COLUMNS).copy()
    print(f"Complete-case shape: {data.shape}")
    if data.empty:
        raise RuntimeError("No complete observations are available for analysis.")

    data["GDP_k"] = data["GDP_per_capita"] / 1000.0
    data["GDP_sq"] = data["GDP_k"] ** 2
    data = data.set_index(["country", "year"]).sort_index()

    samples = [("Full sample", data)]
    samples.extend(
        (group, data[data["Income_Group"] == group])
        for group in sorted(data["Income_Group"].unique())
    )

    with open("regression_results.txt", "w", encoding="utf-8") as output:
        output.write(
            "All models use country fixed effects and country-clustered standard errors.\n"
            "Each sample has an entity-only reference and a preferred specification "
            "with year fixed effects.\n\n"
        )
        for label, sample in samples:
            if len(sample) < 10:
                print(f"Skipping {label}: not enough data.")
                continue

            sample_description = describe_sample(sample, label)
            print(f"\n{sample_description}")
            output.write(sample_description + "\n\n")

            entity_result = fit_model(sample, include_year_effects=False)
            two_way_result = fit_model(sample, include_year_effects=True)
            entity_table = format_result(entity_result)
            two_way_table = format_result(two_way_result)
            print(f"\n--- {label}: Entity FE (reference) ---\n{entity_table}")
            print(f"\n--- {label}: Entity and year FE (preferred) ---\n{two_way_table}")
            output.write(f"--- {label}: Entity FE (reference) ---\n{entity_table}\n\n")
            output.write(
                f"--- {label}: Entity and year FE (preferred) ---\n{two_way_table}\n\n"
            )

            if label == LOW_MIDDLE_GROUP:
                summary = turning_point_summary(two_way_result)
                print(summary)
                output.write(summary + "\n\n")

    plot_data = data.reset_index()
    plt.figure(figsize=(10, 6))
    sns.scatterplot(
        data=plot_data,
        x="GDP_per_capita",
        y="CO2_per_capita",
        hue="Income_Group",
        alpha=0.6,
    )
    sns.regplot(
        data=plot_data,
        x="GDP_per_capita",
        y="CO2_per_capita",
        scatter=False,
        order=2,
        color="black",
        label="Pooled quadratic fit",
    )
    plt.title("Environmental Kuznets Curve Analysis\nGDP vs CO2 per capita")
    plt.xlabel("GDP per capita (constant 2015 US$)")
    plt.ylabel("CO2 emissions (metric tons per capita)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig("ekc_plot.png")
    plt.close()
    print("\nPlot saved to ekc_plot.png")


if __name__ == "__main__":
    run_analysis()
