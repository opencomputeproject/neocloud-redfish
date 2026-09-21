# How out-of-band GPU fleet management works with Redfish — a technology primer

For readers who know GPU clusters but not the management plane. Everything here is what the fleet
evidence in this repository was measured against.

## 1. The two computers in every server

Every server has a second, always-on computer: the **baseboard management controller (BMC)**, an
ARM system-on-chip on the motherboard with its own firmware, its own network port and its own
power rail. It runs whether the host is on, off, wedged or has no operating system installed. It
reads the sensors, controls power, mounts virtual media, exposes a console, updates firmware and
speaks a management API. On the platforms in this fleet the BMC is Supermicro's own firmware, Dell's
iDRAC9, Lenovo's XCC, or AMI MegaRAC; on the NVIDIA HGX baseboard there is a second controller, the
**HMC** (hardware management controller, an OpenBMC build by NVIDIA), and on each BlueField DPU a third.

"Out-of-band" (OOB) means talking to those controllers over the management network, never to the
host. For a neocloud this is the only surface it can count on: the host OS may belong to a tenant,
may not be installed yet, or may be hung — and a hung host is exactly when the telemetry matters.

## 2. Redfish, in one page

**Redfish** (DMTF DSP0266) is the HTTPS/JSON API those controllers expose. It replaced IPMI's
binary-over-UDP commands with a REST tree rooted at `/redfish/v1/`:

```
/redfish/v1/                      service root: vendor, version, features, which services exist
  Systems/<id>                    the host: power state, BIOS, Processors, Memory, Storage
    Processors/<gpu>              a GPU is a Processor with ProcessorType=GPU
      ProcessorMetrics            utilization, PCIe errors, throttle durations, cache ECC
      EnvironmentMetrics          temperature, power, energy
      Ports/<n>/Metrics           NVLink ports and their counters
    Memory/<hbm>/MemoryMetrics    HBM ECC counts (LifeTime, CurrentPeriod)
  Chassis/<id>                    the box: Power/PowerSubsystem, Thermal/ThermalSubsystem, Sensors, Drives
  Managers/<id>                   the controllers themselves: the BMC, and any aggregated HMC
  UpdateService/FirmwareInventory every firmware component and its version
  TelemetryService/MetricReports  bulk metric reports (many values per GET)
  EventService                    push subscriptions, server-sent events
  AccountService, SessionService, CertificateService, ComponentIntegrity (SPDM attestation), LogServices
```

Three properties matter for everything else:

- **Schemas** (DSP8010) define each resource type and version, e.g. `ProcessorMetrics.v1_7_1`.
  Standard properties are the same on every vendor; anything vendor-specific lives under an `Oem`
  object (`Oem.Nvidia.RowRemapping`, `Oem.Dell.GPUResetRecommendedState`).
- **Message registries** (DSP8011 and OEM/OCP registries) give events and log entries a
  `MessageId` such as `Platform.1.0.SensorOverThreshold` so a client can key alerts on them; a
  free-text message is not alertable.
- **Query parameters** (`$expand`, `$select`, `excerpt`, `only`) decide how many HTTP requests a walk
  costs. A BMC that advertises `$expand` depth 3 answers an 8-GPU node in one or two GETs; one that
  advertises depth 1 forces a request per resource.

Redfish also gives the unauthenticated client exactly one thing: the service root. It tells you the
vendor, Redfish version, a chassis identifier and which services exist — enough to fingerprint and
identify a BMC before spending a credential, and nothing more (every data-bearing path returns 401).

## 3. Where the GPUs are: the accelerator management controller and aggregation

An 8-GPU HGX baseboard is a system of its own: 8 GPUs, 2 NVSwitches, 8 PCIe retimers, an FPGA,
a management NIC, and an ERoT (root of trust) per component. NVIDIA's HMC exposes all of it as a
Redfish tree — `Systems/HGX_Baseboard_0`, `Processors/GPU_SXM_1..8`, `Chassis/HGX_GPU_SXM_n`,
`Managers/HGX_BMC_0` — and generates 12 bulk **MetricReports** (`HGX_ProcessorMetrics_0`,
`HGX_MemoryMetrics_0`, `HGX_NVSwitchPortMetrics_0` …) with 11,609 values per node.

How that tree reaches the operator differs by OEM, and that difference is the central fact of this
profile:

