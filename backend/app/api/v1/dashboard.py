import logging
from typing import Annotated

from app.core.auth import authenticate_request
from app.models.auth import AuthenticatedUser
from app.services.cache import get_revenue_summary
from app.services.reservations import MixedCurrencies, PropertyNotFound, list_properties
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()
logger = logging.getLogger(__name__)


def require_tenant(user: AuthenticatedUser):
    if not user.tenant_id:
        raise HTTPException(403, "Tenant context required")
    return user.tenant_id


@router.get("/dashboard/properties")
async def get_dashboard_properties(
    response: Response,
    current_user: Annotated[AuthenticatedUser, Depends(authenticate_request)],
):
    tenant_id = require_tenant(current_user)
    response.headers["Cache-Control"] = "no-store"
    try:
        return await list_properties(tenant_id)
    except (SQLAlchemyError, OSError):
        logger.exception("Property database unavailable")
        raise HTTPException(503, "Property data temporarily unavailable")


@router.get("/dashboard/summary")
async def get_dashboard_summary(
    response: Response,
    property_id: Annotated[str, Query(min_length=1)],
    current_user: Annotated[AuthenticatedUser, Depends(authenticate_request)],
    month: Annotated[int | None, Query(ge=1, le=12)] = None,
    year: Annotated[int | None, Query(ge=1, le=9998)] = None,
):
    tenant_id = require_tenant(current_user)
    if month is not None and year is None:
        raise HTTPException(422, "Year is required with month")
    response.headers["Cache-Control"] = "no-store"
    try:
        data = await get_revenue_summary(property_id, tenant_id, month, year)
    except PropertyNotFound:
        raise HTTPException(404, "Property not found")
    except MixedCurrencies as error:
        raise HTTPException(422, str(error))
    except (SQLAlchemyError, OSError):
        logger.exception("Revenue database unavailable")
        raise HTTPException(503, "Revenue data temporarily unavailable")
    return {
        "property_id": data["property_id"],
        "total_revenue": data["total"],
        "currency": data["currency"],
        "reservations_count": data["count"],
        "month": month,
        "year": year,
        "timezone": data["timezone"],
    }
