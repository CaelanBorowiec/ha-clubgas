"""Tests for Club Gas helpers and API clients."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import Mock

import pytest

from club_gas.api.helpers import (
    haversine_miles,
    parse_sams_prices,
    parse_station_reference,
)
from club_gas.api.costco import CostcoClient

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_station_reference_sams_url() -> None:
    brand, store_id, url = parse_station_reference(
        "https://www.samsclub.com/club/6677-monroeville-pa/fuel-center"
    )
    assert brand == "sams"
    assert store_id == "6677"
    assert "6677" in url


def test_parse_station_reference_costco_url() -> None:
    brand, store_id, _url = parse_station_reference(
        "https://www.costco.com/w/-/pa/pittsburgh/332"
    )
    assert brand == "costco"
    assert store_id == "332"


def test_parse_station_reference_bare_ids() -> None:
    assert parse_station_reference("costco:332")[1] == "332"
    assert parse_station_reference("sams:6677")[1] == "6677"


def test_parse_sams_prices() -> None:
    html = (FIXTURES / "sams_monroeville.html").read_text(encoding="utf-8")
    prices = parse_sams_prices(html)
    assert prices["unleaded"] == pytest.approx(4.36)
    assert prices["premium"] == pytest.approx(5.16)


def test_haversine_miles() -> None:
    distance = haversine_miles(40.4406, -79.9959, 40.4625, -79.9611)
    assert 1.0 < distance < 5.0


def test_costco_parse_warehouse() -> None:
    payload = json.loads((FIXTURES / "costco_warehouses.json").read_text(encoding="utf-8"))
    warehouse = payload[1]
    client = CostcoClient(session=Mock())
    station = client._parse_warehouse(warehouse, 3.2)
    assert station is not None
    assert station.store_id == "332"
    assert station.prices["regular"] == pytest.approx(3.459)
    assert station.prices["diesel"] == pytest.approx(3.899)
