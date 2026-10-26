from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.services.reservations import calculate_monthly_revenue, calculate_total_revenue, period_bounds


@pytest.mark.parametrize("month,year,zone,start,end", [
    (3, 2024, "Europe/Paris", "2024-02-29T23:00:00+00:00", "2024-03-31T22:00:00+00:00"),
    (3, 2024, "America/New_York", "2024-03-01T05:00:00+00:00", "2024-04-01T04:00:00+00:00"),
    (11, 2024, "America/New_York", "2024-11-01T04:00:00+00:00", "2024-12-01T05:00:00+00:00"),
    (12, 2024, "UTC", "2024-12-01T00:00:00+00:00", "2025-01-01T00:00:00+00:00"),
    (2, 2024, "UTC", "2024-02-01T00:00:00+00:00", "2024-03-01T00:00:00+00:00"),
    (None, 2024, "Europe/Paris", "2023-12-31T23:00:00+00:00", "2024-12-31T23:00:00+00:00"),
])
def test_local_calendar_bounds(month, year, zone, start, end):
    bounds = period_bounds(month, year, zone)
    assert bounds == (datetime.fromisoformat(start), datetime.fromisoformat(end))
    assert all(bound.tzinfo == timezone.utc for bound in bounds)


@pytest.mark.parametrize("month,year", [(0, 2024), (13, 2024), (1, 0), (1, 9999)])
def test_invalid_calendar_bounds(month, year):
    with pytest.raises(ValueError):
        period_bounds(month, year, "UTC")


@pytest.mark.asyncio
async def test_seeded_monthly_totals_and_tenant_isolation(db):
    assert await calculate_monthly_revenue("prop-001", 3, 2024, "tenant-a") == Decimal("2250.00")
    february = await calculate_total_revenue("prop-001", "tenant-a", 2, 2024)
    assert (february["total"], february["count"]) == ("0.00", 0)
    ocean = await calculate_total_revenue("prop-001", "tenant-b", 3, 2024)
    assert (ocean["total"], ocean["count"]) == ("0.00", 0)


@pytest.mark.asyncio
async def test_half_open_month_boundary_and_rounding_once(db):
    async with db.get_session() as session:
        # Paris March starts at 23:00 UTC and ends at 22:00 UTC because of DST.
        for id_, date, amount in [
            ("before", "2024-02-29 22:59:59.999999+00", "100.000"),
            ("start", "2024-02-29 23:00:00+00", "0.005"),
            ("last", "2024-03-31 21:59:59.999999+00", "0.000"),
            ("end", "2024-03-31 22:00:00+00", "500.000"),
        ]:
            await session.execute(text("""
                INSERT INTO reservations (id, property_id, tenant_id, check_in_date, check_out_date, total_amount)
                VALUES (:id, 'prop-001', 'tenant-a', CAST(:date AS timestamptz), CAST(:date AS timestamptz) + interval '1 day', :amount)
            """), {"id": id_, "date": datetime.fromisoformat(date), "amount": Decimal(amount)})
        await session.commit()
    result = await calculate_total_revenue("prop-001", "tenant-a", 3, 2024)
    assert result["total"] == "2250.01"  # round half up; never per-reservation rounding
    assert result["count"] == 6
    annual = await calculate_total_revenue("prop-001", "tenant-a", year=2024)
    assert annual["total"] == "2850.01"
