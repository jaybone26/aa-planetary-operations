# Architecture

## Modules

| Module | Responsibility |
|---|---|
| `catalog.py`, `data/catalog.json` | Versioned, read-only commodity, recipe, planet, region and gate data |
| `planner.py` | Recipe expansion, CP-SAT placement, material balance and regional hauling paths |
| `characters.py` | AA ownership checks, scoped token selection, current PI skill/colony reads |
| `esi.py` | Bounded HTTP reads and shared ESI cooldown |
| `market.py` | Paginated Jita 4-4 buy order snapshots and depth-aware gross estimates |
| `models.py`, `migrations/` | Owned skill snapshots and private saved plan inputs/results |
| `forms.py`, `views.py`, `urls.py` | Validated user inputs, ownership-isolated access and exports |
| `tasks.py` | Existing AA Celery worker integration, result persistence and failure reporting |
| `auth_hooks.py` | AA sidebar permission and URL registration |
| `tools/build_catalog.py` | Reproducible compiler for official CCP JSONL SDE archives |

## Planning sequence

1. Validate selection, tier, duration, extraction assumptions, output size and search limits.
2. Aggregate ingredient demand in descending tier order. Round shared ingredients only after all parents contribute their demand. Stop recipe expansion at the selected import boundary.
3. Split required batches into discrete processors using cycles available during the pull. Split P0 requirements into ECUs using assumed extraction capacity. Each task carries planet restrictions, CPU/power and exact input/output quantities.
4. Give each character `1 + active Interplanetary Consolidation − occupied colonies` slots, or full capacity in replacement mode. Keep their Command Center Upgrades level and occupied planet IDs separate.
5. Test single systems with OR-Tools CP-SAT. Every task is assigned once. Each used slot selects a system/planet type, respects the owning character's command-center budget plus launchpad/link reserve, and consumes one distinct available planet for that character. Different characters may each colonize the same planet.
6. Skip resource-incompatible systems. Equivalent planet-type inventories share infeasibility proofs only when occupied planet IDs cannot distinguish them. A solver timeout is never an infeasibility proof.
7. Only after all single-system candidates are excluded or proven infeasible, expand through regional stargate neighborhoods in increasing radius. Minimize systems first, colonies second within each candidate set. Report the first feasible nearby network without claiming a global minimum.
8. Allocate concrete planet IDs, reserve local material consumption, then generate inter-colony movements. Material shortages abort the plan. Record remaining product/surplus, shortest regional gate paths and average-volume pad-service estimates.
9. Fetch all pages of the finished product's regional buy orders; retain Jita 4-4 orders, respect remaining volume and minimum fills, and save timestamped gross estimates.

## Ownership and failures

Views require AA login and `planetary_operations.basic_access`. Every plan query is constrained to `owner=request.user`. Form choices are built from the user's AA ownership records; submitted IDs are validated against those choices. CSRF protects mutation endpoints; deletes, refreshes and price updates require POST.

Tokens must match user, character, owner hash and both required scopes. Character ownership is rechecked after private ESI reads, and selected IDs are rechecked before a completed plan is saved. Active skill levels are used. Failed reads are never substituted with zero skills or an empty colony list.

Queued plan creation commits before task submission. A conditional status transition prevents duplicate tasks from calculating the same plan. Task failures become readable saved-plan errors. Market failure leaves the production plan intact. Abandoned tasks can be released with the recovery command after a worker outage.

Snapshots contain skills, occupied planet IDs and timestamps, never OAuth tokens. Export contains plan settings, character planning capacities and results only. Saved plans are historical snapshots and do not continuously reserve colonies or update themselves.

## Deliberate V1 bounds

Ten selected characters; at most 240 individual facilities; 1–336 hours per pull; 0–5 regional gate jumps from a search center; bounded solver time. The user supplies one common average extraction assumption. Exact pin coordinates, production simulation over time, financial profit, sovereignty/POCO permissions, and global multi-system optimality are outside this implementation's claims.
