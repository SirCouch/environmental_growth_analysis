from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from environmental_growth.sources import (
    fetch_country_metadata,
    normalize_world_bank_indicator,
)


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.content = json.dumps(payload).encode()
        self.headers = {}

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.pages = []

    def get(self, endpoint, params, timeout):
        self.pages.append(params["page"])
        return next(self.responses)


def _record(code):
    return {
        "id": code,
        "name": f"Country {code}",
        "incomeLevel": {"id": "HIC", "value": "High income"},
        "region": {"id": "R1", "value": "Region"},
    }


def test_country_metadata_pagination_is_complete():
    responses = [
        FakeResponse([{"pages": 2}, [_record("AAA")]]),
        FakeResponse([{"pages": 2}, [_record("BBB")]]),
    ]
    session = FakeSession(responses)
    frame, metadata = fetch_country_metadata(
        session, "https://api.worldbank.test/v2", "2026-08-05T00:00:00Z"
    )
    assert session.pages == [1, 2]
    assert frame["country"].tolist() == ["AAA", "BBB"]
    assert metadata["pages"] == 2


def test_complementary_world_bank_duplicates_are_coalesced():
    columns = ["Country Name", "Country Code", "Indicator Name", "Indicator Code", "2000"]
    frame = pd.DataFrame(
        [
            ["Alpha", "AAA", "Test", "TEST", None],
            ["Alpha", "AAA", "Test", "TEST", 1.25],
        ],
        columns=columns,
    )
    csv = "metadata\nmetadata\nmetadata\nmetadata\n" + frame.to_csv(index=False)
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("API_TEST.csv", csv)
    normalized = normalize_world_bank_indicator(
        buffer.getvalue(), "TEST", "value", ["AAA"], 2000, 2000
    )
    assert normalized.to_dict("records") == [
        {"country": "AAA", "year": 2000, "value": 1.25}
    ]
