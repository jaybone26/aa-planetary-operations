"""Compile CCP's JSONL SDE archive into the small, versioned planner catalog.

Usage: python tools/build_catalog.py /path/to/sde.zip
Obtain the archive from https://developers.eveonline.com/static-data/ .
No network access or archive extraction is performed by this command.
"""

import hashlib
import json
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path


def compile_catalog(archive, destination):
    with zipfile.ZipFile(archive) as z:

        def rows(name):
            with z.open(name + ".jsonl") as source:
                for line in source:
                    yield json.loads(line)

        types = {r["_key"]: r for r in rows("types")}
        dogma = {
            r["_key"]: {a["attributeID"]: a["value"] for a in r.get("dogmaAttributes", [])}
            for r in rows("typeDogma")
        }
        recipes = list(rows("planetSchematics"))
        ids = {v["_key"] for r in recipes for v in r["types"]}
        outputs = {v["_key"]: r for r in recipes for v in r["types"] if not v["isInput"]}

        def tier(type_id):
            if type_id not in outputs:
                return 0
            return 1 + max(tier(v["_key"]) for v in outputs[type_id]["types"] if v["isInput"])

        commodities = {}
        for type_id in sorted(ids):
            t = types[type_id]
            product = dict(
                id=type_id,
                name=t["name"]["en"],
                tier=tier(type_id),
                volume=t["volume"],
                inputs={},
                output=1,
                seconds=0,
            )
            if type_id in outputs:
                r = outputs[type_id]
                product.update(
                    schematic=r["_key"],
                    seconds=r["cycleTime"],
                    inputs={str(v["_key"]): v["quantity"] for v in r["types"] if v["isInput"]},
                    output=next(v["quantity"] for v in r["types"] if not v["isInput"]),
                    planets=sorted({int(dogma[p][1632]) for p in r["pins"]}),
                    cpu=int(dogma[r["pins"][0]][49]),
                    power=int(dogma[r["pins"][0]][15]),
                )
            else:
                product.update(
                    planets=sorted(
                        {
                            int(d[1632])
                            for d in dogma.values()
                            if d.get(709) == type_id and 1632 in d
                        }
                    ),
                    cpu=400,
                    power=2600,
                )
            if not product["planets"]:
                raise ValueError(f"No planet types for {type_id}")
            commodities[str(type_id)] = product

        planet_types = {int(d[1632]) for d in dogma.values() if 1632 in d}
        regions = {str(r["_key"]): r["name"]["en"] for r in rows("mapRegions")}
        systems = {
            str(r["_key"]): dict(
                id=r["_key"],
                name=r["name"]["en"],
                region=r["regionID"],
                security=r.get("securityStatus", 0),
                neighbors=[],
                planets=[],
            )
            for r in rows("mapSolarSystems")
        }
        for gate in rows("mapStargates"):
            systems[str(gate["solarSystemID"])]["neighbors"].append(
                gate["destination"]["solarSystemID"]
            )
        for p in rows("mapPlanets"):
            if p["typeID"] in planet_types:
                s = systems[str(p["solarSystemID"])]
                s["planets"].append(
                    dict(
                        id=p["_key"],
                        type=p["typeID"],
                        index=p["celestialIndex"],
                        name=f"{s['name']} {p['celestialIndex']}",
                    )
                )
        # These six upgrade capacities are read from the command-center dogma.
        centers = {}
        for type_id, t in types.items():
            d = dogma.get(type_id, {})
            if t.get("groupID") == 1027 and d.get(1632) == 2016:
                centers[str(int(d.get(633, 0)))] = dict(cpu=int(d[48]), power=int(d[11]))
        catalog = dict(
            schema=1,
            generated_at=datetime.now(timezone.utc).isoformat(),
            source="CCP EVE Online Static Data Export",
            sha256=hashlib.file_digest(open(archive, "rb"), "sha256").hexdigest(),
            commodities=commodities,
            centers=centers,
            regions=regions,
            systems=systems,
            planet_types={str(p): types[p]["name"]["en"] for p in sorted(planet_types)},
        )
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(catalog, separators=(",", ":")), encoding="utf-8")
        print(f"Saved {len(commodities)} commodities, {len(systems)} systems to {destination}")


if __name__ == "__main__":
    compile_catalog(
        Path(sys.argv[1]),
        Path(__file__).resolve().parents[1] / "planetary_operations/data/catalog.json",
    )
