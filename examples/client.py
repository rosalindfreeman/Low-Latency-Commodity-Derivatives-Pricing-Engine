from __future__ import annotations

import asyncio

import httpx


async def main() -> None:
    requests = [
        {"symbol": "GC", "strike": 2400, "maturity": 0.5},
        {"symbol": "SI", "strike": 30, "maturity": 0.5},
        {"symbol": "CL", "strike": 80, "maturity": 0.5},
        {"symbol": "NG", "strike": 3.2, "maturity": 0.5},
    ]
    async with httpx.AsyncClient(base_url="http://localhost:8000", timeout=30) as client:
        responses = await asyncio.gather(*(client.post("/price", json=item) for item in requests))
        for response in responses:
            response.raise_for_status()
            print(response.json())


if __name__ == "__main__":
    asyncio.run(main())

