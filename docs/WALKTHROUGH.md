# Loom walkthrough outline (about 6 minutes)

The [full silent walkthrough is recorded (6:51)](evidence/walkthrough-silent.mp4). Add your voice-over using the [matching chapter timestamps and narration draft](VOICEOVER.txt).

Record the application window and the relevant code. The assignment specifically requires a Loom video; this outline and the supporting browser recording do not claim to replace a published Loom URL.

## 0:00–0:40 — Reproduce and set expectations

“This is a debugging fix to the existing PropertyFlow application. I tested both supplied accounts. Before the fix, both got USD 1,000 and three bookings for property 001. That was wrong: Sunset should get USD 2,250 across four bookings, while Ocean's distinct property with the same ID has no bookings.”

Show `docs/evidence/before.json`, then the two rows in `database/seed.sql` that share the property ID. Explain that property identity includes the tenant.

## 0:40–1:30 — Explain and demonstrate tenant isolation

Show the original cache key in the parent commit and the new key in `backend/app/services/cache.py`. Explain the versioned tenant/property/period key and the validation of cached identity. Show tenant predicates in both property and reservation SQL.

Log in as Sunset using the assignment credentials. Show the three Sunset properties and March's USD 2,250. Log out; log in as Ocean. Select Mountain Lodge Beta, which is also `prop-001`. Show USD 0 and zero bookings. Refresh, select it again, and show the same result. Sunset's names must not appear in the Ocean dropdown.

## 1:30–2:35 — Explain the month boundary

Show `res-tz-1` in `database/seed.sql`: February 29 at 23:30 UTC. Explain that it is March 1 at 00:30 in Paris, so the USD 1,250 belongs to March.

Show `period_bounds` in `backend/app/services/reservations.py`, especially local `ZoneInfo` boundaries, UTC conversion, and the half-open SQL interval. Explain that Paris changes offset within March, so the end boundary is 22:00 UTC. Mention December rollover, leap-year and New York DST tests.

Switch back to Sunset. Change March to February and show zero; restore March and show USD 2,250. Select **Show full year** and show the annual report.

## 2:35–3:30 — Explain exact money and currencies

Show the three seeded amounts `333.333`, `333.333`, and `333.334`. Their exact sum is 1,000. Explain why rounding each booking first loses a cent.

Show PostgreSQL `SUM(NUMERIC)`, Decimal `ROUND_HALF_UP`, and the API decimal string. Show the UI string formatter: no float or JavaScript rounding. Explain that the half-cent regression proves the rounding rule, and that mixed currencies return an error because there is no exchange-rate model.

## 3:30–4:25 — Explain the hidden database failure

Show the original pool's legacy settings, synchronous `QueuePool`, and the original hard-coded mock totals. Explain that the UI looked successful even though the database path was broken.

Show the repaired `DATABASE_URL` async pool, shared instance, correct session lifecycle, and the removed mock fallback. Show the regression requiring 503 on a database outage. Explain Redis-down behavior: real database calculation, never fabricated data.

## 4:25–5:15 — Explain auth and UI follow-through

Show that tenant comes from verified authentication, never a request header or a default tenant. Missing tenant is 403; foreign property is 404. Mention rejected unsigned/expired tokens, auth-cache expiry, password validation, and local fixture credentials being confined to challenge mode.

Explain that the selector now comes from the database, the fake growth figure was removed, and stale async responses cannot replace the newly selected property/period. Mention the corrected local-session response shape that browser testing exposed.

## 5:15–6:00 — Show verification and finish

Run the README test command with the local test database URL and show the passing result. Run `npm run build` from `frontend` or show the captured successful output. Briefly open the regression tests and point out coverage of both tenant orders, financial rounding, DST, currency handling, and outage behavior.

“The fixes keep the existing architecture and original sample data. Revenue is assigned to the local check-in period; money is rounded once at the reporting boundary. The solution and verification steps are in the fork.”

Copy the published Loom share URL into the submission form or assignment email, alongside the fork URL. The submission destination and email-based deadline must come from the original email; they are not present in the repository.
