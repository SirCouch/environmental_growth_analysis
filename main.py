
import os
import sys

def main():
    print("Step 1: Data Acquisition")
    # Check if data exists
    if not os.path.exists("environmental_data.csv"):
        print("Data not found. Running data loader...")
        res = os.system("python src/data_loader.py")
        if res != 0:
            print("Data cleaning failed.")
            sys.exit(1)
    else:
        print("Data found. Skipping download (delete csv to re-download).")
        
    print("\nStep 2: Analysis")
    res = os.system("python src/analysis.py")
    if res != 0:
        print("Analysis failed.")
        sys.exit(1)
        
    print("\nWorkflow completed successfully. Check regression_results.txt and ekc_plot.png.")

if __name__ == "__main__":
    main()
