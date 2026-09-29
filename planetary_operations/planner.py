"""Pure planning engine: recipes, constrained deployment, and material movements.

All quantities describe a steady-state pull. Startup needs one pipeline fill;
extractor yields and link reserves are explicit assumptions, never ESI facts.
"""

from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from math import ceil, floor, isfinite
from time import monotonic

from ortools.sat.python import cp_model

from .catalog import catalog, commodity


class PlanningError(ValueError):
    pass


@dataclass(frozen=True)
class Character:
    id: int
    name: str
    ic: int
    ccu: int
    reserved: int = 0
    occupied: tuple[int, ...] = ()

    @property
    def slots(self):
        return max(0, 1 + self.ic - self.reserved)


@dataclass(frozen=True)
class Config:
    product: int
    start_tier: int
    region: int
    quantity: int = 24
    hours: float = 24
    raw_per_hour: int = 6000
    heads: int = 5
    reserve_percent: int = 15
    max_jumps: int = 2

    def validate(self):
        if str(self.product) not in catalog()["commodities"]:
            raise PlanningError("Choose a PI commodity.")
        tier = commodity(self.product)["tier"]
        if not 0 <= self.start_tier <= max(0, tier - 1):
            raise PlanningError("The import tier must be below the finished product tier.")
        if not isfinite(self.hours) or not 1 <= self.hours <= 336:
            raise PlanningError("Pull duration must be between 1 and 336 hours.")
        if not 1 <= self.quantity <= 10_000_000 or not 1 <= self.raw_per_hour <= 1_000_000:
            raise PlanningError("Output and extraction quantities are outside supported limits.")
        if not 1 <= self.heads <= 10 or not 5 <= self.reserve_percent <= 50:
            raise PlanningError("Use 1–10 extractor heads and a 5–50% link reserve.")
        if not 0 <= self.max_jumps <= 5:
            raise PlanningError("Nearby-system search is limited to 0–5 stargate jumps.")


# Recipe expansion: aggregate shared ingredients before rounding whole batches.
def expand(config):
    config.validate()
    required = Counter({config.product: config.quantity})
    imports, tasks, totals = {}, [], []
    for tier in range(commodity(config.product)["tier"], -1, -1):
        for type_id in sorted(k for k in required if commodity(k)["tier"] == tier):
            item, demand = commodity(type_id), required[type_id]
            if config.start_tier > 0 and tier <= config.start_tier:
                imports[type_id] = demand
                continue
            if tier == 0:
                capacity = floor(config.raw_per_hour * config.hours)
                count = ceil(demand / capacity)
                production = demand
            else:
                batches = ceil(demand / item["output"])
                capacity = floor(config.hours * 3600 / item["seconds"])
                if capacity < 1:
                    raise PlanningError(f"Pull too short for {item['name']}.")
                count, production = ceil(batches / capacity), batches * item["output"]
                for input_id, amount in item["inputs"].items():
                    required[int(input_id)] += batches * amount
            totals.append(
                dict(
                    type_id=type_id,
                    name=item["name"],
                    tier=tier,
                    required=demand,
                    produced=production,
                    surplus=production - demand,
                    facilities=count,
                )
            )
            remaining = production if tier == 0 else batches
            for _ in range(count):
                cycles = min(capacity, remaining)
                remaining -= cycles
                tasks.append(
                    dict(
                        type_id=type_id,
                        name=item["name"],
                        tier=tier,
                        planets=item["planets"],
                        cpu=item["cpu"] + (110 * config.heads if tier == 0 else 0),
                        power=item["power"] + (550 * config.heads if tier == 0 else 0),
                        quantity=cycles if tier == 0 else cycles * item["output"],
                        inputs={int(k): v * cycles for k, v in item["inputs"].items()},
                        schematic=item.get("schematic"),
                        cycles=cycles if tier else None,
                    )
                )
            if len(tasks) > 240:
                raise PlanningError(
                    "This output needs more than 240 facilities. Reduce the output target."
                )
    return tasks, imports, sorted(totals, key=lambda t: (t["tier"], t["name"]))


