"""Live-source acquisition and immutable normalized snapshots.

This is the only module in the reproduction path that performs network I/O.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable
from zipfile import ZipFile

import pandas as pd
import requests

from .panel import sha256_file, validate_unique_country_year


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _header_metadata(response: requests.Response) -> dict[str, str | None]:
    return {
        "etag": response.headers.get("ETag"),
        "last_modified": response.headers.get("Last-Modified"),
    }


def _response_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def fetch_country_metadata(
    session: requests.Session,
    api_base: str,
    retrieved_at: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Fetch every World Bank metadata page and normalize classification fields."""
    endpoint = f"{api_base.rstrip('/')}/country"
    page = 1
    pages = 1
    records: list[dict[str, Any]] = []
    raw_hash = hashlib.sha256()
    response_headers: list[dict[str, str | None]] = []

    while page <= pages:
        params = {"format": "json", "per_page": 400, "page": page}
        response = session.get(endpoint, params=params, timeout=60)
        response.raise_for_status()
        raw_hash.update(response.content)
        response_headers.append(_header_metadata(response))
        payload = response.json()
        if not isinstance(payload, list) or len(payload) < 2 or payload[1] is None:
            raise RuntimeError(f"World Bank country metadata page {page} was empty")
        header = payload[0]
        pages = int(header.get("pages", 1))
        records.extend(payload[1])
        page += 1

    normalized = pd.DataFrame(
        {
            "country": [record["id"] for record in records],
            "country_name": [record["name"] for record in records],
            "income_level_code": [record["incomeLevel"]["id"] for record in records],
            "income_level_name": [record["incomeLevel"]["value"] for record in records],
            "region_code": [record["region"]["id"] for record in records],
            "region_name": [record["region"]["value"] for record in records],
        }
    )
    normalized["is_aggregate"] = normalized["region_name"].eq("Aggregates")
    if normalized["country"].duplicated().any():
        raise RuntimeError("World Bank country metadata contains duplicate country codes")
    normalized = normalized.sort_values("country", kind="stable").reset_index(drop=True)
    metadata = {
        "api_version": "v2",
        "endpoint": endpoint,
        "request_parameters": {"format": "json", "per_page": 400},
        "retrieved_at": retrieved_at,
        "classification_snapshot_date": retrieved_at[:10],
        "response_sha256": raw_hash.hexdigest(),
        "response_headers_by_page": response_headers,
        "pages": pages,
    }
    return normalized, metadata


def _find_world_bank_data_file(archive: ZipFile, indicator_id: str) -> str:
    candidates = [
        name
        for name in archive.namelist()
        if Path(name).name.startswith("API_") and name.lower().endswith(".csv")
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"Expected one World Bank data CSV for {indicator_id}, found {candidates}"
        )
    return candidates[0]


def normalize_world_bank_indicator(
    content: bytes,
    indicator_id: str,
    output_column: str,
    country_codes: Iterable[str],
    start_year: int,
    end_year: int,
) -> pd.DataFrame:
    """Normalize a World Bank bulk-download archive to a country-year series."""
    with ZipFile(BytesIO(content)) as archive:
        data_file = _find_world_bank_data_file(archive, indicator_id)
        wide = pd.read_csv(archive.open(data_file), skiprows=4, low_memory=False)
    required_columns = {"Country Code", *(str(year) for year in range(start_year, end_year + 1))}
    missing = required_columns.difference(wide.columns)
    if missing:
        raise RuntimeError(f"World Bank {indicator_id} schema is missing {sorted(missing)}")

    years = [str(year) for year in range(start_year, end_year + 1)]
    selected = wide.loc[:, ["Country Code", *years]].copy()
    duplicated_codes = selected["Country Code"].duplicated(keep=False)
    if duplicated_codes.any():
        duplicates = selected.loc[duplicated_codes]
        conflicts = duplicates.groupby("Country Code", sort=True)[years].nunique(
            dropna=True
        )
        conflicting_cells = conflicts.gt(1)
        if conflicting_cells.any().any():
            locations = [
                {"country": country, "year": year}
                for country, year in conflicting_cells.stack()[lambda values: values].index[:5]
            ]
            raise RuntimeError(
                f"World Bank {indicator_id} has conflicting duplicate values: "
                f"{locations}"
            )
        # The bulk service occasionally emits complementary duplicate rows for a
        # country. Coalesce only after proving that no country-year has two values.
        selected = selected.groupby("Country Code", as_index=False, sort=False).first()

    long = selected.melt(
        id_vars=["Country Code"],
        value_vars=years,
        var_name="year",
        value_name=output_column,
    ).rename(columns={"Country Code": "country"})
    country_set = set(country_codes)
    long = long[long["country"].isin(country_set)].copy()
    long["year"] = long["year"].astype(int)
    long[output_column] = pd.to_numeric(long[output_column], errors="coerce")
    long = long.sort_values(["country", "year"], kind="stable").reset_index(drop=True)
    validate_unique_country_year(long, output_column)
    return long


