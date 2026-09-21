# Live out-of-band evidence — 2026-09-20 (queried 21:50 PDT)

Source: the reference exporter 1.0.0 (GET-only, read-only BMC accounts), scraped by Grafana Alloy, remote-written
to Thanos, queried directly from the two sites' Thanos query endpoints. Every number below is a PromQL result, not an estimate.

## Coverage

| Site | Fleet | Platform (BMC / Redfish) | BMCs targeted | `redfish_up==1` | `hgx_up==1` | Continuous since | Series/node (avg) | Probe p50 / max |
|---|---|---|---:|---:|---:|---|---:|---|
| Site A | fleet A1 | Supermicro H14DSG-OD, HGX B200 — Supermicro BMC, Redfish 1.22.2 | 128 | 128 | 127 | 2026-09-12 (128/128 every day) | 996 | 1.68 s / 19.6 s |
| Site B | fleet B1 | Supermicro AS-A126GS-TNBR, HGX B200 — Redfish 1.22.2 | 15 | 15 | 15 | 2026-09-07 (25/25 every day) | 1,062 | 1.84 s / 3.43 s |
| Site B | fleet B2 | Dell PowerEdge XE9680, 8× H100 — iDRAC9 7.20.80.50, Redfish 1.20.1 | 10 | 10 | 0 (by design: no HMC surface) | 2026-09-07 | 432 | 6.70 s / 21.4 s |

- Metric families live: 66 (Site A), 77–79 (Site B, adds Dell NVMe SMART + GPU reset-recommended).
- Active series: 127,734 (Site A), 20,245 (Site B).
- Probe errors: 0 on every fleet; `redfish_probe_success==0`: none.
- HGX manager firmware bands in production: Site A 26.04-1-ga38 ×100, 25.05-1-ga35 ×27; Site B 26.04 ×13, 25.05 ×1, 25.02 ×1.
- HGX FirmwareInventory members per node: 34 on 25.05/26.04; 25 on 25.02 (norms are per firmware band, not per model).
- Fleet power visible OOB at Site A: 555.5 kW chassis-consumed (128 nodes), 309.7 kW GPU-tray.
- Dell probe cost is 4× Supermicro: iDRAC advertises `$expand MaxLevels=1`, so 8 GPUs are walked per resource. Supermicro advertises MaxLevels=3 + `excerpt` + `$select`.

## Findings the exporter is surfacing right now (alerts firing, 2026-09-20)

| Alert | Count | Evidence |
|---|---:|---|
| HGXTrayUnreachable (P1) | 1 | **A1-17**: `redfish_up 1`, `hgx_up 0`, host power `Off`, Chassis members 3 (normal 39), FirmwareInventory 19 (normal 66), HGX members 0. Second occurrence of the A1-69 signature (Aug 2026, undetected 9 days then); detected within 5 min this time. |
| HGXComponentsMissing (P1) | 1 | A1-17 (HGX members 0 vs 34 in its own 7-day history). A1-96 also at 25/34 with `hgx_report_missing{report="HGX_ProcessorGPMMetrics_0"}` — not yet alerting (30 m hold). |
| PSURedundancyLost (P1) | 11 nodes / 13 PSUs | Critical PSUs drawing 5 W input (dead supply, still enumerated): A1-02 bay4; A1-25–033 bay1 (A1-30, A1-31 bays 1+2); A1-123 bay1. Rack 4 has 8 of the 13 → likely a feed/PDU issue, not 8 coincident PSU failures. Site B: B1-15 bay 6 Critical (6 W input). |
| GPURemapBanksExhausted (P2) | 2 GPUs | A1-83 GPU6 (8 rows remapped, 2.64e9 correctable HBM ECC lifetime), A1-121 GPU7 (10 rows remapped, 101,597 correctable). Both are RMA candidates before a DBE occurs. |
| NVLinkPortsDown (P2) | 40 device rows / 5 nodes | A1-03, A1-96, A1-101, A1-107, A1-108: all 8 GPUs with ports down. A1-96 also shows all 8 GPUs at `LanesInUse 0` and A1-101 GPU3 at 0 — the "GPU fell off the bus" signature, visible with no host agent. |
| RunnerSilent (P1) | 1 | A second Site A runner retired on 2026-09-11 is still listed in the deadman rule; the single remaining runner scrapes 128/128. A rule to remove, not an outage. |

Other RAS state visible fleet-wide, not alerting by design:

- Uncorrectable HBM ECC lifetime > 0: 1 GPU (A1-92 GPU8 = 12). Correctable > 0: 7 GPUs (604 … 2.64e9).
- Rows remapped > 0: 10 GPUs; remap-bank availability below "max": high 1, partial 8, none 2.
- NVSwitch unintentional link-down counters: up to 978 per switch (A1-74, A1-70, A1-32, A1-10; B1-11 971) — lifetime counters, useful as `increase()` only.
- PCIe fatal/nonfatal GPU errors > 0: none. Drive failure predicted: none. Dell `GPUResetRecommended`: none. NVMe SMART critical warning (Dell bulk report): none.
- HMC-stale values dropped this scrape (Site A): 11.
- Tier disagreement (OOB says 8 GPUs healthy, host sees fewer): cannot be evaluated on tenant nodes (no in-band) — exactly the population OOB exists for.

## What this says about a profile

1. The two-surface model is real. The Supermicro BMC aggregates the NVIDIA HMC natively (12 `HGX_*` MetricReports); Dell iDRAC exposes no HMC managers or reports but models the same GPUs as `Processors/Video.Slot.*` with `ProcessorMetrics` + `Oem.Dell`/`Oem.Nvidia`; Lenovo XCC exposes GPU temp/power only. A single flat "GPU server profile" cannot be Mandatory-satisfiable across the three.
2. Liveness of the accelerator subsystem must be a first-class, standard signal. Two detached-tray incidents in six weeks, both invisible to every other monitoring path.
3. HBM ECC LifeTime counts are present on the HMC path and absent on iDRAC9 7.20 (`MemoryMetrics` = `BandwidthPercent` + `OperatingSpeedMHz` only; `GPUStatistics` report defined but empty). That is the single most important OEM gap to name.
4. Row remapping, NVLink error counters, throttle reasons, stale-value flags are all `Oem.Nvidia` — they carry the fleet's real RAS load and have no standard home.
5. Member counts, report inventories and firmware-component counts vary by HMC firmware band inside one SKU. A profile must forbid clients from hardcoding them and require stable, discoverable collections.
6. Fleet-scale polling cost is dominated by `$expand` depth: MaxLevels=1 makes an 8-GPU walk 4× slower and forces per-resource GETs. The protocol floor should require `$expand` with `$levels>=2` (or bulk MetricReports) for accelerator subtrees.
