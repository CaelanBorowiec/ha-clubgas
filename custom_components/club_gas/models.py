"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class FuelPrice:
    """A single fuel grade price."""

    fuel_type: str
    price: float | None


@dataclass(slots=True)
class StationConfig:
    """Configured station reference."""

    brand: str
    store_id: str
    name: str
    url: str | None = None


@dataclass(slots=True)
class UserConfig:
    """Per-user MPG configuration."""

    user_id: str
    user_name: str
    mpg: float


@dataclass(slots=True)
class StationData:
    """Live station data from a retailer."""

    brand: str
    store_id: str
    name: str
    address: str
    latitude: float | None
    longitude: float | None
    distance_miles: float | None
    url: str | None = None
    prices: dict[str, float | None] = field(default_factory=dict)