def neighborhood(systems, root, jumps):
    distance, queue = {root: 0}, deque([root])
    while queue:
        current = queue.popleft()
        if distance[current] >= jumps:
            continue
        for neighbor in systems[current]["neighbors"]:
            if neighbor in systems and neighbor not in distance:
                distance[neighbor] = distance[current] + 1
                queue.append(neighbor)
    return distance


# Each slot belongs to one character. Its location selects an actual planet type
# in an actual system; distinct planet IDs are assigned after constraint solving.
def fit(tasks, characters, systems, config, seconds):
    slots = [character for character in characters for _ in range(character.slots)]
    locations = [
        (system_id, planet_type)
        for system_id, system in sorted(systems.items())
        for planet_type in sorted({p["type"] for p in system["planets"]})
    ]
    if not slots or not locations:
        return None, "INFEASIBLE"
    model = cp_model.CpModel()
    used = [model.new_bool_var(f"used_{s}") for s in range(len(slots))]
    assigned = [
        [model.new_bool_var(f"t{t}_s{s}") for s in range(len(slots))] for t in range(len(tasks))
    ]
    located = [
        [model.new_bool_var(f"s{s}_l{location_index}") for location_index in range(len(locations))]
        for s in range(len(slots))
    ]
    for row in assigned:
        model.add(sum(row) == 1)
    previous = {}
    for t, task in enumerate(tasks):
        signature = (task["type_id"], task["quantity"])
        if signature in previous:
            before = previous[signature]
            model.add(
                sum(s * assigned[before][s] for s in range(len(slots)))
                <= sum(s * assigned[t][s] for s in range(len(slots)))
            )
        previous[signature] = t
    for s, character in enumerate(slots):
        center = catalog()["centers"][str(character.ccu)]
        model.add(sum(located[s]) == used[s])
        model.add(sum(assigned[t][s] for t in range(len(tasks))) >= used[s])
        model.add(
            sum(tasks[t]["cpu"] * assigned[t][s] for t in range(len(tasks))) + 3600 * used[s]
            <= floor(center["cpu"] * (100 - config.reserve_percent) / 100) * used[s]
        )
        model.add(
            sum(tasks[t]["power"] * assigned[t][s] for t in range(len(tasks))) + 700 * used[s]
            <= floor(center["power"] * (100 - config.reserve_percent) / 100) * used[s]
        )
        for t, task in enumerate(tasks):
            model.add(
                assigned[t][s]
                <= sum(
                    located[s][location_index]
                    for location_index, (_, kind) in enumerate(locations)
                    if kind in task["planets"]
                )
            )
        # Identical slots within a character are interchangeable.
        if s and slots[s - 1].id == character.id:
            model.add(used[s] <= used[s - 1])
    for character in characters:
        indexes = [s for s, c in enumerate(slots) if c.id == character.id]
        for location_index, (system_id, planet_type) in enumerate(locations):
            available = sum(
                p["type"] == planet_type and p["id"] not in character.occupied
                for p in systems[system_id]["planets"]
            )
            model.add(sum(located[s][location_index] for s in indexes) <= available)
    active_systems = []
    for system_id in systems:
        active = model.new_bool_var(f"system_{system_id}")
        location_vars = [
            located[s][location_index]
            for s in range(len(slots))
            for location_index, (sid, _) in enumerate(locations)
            if sid == system_id
        ]
        model.add_max_equality(active, location_vars)
        active_systems.append(active)
    model.minimize((len(slots) + 1) * sum(active_systems) + sum(used))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.01, seconds)
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 0
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, solver.status_name(status)
    colonies, taken = [], defaultdict(set)
    for s, character in enumerate(slots):
        if not solver.value(used[s]):
            continue
        location_index = next(
            location_index
            for location_index in range(len(locations))
            if solver.value(located[s][location_index])
        )
        system_id, planet_type = locations[location_index]
        planet = next(
            p
            for p in systems[system_id]["planets"]
            if p["type"] == planet_type
            and p["id"] not in taken[character.id]
            and p["id"] not in character.occupied
        )
        taken[character.id].add(planet["id"])
        facilities = [dict(tasks[t]) for t in range(len(tasks)) if solver.value(assigned[t][s])]
        colonies.append(
            dict(
                id=len(colonies),
                character_id=character.id,
                character=character.name,
                planet=planet,
                planet_type=catalog()["planet_types"][str(planet_type)],
                system_id=system_id,
                system=systems[system_id]["name"],
                ccu=character.ccu,
                cpu=3600 + sum(t["cpu"] for t in facilities),
                power=700 + sum(t["power"] for t in facilities),
                capacity=catalog()["centers"][str(character.ccu)],
                facilities=facilities,
            )
        )
    return colonies, solver.status_name(status)


