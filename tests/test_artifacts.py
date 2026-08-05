from __future__ import annotations

import json

from environmental_growth.artifacts import verify_manifest
from environmental_growth.panel import sha256_file


def test_manifest_detects_altered_csv_and_figure(tmp_path):
    (tmp_path / "figures").mkdir()
    csv_path = tmp_path / "coefficients.csv"
    figure_path = tmp_path / "figures" / "ekc_plot.png"
    csv_path.write_text("term,estimate\nGDP_k,1\n", encoding="utf-8")
    figure_path.write_bytes(b"original png")
    manifest = {
        "outputs": {
            "coefficients.csv": {"sha256": sha256_file(csv_path)},
            "figures/ekc_plot.png": {"sha256": sha256_file(figure_path)},
        }
    }
    (tmp_path / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    csv_path.write_text("term,estimate\nGDP_k,2\n", encoding="utf-8")
    figure_path.write_bytes(b"altered png")
    errors = verify_manifest(tmp_path)
    assert "manifest hash mismatch: coefficients.csv" in errors
    assert "manifest hash mismatch: figures/ekc_plot.png" in errors
