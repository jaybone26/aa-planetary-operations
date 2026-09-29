# Development

Run these commands from the source repository root.

Python 3.11+ and an ordinary virtual environment:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[test]'
python -m pytest
python -m ruff check .
python -m ruff format --check .
python -m django check --settings=tests.settings --tag=models --tag=templates --tag=urls --tag=staticfiles
python -m django makemigrations --check --dry-run --settings=tests.settings --skip-checks
python -m build
```

Tests use real AA apps and migrations with SQLite, mocked ESI responses and an in-memory Redis substitute. No EVE credentials, running Redis server, or external worker is needed for tests. The test settings must never be used as deployment settings.

See [VERIFICATION.md](../VERIFICATION.md) for the environment and checks completed for this build. See [ARCHITECTURE.md](../ARCHITECTURE.md) for the module map and planning constraints.
