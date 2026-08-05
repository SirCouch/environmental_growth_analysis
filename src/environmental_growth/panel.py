"""Load locked sources and construct the country-year panel."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import pandas as pd


KEY_COLUMNS = ["country", "year"]


def sha256_file(path: str | Path) -> str:
    """Return the SHA-256 digest of a file."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate_unique_country_year(frame: pd.DataFrame, label: str) -> None:
    """Reject duplicate country-year records before they can multiply joins."""
    duplicated = frame.duplicated(KEY_COLUMNS, keep=False)
    if duplicated.any():
        examples = frame.loc[duplicated, KEY_COLUMNS].head(5).to_dict("records")
        raise ValueError(f"{label} contains duplicate country-year rows: {examples}")


def load_source_lock(path: str | Path = "data/sources.lock.json") -> dict[str, Any]:
    lock_path = Path(path)
    with lock_path.open(encoding="utf-8") as stream:
        lock = json.load(stream)
    if lock.get("schema_version") != 1:
        raise ValueError("Unsupported source-lock schema version")
    return lock


def _repository_root(lock_path: Path) -> Path:
    if lock_path.parent.name != "data":
        raise ValueError("The source lock must live directly under the data directory")
    return lock_path.parent.parent.resolve()


def load_locked_sources(
    lock_path: str | Path = "data/sources.lock.json",
) -> tuple[dict[str, Any], pd.DataFrame, dict[str, pd.DataFrame]]:
    """Read and hash-check every normalized file named by the source lock."""
    resolved_lock_path = Path(lock_path).resolve()
    lock = load_source_lock(resolved_lock_path)
    root = _repository_root(resolved_lock_path)
    snapshot_dir = root / lock["snapshot_path"]
    if not snapshot_dir.is_dir():
        raise FileNotFoundError(f"Locked snapshot directory is missing: {snapshot_dir}")

    loaded: dict[str, pd.DataFrame] = {}
    for name, entry in lock["files"].items():
        file_path = snapshot_dir / entry["path"]
        if not file_path.is_file():
            raise FileNotFoundError(f"Locked source file is missing: {file_path}")
        actual_hash = sha256_file(file_path)
        if actual_hash != entry["sha256"]:
            raise ValueError(
                f"Locked source hash mismatch for {file_path}: "
                f"expected {entry['sha256']}, got {actual_hash}"
            )
        loaded[name] = pd.read_csv(file_path)

    try:
        metadata = loaded.pop("country_metadata")
    except KeyError as error:
        raise ValueError("Source lock has no country_metadata file") from error
    return lock, metadata, loaded


def build_panel(
    country_universe: pd.DataFrame,
    sources: dict[str, pd.DataFrame],
    config: dict[str, Any],
) -> pd.DataFrame:
    """Merge normalized sources onto the complete eligible country-year grid."""
    eligible = country_universe.loc[country_universe["eligible"], "country"].tolist()
    start_year = config["period"]["start_year"]
    end_year = config["period"]["end_year"]
    grid = pd.MultiIndex.from_product(
        [eligible, range(start_year, end_year + 1)], names=KEY_COLUMNS
    ).to_frame(index=False)

    panel = grid
    declared_variables = list(
        config["sources"]["world_bank"]["indicators"].values()
    ) + [config["sources"]["owid"]["output_column"]]
    missing_sources = set(declared_variables).difference(sources)
    if missing_sources:
        raise ValueError(f"Snapshot is missing declared variables: {sorted(missing_sources)}")

    for variable in declared_variables:
        source = sources[variable].copy()
        expected = {"country", "year", variable}
        if not expected.issubset(source.columns):
            raise ValueError(f"Source {variable} must contain columns {sorted(expected)}")
        source = source.loc[:, ["country", "year", variable]]
        source["year"] = pd.to_numeric(source["year"], errors="raise").astype(int)
        source[variable] = pd.to_numeric(source[variable], errors="coerce")
        source = source[
            source["country"].isin(eligible)
            & source["year"].between(start_year, end_year)
        ]
        validate_unique_country_year(source, variable)
        panel = panel.merge(source, on=KEY_COLUMNS, how="left", validate="one_to_one")

    metadata_columns = [
        "country",
        "country_name",
        "income_level_code",
        "income_group",
    ]
    panel = panel.merge(
        country_universe.loc[country_universe["eligible"], metadata_columns],
        on="country",
        how="left",
        validate="many_to_one",
    )
    validate_unique_country_year(panel, "merged panel")
    return panel.sort_values(KEY_COLUMNS, kind="stable").reset_index(drop=True)


def transform_analysis_panel(
    panel: pd.DataFrame, config: dict[str, Any]
) -> pd.DataFrame:
    """Create model terms after applying the declared complete-case rule."""
    required = config["coverage"]["required_variables"]
    analytic = panel.dropna(subset=required).copy()
    analytic["GDP_k"] = analytic["GDP_per_capita"] / 1000.0
    analytic["GDP_sq"] = analytic["GDP_k"] ** 2
    return analytic.sort_values(KEY_COLUMNS, kind="stable").reset_index(drop=True)
