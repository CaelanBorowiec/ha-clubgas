# Club Gas

Home Assistant custom integration (HACS) for tracking **Costco** and **Sam's Club** fuel prices in the US, with per-user MPG-based trip cost sensors and Lovelace dashboard examples.

## Features

- Track fuel prices for configured Costco and Sam's Club stations
- Discover nearby stations by home coordinates and search radius
- Add stations manually via fuel-center URL or `costco:332` / `sams:6677` IDs
- Global household driver settings (MPG and fuel grade) shared across all stations
- Trip cost sensors: `(distance / mpg) * price_per_gallon`
- Manual refresh service: `club_gas.refresh`

## Data sources

| Retailer | Method |
| -------- | ------ |
| **Costco US** | Unofficial JSON endpoint used by costco.com (`AjaxWarehouseBrowseLookupView`) |
| **Sam's Club US** | Fuel-center page parsing (`/club/{id}-*/fuel-center`) |

Neither retailer provides a documented public fuel-price API. This integration uses reverse-engineered endpoints and page parsing for personal use. Endpoints may change without notice.

## Installation (HACS)

1. Add this repository as a [custom HACS repository](https://hacs.xyz/docs/faq/custom_repositories/):
   - URL: `https://github.com/CaelanBorowicz/ha-clubgas`
   - Category: **Integration**
2. Install **Club Gas** from HACS
3. Restart Home Assistant
4. Go to **Settings → Devices & Services → Add Integration → Club Gas**

## Configuration

### Step 1 — Home location

Uses your HA home latitude/longitude by default. Set search radius (default 25 mi) and which retailers to include.

### Step 2 — Select stations

The integration discovers nearby stations and shows a checklist sorted by distance. You can also paste URLs, one per line:

```
https://www.samsclub.com/club/6677-monroeville-pa/fuel-center
https://www.samsclub.com/club/6575-pittsburgh-pa/fuel-center
https://www.costco.com/w/-/pa/pittsburgh/332
https://www.costco.com/w/-/PA/homestead/649
```

Or bare IDs:

```
sams:6677
costco:332
```

### Household drivers (optional)

After setup, open **Configure → Configure household drivers** to assign up to three Home Assistant users with MPG and fuel grade (default: 28 MPG, regular/unleaded). Each user gets trip cost sensors for every configured station.

### Reconfigure later

Use **Configure** on the integration to add stations by URL or manage household driver settings.

## Sensors

For each configured station:

| Entity | Example | State |
| ------ | ------- | ----- |
| Price | `sensor.club_gas_costco_332_regular` | $/gal |

For each household driver, trip cost sensors appear under that user's device (one per station):

| Entity | Example | State |
| ------ | ------- | ----- |
| Trip cost | `sensor.jane_costco_pittsburgh_trip_cost` | USD |

Attributes include `distance_miles`, `address`, `latitude`, `longitude`, `mpg`, `trip_gallons`, and `price`.

## Lovelace examples

### Simple entities card

```yaml
type: entities
title: Club Gas Prices
entities:
  - entity: sensor.club_gas_costco_332_regular
  - entity: sensor.club_gas_sams_6677_unleaded
  - entity: sensor.club_gas_sams_6575_unleaded
```

### Sortable table with auto-entities + flex-table-card

Requires [auto-entities](https://github.com/thomasloven/lovelace-auto-entities) and [flex-table-card](https://github.com/custom-cards/flex-table-card):

```yaml
type: custom:auto-entities
card:
  type: custom:flex-table-card
  columns:
    - data: friendly_name
      name: Station
    - data: state
      name: Price
    - data: distance_miles
      name: Distance (mi)
filter:
  include:
    - integration: club_gas
      attributes:
        fuel_type: regular
sort:
  method: state
  numeric: true
```

### Cheapest trip cost (markdown template)

```yaml
type: markdown
content: >
  {% set sensors = states.sensor
     | selectattr('entity_id', 'search', 'trip_cost')
     | list %}
  {% set cheapest = sensors | sort(attribute='state') | first %}
  Cheapest trip: {{ cheapest.name }} — ${{ cheapest.state }}
```

## Development

```bash
pip install aiohttp beautifulsoup4 pytest
pytest
```

The probe script in `scripts/probe_apis.py` can validate live endpoints from your network.

## Disclaimer

Unofficial data sources only. Prices are indicative — verify at the pump before traveling. Not affiliated with Costco or Sam's Club.