def deploy(tasks, characters, config, systems=None, time_limit=25):
    if not characters or len({c.id for c in characters}) != len(characters):
        raise PlanningError("Select at least one distinct character.")
    if len(characters) > 10:
        raise PlanningError("V1 supports up to ten characters in one plan.")
    for c in characters:
        if not 0 <= c.ic <= 5 or not 0 <= c.ccu <= 5 or not 0 <= c.reserved <= 1 + c.ic:
            raise PlanningError("Invalid or missing character skills/colony reservations.")
    if not sum(c.slots for c in characters):
        raise PlanningError("No free colonies remain on the selected characters.")
    if systems is None:
        systems = {
            int(k): v
            for k, v in catalog()["systems"].items()
            if v["region"] == config.region and v["planets"] and int(k) not in {30000142, 30002187}
        }
    deadline, unknown = monotonic() + time_limit, False
    required_types = [set(t["planets"]) for t in tasks]
    signatures = set()
    # Prove single-system feasibility first. Equivalent type inventories need
    # only one solve when there are no occupied planets to distinguish them.
    for system_id, system in sorted(systems.items()):
        kinds = Counter(p["type"] for p in system["planets"])
        if any(not r.intersection(kinds) for r in required_types):
            continue
        signature = tuple(sorted(kinds.items()))
        if not any(c.occupied for c in characters) and signature in signatures:
            continue
        if monotonic() >= deadline:
            raise PlanningError(
                "Search timed out during the one-system check. Reduce output or narrow the region."
            )
        colonies, status = fit(
            tasks, characters, {system_id: system}, config, min(1, deadline - monotonic())
        )
        if colonies:
            return colonies, dict(
                systems=1, single_system_proven=True, status=status, root=system_id
            )
        if status == "INFEASIBLE":
            signatures.add(signature)
        else:
            unknown = True
    if unknown:
        raise PlanningError(
            "Some one-system layouts need more search time; necessity of expansion is unproven. Reduce output or ask the administrator to increase the search budget."
        )
    # Expand through real stargates, staying within the selected region.
    seen = set()
    for jumps in range(1, config.max_jumps + 1):
        for root in sorted(systems):
            nearby = neighborhood(systems, root, jumps)
            key = tuple(sorted(nearby))
            if len(key) < 2 or key in seen:
                continue
            seen.add(key)
            kinds = {p["type"] for sid in nearby for p in systems[sid]["planets"]}
            if any(not r.intersection(kinds) for r in required_types):
                continue
            if monotonic() >= deadline:
                raise PlanningError(
                    "Nearby-system search timed out. No feasible layout was established."
                )
            colonies, status = fit(
                tasks,
                characters,
                {sid: systems[sid] for sid in nearby},
                config,
                min(2, deadline - monotonic()),
            )
            if colonies:
                return colonies, dict(
                    systems=len({c["system_id"] for c in colonies}),
                    single_system_proven=False,
                    single_system_infeasible=True,
                    status=status,
                    root=root,
                    radius=jumps,
                    note="First feasible nearby network; regional minimum is not proven.",
                )
    raise PlanningError(
        "No layout found within the chosen jump radius and available colony budgets. Reduce output, add characters, or import a higher tier."
    )


