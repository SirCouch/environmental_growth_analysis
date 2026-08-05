from pathlib import Path

import pandas as pd


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


def test_locked_run_preserves_reported_sample_and_identification_status():
    artifacts = REPOSITORY_ROOT / "artifacts" / "current"
    composition = pd.read_csv(artifacts / "sample_composition.csv").set_index("sample_id")
    full = composition.loc["full_sample"]
    assert full["n_observations"] == 2009
    assert full["n_countries"] == 104

    turning = pd.read_csv(artifacts / "turning_points.csv").iloc[0]
    assert turning["identification_status"] == "finite_turning_point_not_identified"
