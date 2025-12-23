
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
- **Model**: Fixed Effects (Entity Effects) Quadratic Regression
- **Implementation**: Python (pandas, linearmodels, requests)

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