# Material movements: use local supplies first, then explicit character/planet transfers.
def logistics(colonies, imports, product):
    supplies, demands = defaultdict(list), []
    for colony in colonies:
        for task in colony["facilities"]:
            supplies[task["type_id"]].append([colony["id"], task["quantity"]])
            for type_id, quantity in task["inputs"].items():
                demands.append((colony["id"], type_id, quantity))
    for type_id, quantity in imports.items():
        supplies[type_id].append([None, quantity])
    movements = Counter()
    # Reserve all local consumption before any colony exports its surplus.
    pending = []
    for target, type_id, quantity in demands:
        for source in supplies[type_id]:
            if source[0] == target:
                amount = min(quantity, source[1])
                movements[(target, target, type_id)] += amount
                source[1] -= amount
                quantity -= amount
        pending.append((target, type_id, quantity))
    for target, type_id, quantity in pending:
        for source in supplies[type_id]:
            amount = min(quantity, source[1])
            if amount:
                movements[(source[0], target, type_id)] += amount
                source[1] -= amount
                quantity -= amount
        if quantity:
            raise PlanningError("Material balance failed; no partial plan has been saved.")
    transfers = []
    for (source, target, type_id), quantity in movements.items():
        if not quantity:
            continue
        transfers.append(
            dict(
                source=source,
                target=target,
                type_id=type_id,
                name=commodity(type_id)["name"],
                quantity=quantity,
                volume=round(quantity * commodity(type_id)["volume"], 2),
                kind="Local route"
                if source == target
                else "Import"
                if source is None
                else "Haul / transfer",
            )
        )
    for type_id, remaining in supplies.items():
        for source, quantity in remaining:
            if quantity:
                transfers.append(
                    dict(
                        source=source,
                        target=None,
                        type_id=type_id,
                        name=commodity(type_id)["name"],
                        quantity=quantity,
                        volume=round(quantity * commodity(type_id)["volume"], 2),
                        kind="Finished output" if type_id == product else "Surplus",
                    )
                )
    return transfers


def hauling_routes(transfers, colonies, systems):
    """Shortest regional stargate paths; never invent wormhole connections."""
    routes = {}
    for movement in transfers:
        source, target = movement["source"], movement["target"]
        if source is None or target is None:
            movement["route"] = "Supply / collection location chosen by pilot"
            continue
        start, end = colonies[source]["system_id"], colonies[target]["system_id"]
        key = (start, end)
        if key not in routes:
            previous, queue = {start: None}, deque([start])
            while queue and end not in previous:
                current = queue.popleft()
                for neighbor in systems[current]["neighbors"]:
                    if neighbor in systems and neighbor not in previous:
                        previous[neighbor] = current
                        queue.append(neighbor)
            if end not in previous:
                raise PlanningError(
                    "No regional stargate route exists for a required material transfer."
                )
            route, current = [], end
            while current is not None:
                route.append(current)
                current = previous[current]
            routes[key] = list(reversed(route))
        path = routes[key]
        movement["jumps"] = len(path) - 1
        movement["route"] = " → ".join(systems[sid]["name"] for sid in path)
        movement["route_ids"] = path


def build_plan(config, characters, systems=None, time_limit=25):
    tasks, imports, totals = expand(config)
    colonies, search = deploy(tasks, characters, config, systems, time_limit)
    transfers = logistics(colonies, imports, config.product)
    route_systems = (
        systems
        if systems is not None
        else {int(k): v for k, v in catalog()["systems"].items() if v["region"] == config.region}
    )
    hauling_routes(transfers, colonies, route_systems)
    output = next(t["produced"] for t in totals if t["type_id"] == config.product)
    # Conservative pad service estimate: shared 10,000 m3 for inputs + outputs.
    for colony in colonies:
        volume = sum(
            t["quantity"] * commodity(t["type_id"])["volume"]
            + sum(q * commodity(k)["volume"] for k, q in t["inputs"].items())
            for t in colony["facilities"]
        )
        colony["service_hours"] = round(min(config.hours, 8000 / max(volume, 1) * config.hours), 2)
    return dict(
        version=1,
        product=commodity(config.product)["name"],
        product_id=config.product,
        output=output,
        per_day=output * 24 / config.hours,
        per_week=output * 168 / config.hours,
        hours=config.hours,
        colonies=colonies,
        materials=totals,
        logistics=transfers,
        imports=[
            dict(type_id=k, name=commodity(k)["name"], quantity=v) for k, v in imports.items()
        ],
        search=search,
        catalog_sha256=catalog()["sha256"],
        assumptions=[
            "Steady-state production after initial pipeline fill.",
            f"{config.raw_per_hour:,} raw units/hour per {config.heads}-head ECU; verify in game.",
            f"{config.reserve_percent}% CPU/power reserved for links; exact placement must be checked in game.",
            "One launchpad per colony; service at or before the listed interval.",
            "Verify sovereignty, docking, POCO access and route safety before deployment.",
        ],
    )
