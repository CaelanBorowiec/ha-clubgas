"""Constants for the Club Gas integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "club_gas"
PLATFORMS: Final = ["sensor"]

CONF_HOME_LAT: Final = "home_lat"
CONF_HOME_LNG: Final = "home_lng"
CONF_RADIUS_MILES: Final = "radius_miles"
CONF_STATIONS: Final = "stations"
CONF_USERS: Final = "users"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_FUEL_TYPES: Final = "fuel_types"
CONF_RETAILERS: Final = "retailers"

CONF_BRAND: Final = "brand"
CONF_STORE_ID: Final = "store_id"
CONF_NAME: Final = "name"
CONF_URL: Final = "url"
CONF_USER_ID: Final = "user_id"
CONF_MPG: Final = "mpg"
CONF_USER_NAME: Final = "user_name"
CONF_USER_FUEL_TYPE: Final = "fuel_type"

BRAND_COSTCO: Final = "costco"
BRAND_SAMS: Final = "sams"

FUEL_REGULAR: Final = "regular"
FUEL_PREMIUM: Final = "premium"
FUEL_DIESEL: Final = "diesel"
FUEL_UNLEADED: Final = "unleaded"

DEFAULT_RADIUS_MILES: Final = 25
DEFAULT_MPG: Final = 28.0
DEFAULT_USER_FUEL_TYPE: Final = FUEL_REGULAR
DEFAULT_SCAN_INTERVAL_MINUTES: Final = 180

UPDATE_INTERVAL: Final = timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES)

ATTR_ADDRESS: Final = "address"
ATTR_BRAND: Final = "brand"
ATTR_DISTANCE_MILES: Final = "distance_miles"
ATTR_FUEL_TYPE: Final = "fuel_type"
ATTR_LATITUDE: Final = "latitude"
ATTR_LONGITUDE: Final = "longitude"
ATTR_MPG: Final = "mpg"
ATTR_PRICE: Final = "price"
ATTR_STORE_ID: Final = "store_id"
ATTR_STORE_NAME: Final = "store_name"
ATTR_TRIP_COST: Final = "trip_cost"
ATTR_TRIP_GALLONS: Final = "trip_gallons"
ATTR_USER_ID: Final = "user_id"
ATTR_USER_NAME: Final = "user_name"

SENSOR_TYPE_PRICE: Final = "price"
SENSOR_TYPE_TRIP_COST: Final = "trip_cost"

SERVICE_REFRESH: Final = "refresh"

COSTCO_AJAX_URL: Final = "https://www.costco.com/AjaxWarehouseBrowseLookupView"
SAMS_FUEL_URL_TEMPLATE: Final = "https://www.samsclub.com/club/{club_id}/fuel-center"

USER_AGENT: Final = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
# Costco's Akamai filter blocks browser-like User-Agents. The AJAX API
# allowlists the minimal client fingerprint used by gastrak.
COSTCO_USER_AGENT: Final = "Gastrak/1.0"
