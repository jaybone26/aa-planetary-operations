# Verification — V1 0.1.0

Verified locally on September 29, 2026.

## Environment

- Python 3.12.14, Windows host, isolated virtual environment.
- Alliance Auth **5.4.0**, Django **5.2.17**, Django-ESI **9.10.0**, OR-Tools **9.15.6755**.
- The same test suite also passes with **Alliance Auth 5.0.0**, using the same other installed dependencies. This is a baseline compatibility check, not a matrix of every historic dependency combination.
- Real AA app registrations, ownership models, URL hooks, templates, and database migrations; test-only SQLite, in-memory Redis substitute and mocked ESI transport.

## Completed checks

- **36 automated tests passed** on both AA 5.4.0 and AA 5.0.0.
- Catalog coverage: all 83 commodities, every supported starting tier, acyclic tier dependencies and nonempty planet compatibility.
- Planning: shared recipe requirements, whole-batch rounding, import boundaries including lower-tier P4 ingredients, skill budgets, occupied colonies, multi-character use, P4 planet restrictions, per-day/week normalization, real gate expansion and disconnected-system rejection.
- Security/integration: AA template rendering, permissions, character ownership, token ownership/hash/scopes, active rather than trained skill levels, private saved-plan views/exports, CSRF and POST-only deletion, transaction-aware queue submission, worker failure handling, duplicate delivery handling, saved results with unavailable market data.
- Market: station/order-side filtering, all-page retrieval, cache reuse, order depth, minimum quantities, missing prices, partial-page failure, and rate-limit cooldown.
- Django model/template/URL/static-file checks passed without issues.
- Migration drift check passed; fresh AA test databases apply the real app migrations successfully.
- Python lint and formatting checks passed.
- Wheel and source distribution built successfully. The wheel was installed into a separate directory, its catalog/migrations/templates/static assets were checked, and all 36 tests passed against the installed package.
- Actual AA-rendered planner and production-result pages inspected in the in-app browser.

## Live public-data smoke test

The bundled catalog was compiled from official CCP SDE build **3552227**.

Using the public ESI market endpoint on **2026-09-29 at 22:38 UTC**, the application retrieved Jita 4-4 buy orders for Broadcast Nodes and valued six units at **11,748,000 ISK gross**, with six filled and zero unfilled. This is a historical verification snapshot, not a current price recommendation.

With three synthetic characters at IC V / CCU V and the documented default extraction assumptions, the engine found single-system layouts in Vale of the Silent for:

| Target | Import tier | Target per 24-hour pull | Colonies |
|---|---|---:|---:|
| Broadcast Node | P0 extraction | 6 | 7 |
| Wetware Mainframe | P0 extraction | 6 | 9 |
| Robotics | P0 extraction | 24 | 2 |
| Broadcast Node | Import P3/lower | 24 | 1 |
| Aqueous Liquids | P0 extraction | 144,000 | 1 |

These examples demonstrate solver behavior on the real catalog, not measured in-game extraction or a recommendation to deploy in those systems.

## Still requires the target AA server

- Real character SSO authorization with the deployment's EVE developer application.
- End-to-end execution on its existing Linux Celery worker and Redis/Valkey broker.
- Its production database and reverse-proxy configuration.
- In-game resource yield, pin placement/link capacity, sovereignty and POCO access, startup buffers, and actual hauling cadence.

No changes were made to a live AA installation or any EVE character. Use a staging installation first; the package is ready for that installation step.
