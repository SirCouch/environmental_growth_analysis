
import pandas as pd
import numpy as np
from linearmodels.panel import PanelOLS
import statsmodels.api as sm
import matplotlib.pyplot as plt
import seaborn as sns

def load_data(filepath="environmental_data.csv"):
    df = pd.read_csv(filepath)
    return df

def run_analysis():
    print("Loading data...")
    df = load_data()
    
    # 1. Preprocessing
    # Ensure numeric
    cols = ['GDP_per_capita', 'CO2_per_capita', 'Education_Tertiary', 'Rule_of_Law']
    for c in cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
        
    # Drop missing
    print(f"Original shape: {df.shape}")
    print("Column counts:")
    print(df.count())
    
    # Relax dropna? 
    # Try dropping only subset if needed, but for regression we need all.
    df = df.dropna(subset=cols)
    print(f"Shape after dropna: {df.shape}")
    
    if df.empty:
        print("Error: No data available for analysis.")
        return

    # Scale GDP to 'Thousands of dollars' for numerical stability and readability
    # GDP usually 1000s to 50000+. 
    df['GDP_k'] = df['GDP_per_capita'] / 1000.0
    df['GDP_sq'] = df['GDP_k'] ** 2
    
    # Set Index for Panel Data
    df = df.set_index(['country', 'year'])
    
    # 2. Variable Definitions
    # Dependent: CO2
    # Independent: GDP, GDP^2, RoL, Edu
    # We add a constant
    
    exog_vars = ['GDP_k', 'GDP_sq', 'Rule_of_Law', 'Education_Tertiary']
    
    # 3. Full Model (Fixed Effects)
    print("\n--- Model 1: All Countries (Fixed Effects) ---")
    exog = sm.add_constant(df[exog_vars])
    mod = PanelOLS(df['CO2_per_capita'], exog, entity_effects=True)
    res = mod.fit()
    print(res)
    
    with open("regression_results.txt", "w") as f:
        f.write("--- Model 1: All Countries ---\n")
        f.write(str(res) + "\n\n")

    # 4. Stratified Analysis
    # We have 'Income_Group' column. But it's not in index? 
    # It was in the csv. set_index moves 'country' to index. 'Income_Group' should be a column.
    
    groups = df['Income_Group'].unique()
    
    for g in groups:
        print(f"\n--- Model for Group: {g} ---")
        sub_df = df[df['Income_Group'] == g]
        
        if sub_df.empty or len(sub_df) < 10:
            print("Not enough data.")
            continue
            
        exog_sub = sm.add_constant(sub_df[exog_vars])
        try:
            mod_sub = PanelOLS(sub_df['CO2_per_capita'], exog_sub, entity_effects=True)
            res_sub = mod_sub.fit()
            print(res_sub)
            
            with open("regression_results.txt", "a") as f:
                f.write(f"--- Model: {g} ---\n")
                f.write(str(res_sub) + "\n\n")
        except Exception as e:
            print(f"Model failed for {g}: {e}")

    # 5. Visualization (EKC)
    # Scatter plot of GDP vs CO2
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=df.reset_index(), x='GDP_per_capita', y='CO2_per_capita', hue='Income_Group', alpha=0.6)
    
    # Fit line? 
    # Just a visual aid
    sns.regplot(data=df.reset_index(), x='GDP_per_capita', y='CO2_per_capita', scatter=False, order=2, color='black', label='Quadratic Fit')
    
    plt.title("Environmental Kuznets Curve Analysis\nGDP vs CO2 per capita")
    plt.xlabel("GDP per capita (Constant 2015 US$)")
    plt.ylabel("CO2 Emissions (Metric tons per capita)")
    plt.legend()
    plt.grid(True)
    plt.savefig("ekc_plot.png")
    print("\nPlot saved to ekc_plot.png")

if __name__ == "__main__":
    run_analysis()