def fetch_world_bank_indicator(
    session: requests.Session,
    api_base: str,
    indicator_id: str,
    output_column: str,
    country_codes: Iterable[str],
    start_year: int,
    end_year: int,
    retrieved_at: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    endpoint = f"{api_base.rstrip('/')}/en/indicator/{indicator_id}"
    params = {"downloadformat": "csv"}
    response = session.get(endpoint, params=params, timeout=180)
    response.raise_for_status()
    normalized = normalize_world_bank_indicator(
        response.content,
        indicator_id,
        output_column,
        country_codes,
        start_year,
        end_year,
    )
    metadata = {
        "api_version": "v2",
        "endpoint": endpoint,
        "indicator_id": indicator_id,
        "request_parameters": params,
        "retrieved_at": retrieved_at,
        "response_sha256": _response_sha256(response.content),
        **_header_metadata(response),
    }
    return normalized, metadata


def resolve_github_commit(
    session: requests.Session, repository: str, branch: str
) -> tuple[str, dict[str, Any]]:
    endpoint = f"https://api.github.com/repos/{repository}/commits/{branch}"
    response = session.get(
        endpoint,
        headers={"Accept": "application/vnd.github+json"},
        timeout=60,
    )
    response.raise_for_status()
    payload = response.json()
    commit = payload.get("sha")
    if not isinstance(commit, str) or len(commit) != 40:
        raise RuntimeError("GitHub did not return a full OWID commit SHA")
    headers = _header_metadata(response)
    return commit, {
        "commit_resolution_endpoint": endpoint,
        "commit_resolution_response_sha256": _response_sha256(response.content),
        "commit_resolution_etag": headers["etag"],
        "commit_resolution_last_modified": headers["last_modified"],
    }


def fetch_owid_co2(
    session: requests.Session,
    source_config: dict[str, Any],
    country_codes: Iterable[str],
    start_year: int,
    end_year: int,
    retrieved_at: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Resolve the mutable branch and snapshot the normalized OWID extract."""
    repository = source_config["repository"]
    branch = source_config["branch"]
    commit, resolution_metadata = resolve_github_commit(session, repository, branch)
    upstream_path = source_config["path"]
    endpoint = f"https://raw.githubusercontent.com/{repository}/{commit}/{upstream_path}"
    response = session.get(endpoint, timeout=300)
    response.raise_for_status()
    source_column = source_config["source_column"]
    output_column = source_config["output_column"]
    raw = pd.read_csv(
        BytesIO(response.content),
        usecols=["iso_code", "year", source_column],
        low_memory=False,
    )
    country_set = set(country_codes)
    normalized = raw[
        raw["iso_code"].isin(country_set)
        & raw["year"].between(start_year, end_year)
    ].rename(columns={"iso_code": "country", source_column: output_column})
    normalized["year"] = pd.to_numeric(normalized["year"], errors="raise").astype(int)
    normalized[output_column] = pd.to_numeric(
        normalized[output_column], errors="coerce"
    )
    normalized = normalized.loc[:, ["country", "year", output_column]]
    normalized = normalized.sort_values(["country", "year"], kind="stable").reset_index(drop=True)
    validate_unique_country_year(normalized, output_column)
    metadata = {
        "repository": repository,
        "configured_branch": branch,
        "resolved_commit": commit,
        "upstream_path": upstream_path,
        "endpoint": endpoint,
        "retrieved_at": retrieved_at,
        "response_sha256": _response_sha256(response.content),
        **_header_metadata(response),
        **resolution_metadata,
    }
    return normalized, metadata


def _write_normalized_csv(frame: pd.DataFrame, path: Path) -> None:
    frame.to_csv(
        path,
        index=False,
        lineterminator="\n",
        float_format="%.17g",
        na_rep="",
    )


def _snapshot_digest(files: dict[str, dict[str, str]]) -> str:
    stable = {name: entry["sha256"] for name, entry in sorted(files.items())}
    return hashlib.sha256(
        json.dumps(stable, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def refresh_sources(
    config: dict[str, Any],
    data_dir: str | Path = "data",
    session: requests.Session | None = None,
) -> dict[str, Any]:
    """Contact live sources, store an immutable snapshot, and update the lock."""
    data_path = Path(data_dir).resolve()
    snapshots_path = data_path / "snapshots"
    snapshots_path.mkdir(parents=True, exist_ok=True)
    owned_session = session is None
    http = session or requests.Session()
    retrieved_at = _utc_now().isoformat().replace("+00:00", "Z")
    period = config["period"]
    wb_config = config["sources"]["world_bank"]

    try:
        countries, country_metadata = fetch_country_metadata(
            http, wb_config["api_base"], retrieved_at
        )
        universe_config = config["country_universe"]
        eligible_mask = countries["income_level_code"].isin(universe_config["income_codes"])
        if universe_config["exclude_aggregates"]:
            eligible_mask &= ~countries["is_aggregate"]
        country_codes = countries.loc[eligible_mask, "country"].tolist()

        frames: dict[str, pd.DataFrame] = {"country_metadata": countries}
        source_metadata: dict[str, Any] = {"country_metadata": country_metadata}
        for indicator_id, output_column in wb_config["indicators"].items():
            frame, metadata = fetch_world_bank_indicator(
                http,
                wb_config["api_base"],
                indicator_id,
                output_column,
                country_codes,
                period["start_year"],
                period["end_year"],
                retrieved_at,
            )
            frames[output_column] = frame
            source_metadata[output_column] = metadata

        owid_config = config["sources"]["owid"]
        co2, co2_metadata = fetch_owid_co2(
            http,
            owid_config,
            country_codes,
            period["start_year"],
            period["end_year"],
            retrieved_at,
        )
        frames[owid_config["output_column"]] = co2
        source_metadata[owid_config["output_column"]] = co2_metadata
    finally:
        if owned_session:
            http.close()

    with tempfile.TemporaryDirectory(prefix="snapshot-building-", dir=snapshots_path) as temp:
        temp_path = Path(temp)
        files: dict[str, dict[str, str]] = {}
        for name, frame in frames.items():
            filename = f"{name}.csv"
            file_path = temp_path / filename
            _write_normalized_csv(frame, file_path)
            files[name] = {"path": filename, "sha256": sha256_file(file_path)}

        content_digest = _snapshot_digest(files)
        snapshot_id = f"snapshot-{content_digest[:12]}"
        final_snapshot = snapshots_path / snapshot_id
        if final_snapshot.exists():
            for entry in files.values():
                existing = final_snapshot / entry["path"]
                if not existing.is_file() or sha256_file(existing) != entry["sha256"]:
                    raise RuntimeError(
                        f"Immutable snapshot collision at {final_snapshot}"
                    )
        else:
            final_snapshot.mkdir()
            for entry in files.values():
                shutil.copy2(temp_path / entry["path"], final_snapshot / entry["path"])

    repository_root = data_path.parent
    lock = {
        "schema_version": 1,
        "snapshot_id": snapshot_id,
        "snapshot_path": final_snapshot.relative_to(repository_root).as_posix(),
        "created_at": retrieved_at,
        "classification_snapshot_date": country_metadata[
            "classification_snapshot_date"
        ],
        "content_sha256": content_digest,
        "files": files,
        "sources": source_metadata,
    }
    lock_path = data_path / "sources.lock.json"
    pending_lock = data_path / ".sources.lock.json.pending"
    pending_lock.write_text(
        json.dumps(lock, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    pending_lock.replace(lock_path)
    return lock