| OEM | How the HGX tree is reached | Consequence |
|---|---|---|
| Supermicro | The host BMC **aggregates** the HMC tree into its own (`Managers/HGX_BMC_0` appears beside `Managers/1`; the 12 reports appear under the BMC's TelemetryService). One credential, one endpoint. | Full accelerator RAS agentlessly. |
| Dell iDRAC9 | Does **not** expose the HMC. Models the GPUs itself as `Processors/Video.Slot.*` with standard `ProcessorMetrics` plus `Oem.Dell` / `Oem.Nvidia`; bulk GPU reports through its own TelemetryService (licensed, off by default). | Most GPU metrics, no HBM ECC over Redfish, NVLink in OEM properties. |
| Lenovo XCC | No HMC surface; GPUs as `Processors/GPU1..8` with temperature/power sensors only. | Presence, temperature and power; no RAS. |
| NVIDIA DGX | Host BMC plus HMC on a forwarded port (TCP 18888). | Two endpoints. |

DMTF's DSP2090 (Aggregation Guidance for Compute Expansion Modules) and the OCP System GPU
Management workstream both point at the aggregated model. The OCP GPU & Accelerator Management
Interfaces spec (v1.1) names the two controllers the **AMC** (accelerator management controller — the HMC
here) and the **HMC** (hyperscaler management controller — the host BMC) and standardizes what flows
between them: PLDM over MCTP for inventory/sensors/firmware, Redfish for the operator-facing model,
SPDM for attestation.

## 4. Telemetry: three ways to get numbers out

1. **Walk the tree** (`GET` each `ProcessorMetrics`, `MemoryMetrics`, …). Universal, no license,
   cost proportional to resource count and `$expand` depth. Dell at depth 1: p50 6.7 s per 8-GPU node.
2. **Bulk MetricReports** (`TelemetryService/MetricReports/<name>`). One GET returns hundreds of
   `MetricValues`, each a `MetricProperty` URI (pointing back into the tree), a string `MetricValue`
   and, on the HMC, a per-value `Timestamp` and stale flag. Generated `OnRequest` by the HMC, so poll
   rate is the client's cost. Supermicro: p50 1.7 s per node for 1,060 series.
3. **Push** (`EventService` subscriptions, server-sent events, `MetricReport` event format).
   Advertised everywhere, the right long-term path, and where event storms during firmware pushes
   become the operational problem the hyperscalers describe.

A collector turns these into a metrics dialect (here Prometheus/OpenMetrics: `hgx_gpu_hbm_ecc_errors_total`,
`redfish_psu_health`) and the data quality rules are non-negotiable: values the controller flags
stale are dropped, `"NA"` means absent not zero, implausible values (a uint overflow) are dropped and
counted, ISO-8601 durations are parsed, and a missing subsystem is a finding (`hgx_up 0`), never a
collection error.

## 5. Health, events and logs

Every resource carries `Status.{Health, State}` (and may carry `Status.Conditions[]`, the active-fault
list). `State=Absent` on an empty PSU bay and `State=UnavailableOffline` on a device that left the bus
are the standard way to say "not there" — and where an implementation reports `Enabled/OK` instead,
the client has to infer from `PCIeInterface.LanesInUse=0`.

Faults also arrive as `LogEntry` records (`LogServices/EventLog/Entries`) with `Severity`, `Created`,
`MessageId`, `Message`, and optionally `OriginOfCondition` (which resource), `AdditionalDataURI`
(a CPER blob per the OCP RAS Requirements), and since Redfish 2026.2 a `VendorCode` — the standard
place for an NVIDIA XID/SXID code. Today those arrive as free text inside a generic
`ResourceEvent.1.0.ResourceErrorsDetected`; the OCP `AcceleratorFabric` registry and this repository's
`OCPAcceleratorRAS` draft give them neutral `MessageId`s.

## 6. Security plane

`AccountService` and `Role` define who can do what; a **ReadOnly** predefined role is the correct
monitoring credential and can be verified at the role. `SessionService` issues tokens (BMCs have
small session tables; a fleet collector uses basic auth or reuses sessions). `CertificateService`
manages TLS. `ComponentIntegrity` exposes **SPDM** attestation of each root of trust (13–21 ERoT/IRoT
members on an HGX node) — a scheduled pass/fail audit, not a metric. `SecureBoot` reports boot
integrity. `UpdateService.MultipartHttpPushUri` is the modern firmware push, and `FirmwareInventory`
is the fleet's component census: on HGX, 34 members, one per updatable part.

## 7. Interoperability profiles: how requirements become tests

A **Redfish Interoperability Profile** (DSP0272) is a JSON document that says, resource by resource
and property by property, what an implementation **must** (`Mandatory`), **should** (`Recommended`),
or must-if-present (`IfImplemented`) expose, with `UseCases` to scope requirements (e.g. only
`Processor`s whose `ProcessorType` is `GPU`) and `RequiredProfiles` to compose other profiles. The
DMTF **Redfish-Interop-Validator** reads a profile, walks a live service (or a recorded tree served
by a fake BMC) and emits pass/fail per requirement. OCP publishes its hardware-management
requirements in exactly this form, and OEMs already accept customer profiles as requirements
documents. That is why this repository is a profile and not a white paper: the same file is the
requirement, the procurement clause, and the acceptance test.

## 8. What the profile can and cannot reach

Redfish reaches the BMC, the aggregated accelerator controller, the chassis, and (through
`PowerEquipment`/`ThermalEquipment` on facility gear that speaks it) PDUs and CDUs. It does not
reach the host OS, container attribution, NCCL, the InfiniBand subnet manager, rack-scale NVLink
managed by NVIDIA NMX-C/GFM, or anything ClusterMAX grades that is a business process. The profile
says so explicitly, so the OCP reviewers are not asked where the SOC 2 control is.
