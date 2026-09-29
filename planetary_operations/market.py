"""Jita 4-4 station buy orders. Gross estimates are never described as profit."""

from datetime import datetime, timezone
from decimal import Decimal

from django.core.cache import cache

from . import esi

REGION = 10000002
STATION = 60003760


def order_book(type_id):
    key = f"planetary_operations:jita:{type_id}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    orders, page, pages, ttl = [], 1, 1, 300
    while page <= pages:
        data, headers = esi.get(
            f"markets/{REGION}/orders/", dict(order_type="buy", type_id=type_id, page=page)
        )
        try:
            next_pages = int(headers.get("X-Pages", 1))
            if not 1 <= next_pages <= 100 or (page > 1 and next_pages != pages):
                raise ValueError("Pagination changed")
            pages = next_pages
            for row in data:
                if (
                    row["is_buy_order"]
                    and row["location_id"] == STATION
                    and row["type_id"] == type_id
                    and row["volume_remain"] > 0
                ):
                    # Expired orders are excluded even if upstream cache retained them.
                    issued = datetime.fromisoformat(row["issued"].replace("Z", "+00:00"))
                    if (datetime.now(timezone.utc) - issued).total_seconds() >= row[
                        "duration"
                    ] * 86400:
                        continue
                    price = Decimal(str(row["price"]))
                    if not price.is_finite() or price <= 0:
                        raise ValueError("Invalid price")
                    orders.append(
                        dict(
                            id=row["order_id"],
                            price=str(price),
                            remaining=int(row["volume_remain"]),
                            minimum=int(row["min_volume"]),
                        )
                    )
        except (KeyError, TypeError, ValueError) as exc:
            raise esi.ESIUnavailable("ESI returned an incomplete market order book.") from exc
        ttl = min(ttl, esi.cache_seconds(headers))
        page += 1
    if len({r["id"] for r in orders}) != len(orders):
        raise esi.ESIUnavailable("Market pages changed during retrieval. Refresh again.")
    orders.sort(key=lambda row: Decimal(row["price"]), reverse=True)
    book = dict(orders=orders, fetched_at=datetime.now(timezone.utc).isoformat(), station=STATION)
    cache.set(key, book, ttl)
    return book


def value_quantity(book, quantity):
    remaining, gross = quantity, Decimal(0)
    for order in book["orders"]:
        amount = min(remaining, order["remaining"])
        if amount < min(order["minimum"], order["remaining"]):
            continue
        gross += amount * Decimal(order["price"])
        remaining -= amount
        if remaining == 0:
            break
    return dict(
        quantity=quantity,
        filled=quantity - remaining,
        unfilled=remaining,
        gross=str(gross.quantize(Decimal("0.01"))),
    )


def valuate(result):
    book = order_book(result["product_id"])
    pull = value_quantity(book, result["output"])
    gross = Decimal(pull["gross"])
    return dict(
        **pull,
        available=bool(book["orders"]),
        fetched_at=book["fetched_at"],
        station=STATION,
        best_buy=book["orders"][0]["price"] if book["orders"] else None,
        per_day=str(
            (gross * Decimal(24) / Decimal(str(result["hours"]))).quantize(Decimal("0.01"))
        ),
        per_week=str(
            (gross * Decimal(168) / Decimal(str(result["hours"]))).quantize(Decimal("0.01"))
        ),
        note="Gross station buy-order estimate. Day/week extrapolate this pull; future liquidity is not guaranteed. Excludes imports, taxes, fees and hauling costs.",
    )
