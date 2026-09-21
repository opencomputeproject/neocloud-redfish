# Telemetry coverage: Redfish out-of-band vs. in-band agents

**Author:** an operator SRE · **Date:** 2026-08-14, updated with the Site B sweep 2026-08-17 ·
condensed from the original research note  and the
21 Aug 2026 field report *Agentless BMC Management*. Fleet-internal addresses removed.

**Key finding:** on NVIDIA HGX platforms whose BMC aggregates the HMC, the Redfish collector replaces
most of DCGM (57 GPU metric names) and all of `ipmi_exporter` (23), adds NVLink / NVSwitch / retimer
error surfaces DCGM never had, and gives a coarse subset (5 fields) of the NVMe SMART model. It cannot
replace OS-level metrics (~390 `node_*` names), per-container attribution, XID-as-metric, or GPU-presence truth.

## Per-brand depth, one live machine per brand (BMC credential only, no SSH, no agent)

| Platform | GPU errors (ECC, NVLink, throttle) | GPU usage (util, temp, power) | Chassis (PSU, fans, temps, drive wear) | Notes |
|---|---|---|---|---|
| Supermicro HGX B200 (fleet A1 ×128, fleet B1 ×15) | ✅ full | ✅ full | ✅ full | 12 `HGX_*` MetricReports, 771–1,130 series/node, all 8 GPUs; 9 extra chassis power-history rollup reports on the AS-A126GS-TNBR |
| Dell XE9680 H100 (fleet B2 ×10) | 🟠 most | 🟠 most | ✅ | Per-GPU `ProcessorMetrics` on demand (`Oem.Dell` NVLink/violation/reset-recommended, `Oem.Nvidia` activity/throttle reasons); bulk `TelemetryService` was licensed (iDRAC9 Datacenter) but `ServiceEnabled=false` until one ops PATCH; HBM ECC not exposed; `SMUtilizationPercent` seen as a uint overflow → plausibility bounds are mandatory in a collector |
| Lenovo SR680a V3 H200 (fleet B3 ×8) | ❌ none | 🟡 temp + power + presence only | ✅ (8 PSUs in/out watts, 32 DIMMs) | XCC does not aggregate the HMC: no HGX managers, 7 generic platform reports; GPUs appear as `Processors/GPU1..8` (`ProcessorType=GPU`, no health) and `GPUn_Temp/Power` chassis sensors. The one fleet where DCGM is the only source of GPU faults |
| PCIe GPU servers: MSI S337 (4× RTX 4090), Gigabyte G493 (H100 NVL), Supermicro 4124GO (HGX A100) | ❌ | ❌ | ✅ | No HMC tray (A100-generation HGX predates the HMC Redfish surface). AMI MegaRAC roots advertise `ComponentIntegrity`/`Fabrics` with nothing behind them |
| Any Redfish BMC | — | — | ✅ baseline | Liveness, chassis thermals/fans, PSU health, drive wear/failure-predicted, DIMM/CPU census — reaches tenant, unprovisioned, wedged and powered-off nodes (~⅓ of a fleet) |

## Equivalence map (DCGM → out-of-band)

| In-band today | Out-of-band equivalent |
|---|---|
| `DCGM_FI_DEV_GPU_TEMP` / `MEMORY_TEMP` | `EnvironmentMetrics`/HGX sensor temperatures per GPU and HBM |
| `DCGM_FI_DEV_POWER_USAGE` / `TOTAL_ENERGY_CONSUMPTION` | per-GPU power and energy sensors |
| `DCGM_FI_DEV_SM_CLOCK` | `ProcessorMetrics.OperatingSpeedMHz` |
| `DCGM_FI_PROF_SM_ACTIVE/OCCUPANCY/PIPE_*` | `Oem.Nvidia` GPM activity percentages |
| `DCGM_FI_DEV_ECC_*`, `*_REMAPPED_ROWS`, `ROW_REMAP_FAILURE` | `MemoryMetrics.LifeTime.*ECCErrorCount` (standard); `Oem.Nvidia.RowRemapping.*`, `RowRemappingFailed` (OEM) |
| `DCGM_FI_DEV_PCIE_REPLAY_COUNTER`, `PCIE_LINK_GEN/WIDTH` | `ProcessorMetrics.PCIeErrors.ReplayCount`, `PCIeInterface.{PCIeType,LanesInUse,MaxLanes}` |
| `DCGM_FI_DEV_POWER/THERMAL_VIOLATION` | `ProcessorMetrics.{PowerLimit,ThermalLimit}ThrottleDuration` (+ `Oem.Nvidia` HW/SW violation durations, `ThrottleReasons`) |
| `DCGM_FI_PROF_NVLINK_RX/TX_BYTES`, `NVLINK_*_ERROR_COUNT` | `PortMetrics.RX/TXBytes`, `RXErrors` (standard); `Oem.Nvidia` link-down / recovery / symbol / BER counters, plus the NVSwitch side DCGM never sees |
| `DCGM_FI_DEV_XID_ERRORS` | ❌ free text in the HGX `EventLog` (`ResourceEvent.1.0.ResourceErrorsDetected`) — logs, not metrics |
| `DCGM_FI_DEV_FB_USED/FREE`, `ENC/DEC_UTIL`, GPU presence | ❌ no equivalent (BMC reported 8 healthy GPUs on a node with 4 on the bus) |
| `ipmi_*` | `redfish_*` platform tier — strict superset |
| `nvme_*` SMART / OCP log pages / risk score (74) | `Drive.PredictedMediaLifeLeftPercent`, `FailurePredicted`, health, capacity, identity (5); Dell adds NVMe SMART via the `NVMeSMARTData` report |

## What out-of-band adds that in-band never had

- Coverage of tenant, unprovisioned, wedged and powered-off nodes.
- Accelerator-subsystem liveness (`hgx_up`): tray detachment detection (A1-69 went 9 days dark in Aug 2026; A1-17 detected within 5 minutes on 2026-09-20).
- NVSwitch-internal error counters, per-device BER, retimer faults, HSC rail power/temperature.
- PSU line voltage and input-vs-output watts, drive failure prediction where `nvme-cli` can never run.
- ERoT/IRoT SPDM attestation (`ComponentIntegrity`, 13–21 members per HGX node) as a scheduled audit.
