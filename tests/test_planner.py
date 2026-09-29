from collections import Counter

import pytest

from planetary_operations.catalog import catalog, commodity
from planetary_operations.planner import Character, Config, PlanningError, build_plan, expand


def system(sid, types, neighbors=()):
    return dict(
        id=sid,
        name=f"System {sid}",
        region=1,
        neighbors=list(neighbors),
        planets=[
            dict(id=sid * 100 + i, type=t, name=f"Planet {i}", index=i) for i, t in enumerate(types)
        ],
    )


def test_complete_catalog():
    assert Counter(c["tier"] for c in catalog()["commodities"].values()) == {
        0: 15,
        1: 15,
        2: 24,
        3: 21,
        4: 8,
    }
    for item in catalog()["commodities"].values():
        assert item["planets"]
        for input_id in item["inputs"]:
            assert commodity(input_id)["tier"] < item["tier"]


def test_robotics_expansion_and_shared_rounding():
    tasks, imports, totals = expand(Config(9848, 0, 1, quantity=3))
    assert not imports
    amounts = {t["type_id"]: t for t in totals}
    assert amounts[9848]["produced"] == 3
    assert amounts[3689]["required"] == 10
    assert amounts[9836]["required"] == 10
    assert sum(t["tier"] == 0 for t in tasks) == 4


def test_import_cutoff_keeps_lower_tier_p4_ingredients():
    _, imports, totals = expand(Config(2869, 3, 1, quantity=1))
    assert imports
    assert all(commodity(k)["tier"] <= 3 for k in imports)
    assert any(commodity(k)["tier"] == 1 for k in imports)
    assert len(totals) == 1


def test_factory_restricted_to_barren_or_temperate():
    cfg = Config(2867, 3, 1, quantity=1)
    with pytest.raises(PlanningError):
        build_plan(cfg, [Character(1, "Main", 5, 5)], {1: system(1, [13])})
    result = build_plan(cfg, [Character(1, "Main", 5, 5)], {1: system(1, [2016])})
    assert result["search"]["systems"] == 1
    assert result["output"] == 1


def test_zero_ccu_cannot_afford_launchpad():
    with pytest.raises(PlanningError):
        build_plan(Config(2268, 0, 1), [Character(1, "Main", 0, 0)], {1: system(1, [2016])})


def test_multi_character_colony_limits_and_balance():
    cfg = Config(9848, 0, 1, quantity=24, raw_per_hour=12000)
    chars = [Character(i, f"Alt {i}", 0, 5) for i in range(1, 5)]
    result = build_plan(cfg, chars, {1: system(1, [2016, 2015, 11, 12])}, time_limit=10)
    assert len({c["character_id"] for c in result["colonies"]}) > 1
    assert max(Counter(c["character_id"] for c in result["colonies"]).values()) == 1
    for c in result["colonies"]:
        assert c["cpu"] <= c["capacity"]["cpu"] * 0.85
        assert c["power"] <= c["capacity"]["power"] * 0.85
    assert sum(m["quantity"] for m in result["logistics"] if m["kind"] == "Finished output") == 24


def test_reserved_and_occupied_colonies_are_respected():
    with pytest.raises(PlanningError):
        build_plan(Config(2268, 0, 1), [Character(1, "Main", 0, 5, 1)], {1: system(1, [2016])})
    with pytest.raises(PlanningError):
        build_plan(
            Config(2268, 0, 1), [Character(1, "Main", 1, 5, 1, (100,))], {1: system(1, [2016])}
        )


def test_pull_normalization_and_integer_batches():
    cfg = Config(9848, 2, 1, quantity=4, hours=48)
    result = build_plan(cfg, [Character(1, "Main", 5, 5)], {1: system(1, [2016])})
    assert result["output"] == 6
    assert result["per_day"] == 3
    assert result["per_week"] == 21


def test_expands_only_when_one_system_cannot_supply_resources():
    systems = {1: system(1, [2016], [2]), 2: system(2, [2015], [1])}
    result = build_plan(Config(9848, 0, 1, quantity=3), [Character(1, "Main", 5, 5)], systems)
    assert result["search"]["systems"] == 2
    assert result["search"]["single_system_infeasible"]
    assert any(m.get("jumps") == 1 for m in result["logistics"])
    with pytest.raises(PlanningError):
        build_plan(
            Config(9848, 0, 1, quantity=3, max_jumps=0), [Character(1, "Main", 5, 5)], systems
        )


def test_disconnected_systems_do_not_invent_a_route():
    systems = {1: system(1, [2016]), 2: system(2, [2015])}
    with pytest.raises(PlanningError):
        build_plan(Config(9848, 0, 1, quantity=3), [Character(1, "Main", 5, 5)], systems)


def test_entire_catalog_expands_for_every_import_tier():
    for item in catalog()["commodities"].values():
        for tier in range(max(1, item["tier"])):
            tasks, imports, totals = expand(Config(item["id"], tier, 1, quantity=1))
            assert tasks
            assert all(commodity(k)["tier"] <= tier for k in imports)
            assert sum(t["produced"] for t in totals if t["type_id"] == item["id"]) >= 1


@pytest.mark.parametrize(
    "config",
    [
        Config(9848, 3, 1),
        Config(9848, 0, 1, hours=float("nan")),
        Config(9848, 0, 1, quantity=0),
        Config(9848, 0, 1, heads=11),
    ],
)
def test_invalid_configs(config):
    with pytest.raises(PlanningError):
        expand(config)
