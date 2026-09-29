"""Read-only, process-local static data. Never stores user or token data."""

import json
from functools import lru_cache
from importlib.resources import files


@lru_cache(maxsize=1)
def catalog():
    return json.loads(
        files("planetary_operations").joinpath("data/catalog.json").read_text("utf-8")
    )


def commodity(type_id):
    return catalog()["commodities"][str(type_id)]
