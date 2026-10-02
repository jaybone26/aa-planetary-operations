"""Small ESI transport, with timeouts, public caching, and shared cooldowns."""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from django.conf import settings
from django.core.cache import cache


class ESIUnavailable(RuntimeError):
    pass


def get(path, params=None, access_token=None):
    if cache.get("planetary_operations:esi_cooldown"):
        raise ESIUnavailable("ESI is rate limited. Try again after its cooldown.")
    headers = {
        "User-Agent": getattr(
            settings, "PLANETARY_OPERATIONS_USER_AGENT", "AA-Planetary-Operations/0.1.1"
        ),
        "Accept": "application/json",
    }
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"
    try:
        response = requests.get(
            "https://esi.evetech.net/latest/" + path.lstrip("/"),
            params=params,
            headers=headers,
            timeout=(5, 20),
        )
        if (
            response.status_code in (420, 429)
            or int(response.headers.get("X-Esi-Error-Limit-Remain", 100)) < 5
        ):
            delay = int(
                response.headers.get(
                    "Retry-After", response.headers.get("X-Esi-Error-Limit-Reset", 60)
                )
            )
            cache.set("planetary_operations:esi_cooldown", True, max(1, min(delay, 3600)))
        response.raise_for_status()
        return response.json(), response.headers
    except (requests.RequestException, ValueError) as exc:
        # Never include response bodies, request headers or token material.
        raise ESIUnavailable(
            "ESI data is unavailable. Reauthorize the character if this persists."
        ) from exc


def cache_seconds(headers):
    try:
        return max(
            1,
            min(
                300,
                int(
                    (
                        parsedate_to_datetime(headers["Expires"]) - datetime.now(timezone.utc)
                    ).total_seconds()
                ),
            ),
        )
    except (KeyError, ValueError, TypeError):
        return 60
