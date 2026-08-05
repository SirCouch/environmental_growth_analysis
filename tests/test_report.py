from environmental_growth.report import readme_matches_run


def test_readme_run_marker_must_match_manifest(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text("<!-- run-id: correct -->\n", encoding="utf-8")
    assert readme_matches_run(readme, {"run_id": "correct"})
    assert not readme_matches_run(readme, {"run_id": "different"})
