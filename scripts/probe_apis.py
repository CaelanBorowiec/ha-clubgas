"""Phase 0 API validation probe (not shipped)."""

from __future__ import annotations

import asyncio
import json
import re

import aiohttp

COSTCO_URL = "https://www.costco.com/AjaxWarehouseBrowseLookupView"
LAT, LNG = 40.4406, -79.9959

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.costco.com/warehouse-locations",
}


async def test_costco(session: aiohttp.ClientSession) -> None:
    params = {
        "numOfWarehouses": "50",
        "hasGas": "true",
        "populateWarehouseDetails": "true",
        "latitude": str(LAT),
        "longitude": str(LNG),
        "countryCode": "US",
    }
    async with session.get(COSTCO_URL, params=params, headers=HEADERS) as resp:
        print("Costco status:", resp.status)
        data = json.loads(await resp.text())
        print("Costco warehouses:", len(data) - 1 if isinstance(data, list) else 0)
        if isinstance(data, list) and len(data) > 1:
            w = data[1]
            print(
                "Sample:",
                w.get("stlocID"),
                w.get("locationName"),
                w.get("gasPrices"),
            )


async def test_sams(session: aiohttp.ClientSession) -> None:
    urls = [
        "https://www.samsclub.com/club/6677-monroeville-pa/fuel-center",
        "https://www.samsclub.com/club/6575-pittsburgh-pa/fuel-center",
    ]
    html_headers = {
        **HEADERS,
        "Accept": "text/html,application/xhtml+xml",
    }
    for url in urls:
        async with session.get(url, headers=html_headers) as resp:
            html = await resp.text()
            club_id = url.split("/club/")[1].split("-")[0]
            print(f"Sams #{club_id} status:", resp.status, "len:", len(html))
            next_data = re.search(
                r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>',
                html,
                re.DOTALL,
            )
            if next_data:
                print("  __NEXT_DATA__ found")
            prices = re.findall(
                r"(Unleaded|Premium)\s+(\d+\.\d+)\s+dollars and \d+ tenths cents",
                html,
            )
            if not prices:
                prices = re.findall(
                    r'aria-label="(Unleaded|Premium)\s+(\d+\.\d+)',
                    html,
                )
            print("  prices:", prices)


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        await test_costco(session)
        await test_sams(session)


if __name__ == "__main__":
    asyncio.run(main())
