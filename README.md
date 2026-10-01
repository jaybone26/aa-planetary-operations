![Version](https://img.shields.io/badge/version-0.1.0-blue)
![Alliance Auth](https://img.shields.io/badge/Alliance_Auth-v5-blue)
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Django](https://img.shields.io/badge/Django-5.2-green)
[![License](https://img.shields.io/badge/license-MIT-green)](https://github.com/jaybone26/aa-planetary-operations/blob/HEAD/LICENSE)
![Status](https://img.shields.io/badge/status-staging-orange)

# AA Planetary Operations for Alliance Auth

Plan your planetary industry across your main and alts, build the production network, and see its Jita buy value per pull.

---

## Contents

- [Features](#features)
- [Upcoming](#upcoming)
- [Highlights](#highlights)
- [Installation](#installation)
  - [Step 1 — Install the package](#step-1--install-the-package)
  - [Step 2 — Configure Alliance Auth](#step-2--configure-alliance-auth)
  - [Step 3 — Configure ESI access](#step-3--configure-esi-access)
  - [Step 4 — Run migrations and collect static files](#step-4--run-migrations-and-collect-static-files)
  - [Step 5 — Set up permissions](#step-5--set-up-permissions)
  - [Step 6 — Authorize characters and build a plan](#step-6--authorize-characters-and-build-a-plan)
- [Settings](#settings)
- [Using the planner](#using-the-planner)
- [Translations](#translations)
- [License and credits](#license-and-credits)

## Features

- **Main and alt planning** — combine up to ten AA-authenticated characters in one operation.
- **Automatic PI skill reads** — use active skill levels and existing colonies to determine available capacity.
- **P0 through P4** — choose any of the 83 PI commodities as your finished product.
- **Import tiers** — extract from P0 or start with supplied P1, P2, or P3 materials.
- **Region selection** — use real planet types, resources, recipes, and stargate connections from CCP's static data.
- **One system first** — try single-system layouts before expanding into nearby systems.
- **Character assignments** — fit colonies and facilities within each character's skill limits.
- **Build sheets** — see each planet, command-center level, extractor, processor, and required material.
- **Logistics plans** — get import quantities, local routes, character handoffs, hauling volumes, and regional gate paths.
- **Extraction schedules** — set the pull duration, output target, assumed extraction yield, and extractor head count.
- **Jita buy valuation** — estimate gross ISK per pull, day, and week from Jita 4-4 buy orders and available order volume.
- **Saved operations** — keep private plans, adjust a copy, refresh prices, or export the build sheet.

## Upcoming

Future possibilities beyond V1:

- Discord alerts.
- Alliance-wide collaborative production and suppliers.
- Advanced POCO tools.
- Historical production and market analytics.

## Highlights

### Characters and operation planner

Select your authenticated characters and configure the production chain in one place.

![AA Planetary Operations — characters and planner](https://raw.githubusercontent.com/jaybone26/aa-planetary-operations/HEAD/docs/images/planner.png)

### Production overview

Review estimated output, deployment size, and the Jita valuation status for a saved operation.

![AA Planetary Operations — saved operation overview](https://raw.githubusercontent.com/jaybone26/aa-planetary-operations/HEAD/docs/images/operation.png)

*Screenshots show a local demonstration using sample characters. Market pricing is unavailable in the pictured preview.*

## Installation

> **Requirements:** Alliance Auth v5, Python 3.11+, and your existing Auth database, Redis/Valkey, and Celery worker.
>
> Version 0.1.0 is ready for staging evaluation. Install it directly into your Alliance Auth virtual environment. Complete a real SSO authorization and worker run on your server before rollout.

### Step 1 — Install the package

Activate the virtual environment used by your Alliance Auth installation, then install from [PyPI](https://pypi.org/project/aa-planetary-operations/):

```shell
python -m pip install aa-planetary-operations==0.1.0
```

### Step 2 — Configure Alliance Auth

Add the app in your Auth project's `settings/local.py`:

```python
INSTALLED_APPS += [
    'planetary_operations',
]
```

Set a User-Agent that identifies your deployment and administrator contact:

```python
PLANETARY_OPERATIONS_USER_AGENT = "AA-Planetary-Operations/0.1.0 (your administrator contact)"
PLANETARY_OPERATIONS_SEARCH_SECONDS = 30
```

The package includes its PI and universe catalog. A separate SDE app or initial data download is not required.

### Step 3 — Configure ESI access

Enable the following scopes on the EVE developer application used by your Auth installation:

| Scope | Purpose |
| :--- | :--- |
| `esi-skills.read_skills.v1` | Read each character's active PI skill levels. |
| `esi-planets.manage_planets.v1` | Read existing colonies and occupied planet IDs. |

Keep your existing AA SSO callback URL. Users grant these scopes through **Authorize a character’s PI access**. The plugin only reads ESI, including the scope named “manage”; it makes no in-game changes.

### Step 4 — Run migrations and collect static files

From your Auth project directory:

```shell
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py check
```

Restart your existing Auth web processes and Celery workers through your normal service manager.

Plan calculations use the task `planetary_operations.tasks.calculate_plan` on the existing AA worker. No additional Celery Beat schedule is required.

### Step 5 — Set up permissions

Grant this permission to the appropriate AA group or state:

| Permission | Description | Access |
| :--- | :--- | :--- |
| `planetary_operations.basic_access` | Can use Planetary Operations | Opens the app and allows users to create and manage their own plans. |

The sidebar entry appears for permitted users. Saved plans are private to their owner.

### Step 6 — Authorize characters and build a plan

1. Open **Planetary Operations** from the AA sidebar.
2. Attach any missing alts to your AA account.
3. Use **Authorize a character’s PI access** for each character.
4. Select the characters, finished product, import tier, and region.
5. Set the pull duration and output target. Enter an extraction estimate based on your in-game program.
6. Select **Build & save plan**. The result page updates when the worker finishes.

## Settings

Optional settings in `settings/local.py`:

| Setting | Description | Default |
| :--- | :--- | :--- |
| `PLANETARY_OPERATIONS_USER_AGENT` | Identifies your application to ESI. Set it to include your administrator contact. | `AA-Planetary-Operations/0.1.0` |
| `PLANETARY_OPERATIONS_SEARCH_SECONDS` | Solver search budget in seconds, limited to 5–120. | `30` |

## Using the planner

Existing colonies reduce available slots by default. Enable **Plan a replacement for my existing colonies** if you intend to rebuild them in game. Saved plans are alternative layouts; they do not reserve colony slots against each other.

**Read estimates as steady-state targets.** The planner checks factory cycles and fitting budgets against your requested output. Future extraction yield, resource hotspots, exact link placement, startup buffers, sovereignty, and POCO access need an in-game check. Nearby-system results report a feasible network without claiming a global regional optimum.

**Jita estimates are gross value.** Imported materials, taxes, fees, and hauling costs are excluded. Unfilled buy-order volume is reported. Day/week figures extrapolate the current pull valuation; future liquidity can change.

## Translations

The V1 interface is currently in English. Translation support is not included in this release.

## License and credits

Source code is available under the [MIT License](https://github.com/jaybone26/aa-planetary-operations/blob/HEAD/LICENSE).

Built for [Alliance Auth](https://allianceauth.readthedocs.io/) using [Django-ESI](https://django-esi.readthedocs.io/) token management, CCP's [Static Data Export](https://developers.eveonline.com/docs/services/static-data/), and the [EVE ESI API](https://esi.evetech.net/ui/).

EVE Online and its game data belong to CCP. See [NOTICE.md](https://github.com/jaybone26/aa-planetary-operations/blob/HEAD/NOTICE.md).
