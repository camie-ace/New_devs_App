"""Revenue is recognized in the property's local check-in month.

Sum PostgreSQL NUMERIC values at full precision; round once, half up, when
publishing a two-decimal report. Never combine different currencies.
"""

from datetime import UTC, datetime
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from app.core.database_pool import db_pool
from sqlalchemy import text


class PropertyNotFound(Exception):
    pass


class MixedCurrencies(Exception):
    pass


def period_bounds(month: int | None, year: int, property_timezone: str):
    """Half-open UTC interval derived from local calendar boundaries, including DST."""
    if not 1 <= year <= 9998 or (month is not None and not 1 <= month <= 12):
        raise ValueError("Invalid reporting period")
    zone = ZoneInfo(property_timezone)
    first_month = month or 1
    next_month = first_month + 1 if month and month < 12 else 1
    next_year = year if month and month < 12 else year + 1
    return (
        datetime(year, first_month, 1, tzinfo=zone).astimezone(UTC),
        datetime(next_year, next_month, 1, tzinfo=zone).astimezone(UTC),
    )


async def list_properties(tenant_id: str):
    await db_pool.initialize()
    async with db_pool.get_session() as session:
        result = await session.execute(
            text("""
            SELECT id, name, timezone FROM properties
            WHERE tenant_id = :tenant_id ORDER BY name, id
        """),
            {"tenant_id": tenant_id},
        )
        return [dict(row) for row in result.mappings()]


async def calculate_total_revenue(
    property_id: str,
    tenant_id: str,
    month: int | None = None,
    year: int | None = None,
    db_session=None,
):
    if not tenant_id:
        raise ValueError("Tenant is required")
    if month is not None and year is None:
        raise ValueError("Year is required with month")
    if db_session is None:
        await db_pool.initialize()
        async with db_pool.get_session() as session:
            return await calculate_total_revenue(
                property_id, tenant_id, month, year, session
            )

    params = {"property_id": property_id, "tenant_id": tenant_id}
    property_result = await db_session.execute(
        text("""
        SELECT timezone FROM properties WHERE id = :property_id AND tenant_id = :tenant_id
    """),
        params,
    )
    property_timezone = property_result.scalar_one_or_none()
    if property_timezone is None:
        # Same answer for an unknown ID and another tenant's property.
        raise PropertyNotFound()

    period_filter = ""
    if year is not None:
        params["start"], params["end"] = period_bounds(month, year, property_timezone)
        period_filter = "AND check_in_date >= :start AND check_in_date < :end"

    result = await db_session.execute(
        text(f"""
        SELECT currency, SUM(total_amount) AS total, COUNT(*) AS count
        FROM reservations
        WHERE property_id = :property_id AND tenant_id = :tenant_id
        {period_filter}
        GROUP BY currency
    """),
        params,
    )
    rows = result.mappings().all()
    if len(rows) > 1 or (rows and not rows[0]["currency"]):
        raise MixedCurrencies("Cannot sum multiple or unspecified currencies")
    total = rows[0]["total"] if rows else Decimal(0)
    return {
        "property_id": property_id,
        "tenant_id": tenant_id,
        "month": month,
        "year": year,
        "total": format(total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), ".2f"),
        "currency": rows[0]["currency"] if rows else "USD",
        "count": rows[0]["count"] if rows else 0,
        "timezone": property_timezone,
    }


async def calculate_monthly_revenue(
    property_id: str,
    month: int,
    year: int,
    tenant_id: str,
    db_session=None,
) -> Decimal:
    summary = await calculate_total_revenue(
        property_id, tenant_id, month, year, db_session
    )
    return Decimal(summary["total"])
