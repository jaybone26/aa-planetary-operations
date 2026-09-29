# Operating guide

[Back to the README](../README.md)

## Using the planner

1. Attach your alts to your AA account, then authorize PI access for each.
2. Select the characters together. Existing colonies reduce their available slots by default.
3. Choose a product and import tier. For recipes with ingredients below the selected import tier, those lower-tier ingredients are imported too.
4. Set your pull duration and target output. Enter the **average raw output per hour of one ECU with the chosen number of heads**, based on your in-game program. The default 6,000 is a placeholder assumption.
5. Build and save. AA's worker refreshes private data, calculates the network, and reads Jita prices. The result page updates when complete.
6. Follow each colony's fitting and material instructions. Rebuild a saved plan with **Adjust & build a copy** when skills, characters, or assumptions change.

**Replacement mode:** “Plan a replacement for my existing colonies” uses full skill-based capacity and permits those planet IDs again. You must remove/rebuild the existing colonies yourself. Saved plans do not reserve capacity against other saved plans; treat each as an alternative operation.

## Understand the estimates

This is a production planning tool, not an automatic in-game colony builder.

- ESI does not supply future resource extraction yield or hotspot predictions. A common user-entered ECU rate is used across the plan; validate every assigned resource in game, then lower the assumption if needed.
- Factory quantities use whole batches and actual schematic cycle times. Surplus is explicit. Output is the requested, capacity-checked production target, rounded to whole batches; V1 does not maximize output automatically.
- The plan describes **steady state after pipeline fill**. Initial extraction, factory startup, hauling delays, and the first pull need additional lead time or prefilled intermediate buffers.
- Each colony budgets one launchpad and a configurable percentage of CPU/power for links. Exact pin placement, link lengths, link upgrades and extraction hotspots need an in-game check. A mathematical fit is not a verified physical layout.
- The recommended pad-service interval is a conservative average-volume estimate using 8,000 of its 10,000 m³. Bursty extraction and batch arrivals still need inventory checks. Factory tasks show how many cycles to run per pull; stop or throttle surplus production beyond that target.
- Within a candidate system set, the solver prioritizes fewer systems, then fewer colonies. The first feasible single-system result proves the system-count minimum of one. Multi-system search returns the first feasible nearby network; it does **not** prove the global regional optimum. Timeouts are reported explicitly, never interpreted as proof of impossibility.
- Stargate routes are restricted to the selected region. Wormhole connections, jump bridges, security preferences, POCO access, and sovereignty are not modeled. Verify the site and travel route before building. Jita and Amarr are excluded from deployment candidates.
- Gross ISK uses only buy orders located at station ID **60003760**, region **10000002**. Regional orders at other stations are intentionally excluded, even if their order range extends to Jita.
- Order pages must all load successfully. Insufficient volume and minimum-fill restrictions are shown as unfilled units. Missing prices are unavailable, not zero. Day/week ISK extrapolate the current pull valuation, assuming replenished liquidity; they are not executable future quotes.
- Costs for imported materials, taxes, market fees and hauling are excluded. **Gross value is not profit.** Price retrieval failures do not discard a valid build sheet.

## Static-data updates

The bundled catalog was generated from CCP SDE build **3552227**. Its SHA-256 and generation time are embedded in `catalog.json`, and the catalog hash is stored in every plan. This catalog includes all recipe tiers and 8,490 system records; deployment uses only systems with supported planets.

To update from a downloaded official JSON Lines SDE archive:

```sh
python tools/build_catalog.py /path/to/eve-online-static-data-BUILD-jsonl.zip
python -m pytest
python -m build
```

The compiler reads the archive without extracting its paths. Resource-to-planet compatibility comes from SDE extractor restrictions; factory restrictions, fitting costs and command-center capacities come from schematic pins and dogma. Resource abundance is not inferred from the SDE. Restart workers and web processes after installing a catalog update.

## Troubleshooting

- **Authorize PI access:** each selected character needs both scopes and an owner-hash-matching token belonging to the logged-in AA user.
- **No free colonies:** choose other characters, or enable replacement mode if you intend to rebuild existing colonies.
- **No feasible layout / timeout:** reduce output, add characters, import a higher tier, change region, or raise the nearby-system radius. Administrators may raise the search budget to at most 120 seconds.
- **Queued indefinitely:** check the existing AA Celery worker and broker. After resolving a worker outage, release abandoned plans older than 15 minutes with `python manage.py po_recover_plans`, then build a copy.
- **Prices unavailable:** refresh later. ESI error/rate-limit cooldowns and short-lived public-price caching are respected. The UI shows the snapshot time.
