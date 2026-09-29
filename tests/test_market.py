from datetime import datetime, timezone

import pytest

from planetary_operations.esi import ESIUnavailable
from planetary_operations.market import order_book, valuate, value_quantity


def order(oid=1, price=100, volume=10, **kwargs):
    return dict(
        order_id=oid,
        is_buy_order=True,
        location_id=60003760,
        type_id=9848,
        volume_remain=volume,
        min_volume=1,
        price=price,
        duration=90,
        issued=datetime.now(timezone.utc).isoformat(),
        **kwargs,
    )


def test_pagination_station_filter_and_cache(requests_mock):
    url = "https://esi.evetech.net/latest/markets/10000002/orders/"
    other = order(2, price=1000)
    other["location_id"] = 60000001
    sell = order(3, price=2000)
    sell["is_buy_order"] = False
    requests_mock.get(
        url + "?order_type=buy&type_id=9848&page=1",
        json=[order(), other, sell],
        headers={"X-Pages": "2"},
    )
    requests_mock.get(
        url + "?order_type=buy&type_id=9848&page=2",
        json=[order(4, price=90, volume=20)],
        headers={"X-Pages": "2"},
    )
    book = order_book(9848)
    assert len(book["orders"]) == 2
    assert value_quantity(book, 15)["gross"] == "1450.00"
    assert value_quantity(book, 40)["unfilled"] == 10
    assert order_book(9848) == book
    assert requests_mock.call_count == 2


def test_minimum_volume():
    book = {
        "orders": [
            {"price": "100", "remaining": 50, "minimum": 20},
            {"price": "90", "remaining": 10, "minimum": 1},
        ]
    }
    assert value_quantity(book, 10)["gross"] == "900.00"


def test_absent_price_is_not_zero_value(requests_mock):
    requests_mock.get("https://esi.evetech.net/latest/markets/10000002/orders/", json=[])
    value = valuate({"product_id": 9848, "output": 10, "hours": 24})
    assert value["available"] is False
    assert value["unfilled"] == 10
    assert value["best_buy"] is None


def test_partial_pages_fail_closed(requests_mock):
    url = "https://esi.evetech.net/latest/markets/10000002/orders/"
    requests_mock.get(
        url + "?order_type=buy&type_id=9848&page=1", json=[order()], headers={"X-Pages": "2"}
    )
    requests_mock.get(url + "?order_type=buy&type_id=9848&page=2", status_code=503)
    with pytest.raises(ESIUnavailable):
        order_book(9848)


def test_rate_limit_stops_further_requests(requests_mock):
    requests_mock.get(
        "https://esi.evetech.net/latest/markets/10000002/orders/",
        status_code=429,
        headers={"Retry-After": "60"},
    )
    for _ in range(2):
        with pytest.raises(ESIUnavailable):
            order_book(9848)
    assert requests_mock.call_count == 1
