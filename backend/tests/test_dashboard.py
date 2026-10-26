from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import jwt
import pytest
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from app.config import settings
from app.core import auth
from app.models.auth import AuthenticatedUser
from app.services import cache
from conftest import login_as

URL = '/api/v1/dashboard/summary'
MARCH = {"property_id": "prop-001", "month": 3, "year": 2024}


@pytest.mark.asyncio
async def test_both_clients_warm_cache_and_reload_in_both_orders(api):
    headers = {tenant: await login_as(api, tenant) for tenant in ['a', 'b']}
    for sequence in [('a', 'b', 'a', 'b'), ('b', 'a', 'b', 'a')]:
        cache.redis_client.values.clear()
        for tenant in sequence:
            r = await api.get(URL, params=MARCH, headers={**headers[tenant], 'X-Simulated-Tenant': 'tenant-b' if tenant == 'a' else 'tenant-a'})
            assert r.status_code == 200, r.text
            data = r.json()
            assert data['total_revenue'] == ('2250.00' if tenant == 'a' else '0.00')
            assert data['reservations_count'] == (4 if tenant == 'a' else 0)
            assert isinstance(data['total_revenue'], str)
            assert r.headers['cache-control'] == 'no-store'


@pytest.mark.asyncio
async def test_only_own_properties_are_listed_and_foreign_property_is_404(api):
    a, b = await login_as(api), await login_as(api, 'b')
    properties_a = (await api.get('/api/v1/dashboard/properties', headers=a)).json()
    properties_b = (await api.get('/api/v1/dashboard/properties', headers=b)).json()
    assert {p['id'] for p in properties_a} == {'prop-001', 'prop-002', 'prop-003'}
    assert {p['id'] for p in properties_b} == {'prop-001', 'prop-004', 'prop-005'}
    assert next(p for p in properties_b if p['id'] == 'prop-001')['name'] == 'Mountain Lodge Beta'
    for header, property_ in [(a, 'prop-004'), (b, 'prop-002'), (a, 'missing')]:
        response = await api.get(URL, params={**MARCH, 'property_id': property_}, headers=header)
        assert response.status_code == 404
        assert response.json() == {'detail': 'Property not found'}


@pytest.mark.asyncio
async def test_periods_all_properties_and_annual_totals(api):
    a, b = await login_as(api), await login_as(api, 'b')
    for headers, totals in [(a, {'prop-001': '2250.00', 'prop-002': '4975.50', 'prop-003': '6100.50'}),
                            (b, {'prop-001': '0.00', 'prop-004': '1776.50', 'prop-005': '3256.00'})]:
        for property_, expected in totals.items():
            response = await api.get(URL, params={**MARCH, 'property_id': property_}, headers=headers)
            assert response.status_code == 200, response.text
            assert response.json()['total_revenue'] == expected
    for params, total in [({'property_id': 'prop-001', 'year': 2024}, '2250.00'),
                           ({'property_id': 'prop-001'}, '2250.00'),
                           ({**MARCH, 'month': 2}, '0.00'), ({**MARCH, 'year': 2025}, '0.00')]:
        response = await api.get(URL, params=params, headers=a)
        assert response.status_code == 200
        assert response.json()['total_revenue'] == total


@pytest.mark.parametrize('params', [
    {'property_id': 'prop-001', 'month': 3},
    {**MARCH, 'month': 0}, {**MARCH, 'month': 13}, {**MARCH, 'year': 10000},
    {**MARCH, 'month': 'bad'}, {**MARCH, 'property_id': ''},
])
@pytest.mark.asyncio
async def test_invalid_periods_are_rejected(api, params):
    response = await api.get(URL, params=params, headers=await login_as(api))
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_mixed_currencies_are_never_added_or_mislabeled(api, db):
    async with db.get_session() as session:
        await session.execute(text("UPDATE reservations SET currency='EUR' WHERE id='res-dec-1'"))
        await session.commit()
    response = await api.get(URL, params=MARCH, headers=await login_as(api))
    assert response.status_code == 422
    assert not cache.redis_client.values
    async with db.get_session() as session:
        await session.execute(text("UPDATE reservations SET currency='EUR'"))
        await session.commit()
    response = await api.get(URL, params=MARCH, headers=await login_as(api))
    assert response.json()['currency'] == 'EUR'
    assert response.json()['total_revenue'] == '2250.00'


@pytest.mark.asyncio
async def test_db_failure_is_503_not_fabricated_or_cached(api, monkeypatch):
    monkeypatch.setattr(cache, 'calculate_total_revenue', AsyncMock(side_effect=OperationalError('query', {}, Exception('offline'))))
    response = await api.get(URL, params=MARCH, headers=await login_as(api))
    assert response.status_code == 503
    assert not cache.redis_client.values


@pytest.mark.asyncio
async def test_missing_tenant_fails_closed(api):
    async def no_tenant():
        return AuthenticatedUser(id='user', email='user@example.com', permissions=[], cities=[], is_admin=False, tenant_id=None)
    api._transport.app.dependency_overrides[auth.authenticate_request] = no_tenant
    response = await api.get(URL, params=MARCH)
    assert response.status_code == 403


@pytest.mark.parametrize('kind', ['missing', 'garbage', 'unsigned', 'expired', 'wrong-key', 'no-exp', 'no-tenant'])
@pytest.mark.asyncio
async def test_bad_tokens_do_not_fall_back_to_tenant_a(api, kind):
    payload = {'id': 'user-sunset', 'email': 'sunset@propertyflow.com', 'aud': 'authenticated',
               'app_metadata': {'tenant_id': 'tenant-a'}, 'exp': datetime.now(timezone.utc) + timedelta(hours=1)}
    if kind == 'expired': payload['exp'] = datetime.now(timezone.utc) - timedelta(seconds=1)
    if kind == 'no-exp': payload.pop('exp')
    if kind == 'no-tenant': payload.pop('app_metadata')
    token = jwt.encode(payload, 'wrong-secret-key-that-is-long-enough' if kind == 'wrong-key' else settings.secret_key, algorithm='HS256')
    if kind == 'unsigned': token = jwt.encode(payload, '', algorithm='none')
    if kind == 'garbage': token = 'mock-token-123'
    headers = {} if kind == 'missing' else {'Authorization': 'Bearer ' + token}
    response = await api.get(URL, params=MARCH, headers=headers)
    assert response.status_code == (403 if kind == 'no-tenant' else 401), response.text


@pytest.mark.asyncio
async def test_expired_auth_cache_entry_is_revalidated(api):
    headers = await login_as(api)
    assert (await api.get(URL, params=MARCH, headers=headers)).status_code == 200
    for entry in auth.auth_cache.values(): entry['expires_at'] = 0
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(auth.jwt, 'decode', lambda *a, **kw: (_ for _ in ()).throw(auth.JWTError('expired')))
        response = await api.get(URL, params=MARCH, headers=headers)
    assert response.status_code == 401


@pytest.mark.parametrize('email,password', [
    ('sunset@propertyflow.com', 'bad'), ('ocean@propertyflow.com', 'bad'),
    ('candidate@propertyflow.com', 'anything'), ('unknown@example.com', 'anything'),
])
@pytest.mark.asyncio
async def test_invalid_passwords_and_unlisted_challenge_users_are_rejected(api, email, password):
    response = await api.post('/api/v1/auth/login', json={'email': email, 'password': password})
    assert response.status_code == 401
