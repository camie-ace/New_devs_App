import json
from unittest.mock import AsyncMock

import pytest
from app.services import cache
from redis.exceptions import ConnectionError


def summary(tenant, month=3, year=2024):
    return {
        "property_id": "prop-001",
        "tenant_id": tenant,
        "month": month,
        "year": year,
        "total": "2250.00" if tenant == "tenant-a" else "0.00",
        "count": 4,
        "currency": "USD",
        "timezone": "Europe/Paris",
    }


@pytest.mark.asyncio
async def test_cache_is_scoped_by_tenant_and_period(monkeypatch, memory_cache):
    async def calculate(property_id, tenant_id, month, year):
        return summary(tenant_id, month, year)

    calculator = AsyncMock(side_effect=calculate)
    monkeypatch.setattr(cache, "calculate_total_revenue", calculator)
    for tenant in ["tenant-a", "tenant-b", "tenant-a", "tenant-b"]:
        result = await cache.get_revenue_summary("prop-001", tenant, 3, 2024)
        assert result["tenant_id"] == tenant
    assert calculator.await_count == 2
    for month, year in [(2, 2024), (3, 2025), (None, 2024), (None, None)]:
        await cache.get_revenue_summary("prop-001", "tenant-a", month, year)
    assert len(memory_cache.values) == 6
    assert all(ttl == 300 for _, ttl, _ in memory_cache.writes)


@pytest.mark.parametrize(
    "cached",
    [
        "not-json",
        "[]",
        "null",
        json.dumps(summary("tenant-b")),
        json.dumps({**summary("tenant-a"), "total": None}),
    ],
)
@pytest.mark.asyncio
async def test_bad_or_foreign_cache_entry_is_ignored(monkeypatch, memory_cache, cached):
    key = "revenue:v2:" + json.dumps(["tenant-a", "prop-001", 3, 2024])
    memory_cache.values[key] = cached
    calculator = AsyncMock(return_value=summary("tenant-a"))
    monkeypatch.setattr(cache, "calculate_total_revenue", calculator)
    assert (await cache.get_revenue_summary("prop-001", "tenant-a", 3, 2024))[
        "tenant_id"
    ] == "tenant-a"
    calculator.assert_awaited_once()


@pytest.mark.asyncio
async def test_redis_failure_reads_real_database_and_does_not_hide_db_failure(
    monkeypatch,
):
    monkeypatch.setattr(
        cache,
        "redis_client",
        AsyncMock(
            get=AsyncMock(side_effect=ConnectionError),
            setex=AsyncMock(side_effect=ConnectionError),
        ),
    )
    calculator = AsyncMock(return_value=summary("tenant-a"))
    monkeypatch.setattr(cache, "calculate_total_revenue", calculator)
    assert (await cache.get_revenue_summary("prop-001", "tenant-a", 3, 2024))[
        "total"
    ] == "2250.00"
    calculator.side_effect = RuntimeError("database down")
    with pytest.raises(RuntimeError, match="database down"):
        await cache.get_revenue_summary("prop-001", "tenant-a", 3, 2024)
