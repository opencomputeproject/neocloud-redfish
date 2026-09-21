#!/usr/bin/env python3
"""Generate the OCP Neocloud Redfish Interoperability Profile family and registry.

    python build_profiles.py        # writes profiles/*.v0_6_0.json and registries/*.json

Edit this file, not the JSON. Every requirement carries a Purpose that names its evidence:
  [live]  a Thanos query against the Site A/Site B fleets on 2026-09-20 (docs/evidence/live-evidence-2026-09-20.md)
  [rec]   a recorded BMC tree in the reference collector tests/fixtures/redfish (docs/evidence/recorded-tree-evidence.md)
  [sweep] operator SRE research's unauthenticated fleet sweep (docs/research/bmc-unauthenticated-endpoints.md)
  [gap]   the ClusterMAX gap analysis (docs/gap-analysis.md)
"""
import json
import os

VERSION = "0.6.0"
VFILE = VERSION.replace(".", "_")
SCHEMA = "RedfishInteroperabilityProfile.v1_10_0"
CONTRIBUTED_BY = "OCP Scaling AI Clusters at Neoclouds workgroup (DRAFT); evidence from the reference collector"
CONTACT = "OCP FTI Scaling AI Clusters at Neoclouds workstream"
GPU_REPO = "github.com/opencomputeproject/ocp-hm-system-gpu-management/profiles"
HW_REPO = "github.com/opencomputeproject/HWMgmt-OCP-Profiles"
ACCEL = ["GPU", "Accelerator"]
HBM = ["HBM", "HBM2", "HBM2E", "HBM3", "HBM3E"]


def M(**kw):
    d = {"ReadRequirement": "Mandatory"}; d.update(kw); return d


def R(**kw):
    d = {"ReadRequirement": "Recommended"}; d.update(kw); return d


def IF(**kw):
    d = {"ReadRequirement": "IfImplemented"}; d.update(kw); return d


def S(**kw):
    d = {"ReadRequirement": "Supported"}; d.update(kw); return d


def status(conditions=True):
    p = {"Health": M(), "State": M()}
    if conditions:
        p["Conditions"] = R(Purpose="Active-fault list without log scraping [gap 8.4]. Not populated by any BMC in the fleet today [rec]; Recommended so the ask is on record.")
    return M(PropertyRequirements=p)


def header(name, purpose, required):
    return {
        "SchemaDefinition": SCHEMA,
        "ProfileName": name,
        "ProfileVersion": VERSION,
        "Purpose": purpose,
        "OwningEntity": "Open Compute Project",
        "ContributedBy": CONTRIBUTED_BY,
        "ContactInfo": CONTACT,
        "ProfileType": "Interop",
        "RequiredProfiles": required,
    }


# =====================================================================
# 1. OCPNeocloudServiceCore — the service plane every neocloud BMC must offer
# =====================================================================
service_core = header(
    "OCPNeocloudServiceCore",
    "Neocloud service-plane core. Composes the approved OCP Service Baseline, Baseline Hardware Management "
    "and Server Hardware Management profiles and tightens what fleet-scale, agentless, read-only monitoring "
    "needs: pre-authentication identity, a query-parameter floor, subordinate-manager liveness, firmware "
    "inventory as the fleet-consistency source, eventing, RBAC and an audit log. Required by "
    "OCPNeocloudPlatform and OCPNeocloudAccelerator. Level: Neocloud-Core = Mandatory items; "
    "Neocloud-Trusted = Recommended items.",
    {
        "OCPServiceBaseline": {"MinVersion": "1.0.0", "Repository": HW_REPO},
        "OCPBaselineHardwareManagement": {"MinVersion": "1.1.0", "Repository": HW_REPO},
        "OCPServerHardwareManagement": {"MinVersion": "1.0.0", "Repository": HW_REPO},
    },
)
service_core["Protocol"] = {
    "MinVersion": "1.15",
    "ExpandQuery": "Recommended",
    "SelectQuery": "Recommended",
    "FilterQuery": "Recommended",
    "ExcerptQuery": "Recommended",
    "OnlyQuery": "Mandatory",
    "DeepPATCH": "None",
    "DeepPOST": "None",
}
service_core["Resources"] = {
    "ServiceRoot": M(PropertyRequirements={
        "RedfishVersion": M(),
        "Vendor": M(Purpose="Pre-authentication vendor fingerprint. Null on Supermicro JBOF firmware, where Oem is the reliable fingerprint [sweep]."),
        "UUID": R(Purpose="Dell iDRAC reports no UUID and exposes ServiceIdentification instead [rec]; either identifier satisfies the identity requirement below."),
        "ServiceIdentification": R(Purpose="A per-chassis identifier readable without a credential. 121 of 121 Redfish BMCs in a 259-address sweep carried a unique identifier (UUID or service tag) unauthenticated, zero collisions [sweep]. Lets a client confirm the machine at an address before spending a credential."),
        "ProtocolFeaturesSupported": M(PropertyRequirements={
            "ExpandQuery": M(PropertyRequirements={
                "Levels": M(),
                "MaxLevels": M(Purpose="Fleet-scale cost is set by expand depth: MaxLevels=1 (iDRAC9) forces a per-resource walk of 8 GPUs, p50 6.7 s per node; MaxLevels=3 (Supermicro) or bulk MetricReports give p50 1.7 s [live]. A value of 2 or more, or bulk MetricReports covering every accelerator ProcessorMetrics and MemoryMetrics, is the Neocloud-Trusted expectation."),
            }),
            "SelectQuery": R(),
            "FilterQuery": R(),
            "ExcerptQuery": R(Purpose="Present on Supermicro 1.22.2, absent on iDRAC9 1.20.1 [rec]."),
            "OnlyMemberQuery": M(),
        }),
        "Systems": M(), "Chassis": M(), "Managers": M(),
        "SessionService": M(), "AccountService": M(), "EventService": M(), "UpdateService": M(),
        "CertificateService": M(),
        "TelemetryService": R(Purpose="License- or configuration-gated on several OEMs (Dell iDRAC Datacenter license; ServiceEnabled=false shipped fleet-wide until an ops PATCH [rec]). Content requirements live in OCPNeocloudAccelerator and are conditional."),
        "LicenseService": R(Purpose="Makes telemetry/feature licensing auditable. Advertised by Supermicro, Dell and Lenovo, absent on AMI MegaRAC [sweep]."),
        "ComponentIntegrity": R(Purpose="SPDM attestation roots (13-21 ERoT/IRoT members per HGX node [rec]). Neocloud-Trusted. Advertised but empty on AMI MegaRAC PCIe boxes [sweep] - a link is not proof."),
        "AggregationService": R(Purpose="The standard form of the host-BMC to accelerator-controller relationship (DSP0266 s16). No BMC in the fleet implements it; Supermicro aggregates the NVIDIA HMC implicitly into its own tree and AggregationService 404s [rec]."),
    }),
    "Manager": M(PropertyRequirements={
        "ManagerType": M(),
        "FirmwareVersion": M(Purpose="Firmware band, not model, decides the Redfish tree: HMC 25.02 enumerates 25 firmware components, 25.05 and 26.04 enumerate 34 [live]. Clients key norms on this value."),
        "Status": M(PropertyRequirements={
            "Health": M(),
            "State": M(Purpose="Subordinate managers (an accelerator management controller aggregated by the host BMC) shall appear as Manager members, and their unavailability shall be expressed here (UnavailableOffline or Absent) rather than only as HTTP 503 on their subtree. Two HGX trays detached in six weeks (A1-69 Aug 2026, undetected 9 days; A1-17 2026-09-20) while the host BMC answered 200 [live]."),
            "Conditions": R(),
        }),
        "Links": R(PropertyRequirements={"ManagerForServers": R(), "ManagerForChassis": R()}),
        "DateTime": R(Purpose="Accelerator event logs carry 2020-01-01 timestamps before the controller has NTP [rec]; clients must be able to detect an unsynchronized manager clock."),
        "LogServices": R(),
    }),
    "SessionService": M(PropertyRequirements={"SessionTimeout": M(), "Sessions": M()}),
    "Session": M(Purpose="Audit identity: who connected, from where, when.", PropertyRequirements={
        "UserName": M(), "ClientOriginIPAddress": R(), "CreatedTime": R()}),
    "AccountService": M(Purpose="RBAC and least privilege on the management interface. A read-only role whose privilege cannot change hardware state is the Core credential [gap 2.2].", PropertyRequirements={
        "Accounts": M(), "Roles": M(),
        "LDAP": R(), "ActiveDirectory": R(), "OAuth2": R(Purpose="Delegated auth / SSO (DSP0266 s13.4.4)."),
        "MultiFactorAuth": R(), "AccountLockoutThreshold": R(), "MinPasswordLength": R()}),
    "Role": M(Purpose="The monitoring credential is a ReadOnly role whose privileges cannot change hardware state, verified at the role, not in collector code [gap 2.2]. Demoting a shared account to read-only has broken provisioning tooling that depended on it [live]; a distinct predefined ReadOnly role avoids that.", PropertyRequirements={"RoleId": M(MinSupportValues=["ReadOnly"]), "AssignedPrivileges": M(), "IsPredefined": R()}),
    "EventService": M(Purpose="Push eventing to monitoring and SIEM. Advertised by every BMC vendor in the fleet [sweep]; content below is the floor.", PropertyRequirements={
        "ServiceEnabled": M(), "Subscriptions": M(),
        "ServerSentEventUri": R(Purpose="SSE stream of events and metric reports; present on the NVIDIA HMC surface [rec]."),
        "IncludeOriginOfConditionSupported": R(), "RegistryPrefixes": R(), "ResourceTypes": R()},
        ActionRequirements={"SubmitTestEvent": R()}),
    "EventDestination": IF(PropertyRequirements={
        "Destination": M(), "Protocol": M(), "SubscriptionType": M(),
        "EventFormatType": R(Purpose="MetricReport format for streamed telemetry."),
        "IncludeOriginOfCondition": R(), "DeliveryRetryPolicy": R(),
        "SyslogFilters": R(Purpose="Forward security/audit events to a SIEM.")}),
    "LogService": M(Purpose="At least one LogService whose LogPurposes contains Security, capturing privileged actions with actor identity [gap 2.2]; and the platform/accelerator event logs consumed as logs, not metrics.", PropertyRequirements={
        "Entries": M(), "LogPurposes": R(), "ServiceEnabled": R(), "DateTime": R()},
        ActionRequirements={"ClearLog": R()}),
    "LogEntry": M(PropertyRequirements={
        "Created": M(), "Severity": M(), "Message": M(),
        "MessageId": M(Purpose="Accelerator RAS events (XID, SXID, strap mismatch) arrive today as free text inside ResourceEvent.1.0.ResourceErrorsDetected [rec]. A MessageId from an accelerator RAS registry (OCPAcceleratorRAS, AcceleratorFabric) is what makes them alertable."),
        "MessageArgs": R(), "OriginOfCondition": R(), "Originator": R(), "OriginatorType": R(),
        "AdditionalDataURI": R(Purpose="CPER / diagnostic payload per OCP GPU & Accelerator RAS Requirements 1.7."),
        "VendorCode": R(Purpose="Redfish 2026.2 (LogEntry v1.22, Condition, Event, Message) added VendorCode: the standard place for an NVIDIA XID/SXID or AMD RAS code alongside a neutral MessageId, instead of free text. Neocloud-Trusted."),
        "DiagnosticDataType": R(Purpose="CPER / CPERSection / Device (2025.1) so accelerator CPER records land in a standard, filterable place."),
        "CPER": R(PropertyRequirements={"NotificationType": R(), "SectionType": R()})}),
    "UpdateService": M(Purpose="Firmware inventory is the fleet-consistency and component-census source; multipart push is the update mechanism (aligned with OCP_UBB_BaselineManagement 2.0.0).", PropertyRequirements={
        "ServiceEnabled": M(),
        "FirmwareInventory": M(Purpose="Shall enumerate every field-updatable component the service manages, including every component of an aggregated accelerator subsystem (HGX: BMC, ERoTs, FPGA, 8 GPUs, InfoROMs, NVSwitches, NVLink NIC, 8 retimers = 34 members) [rec]. A member count that falls below the node's own recent value is how a silently degraded tray is caught [live]."),
        "MultipartHttpPushUri": M(),
        "SoftwareInventory": R()},
        ActionRequirements={"SimpleUpdate": R(Parameters={"ImageURI": M(), "Targets": R(), "TransferProtocol": R()})}),
    "SoftwareInventory": M(PropertyRequirements={
        "Version": M(Purpose="Fleet firmware-consistency reconciliation (driver/firmware version drift is a ClusterMAX Reliability item) [gap 2.1]."),
        "Status": M(PropertyRequirements={"Health": R(), "State": M()}),
        "Updateable": R(), "SoftwareId": R(), "RelatedItem": R(), "Manufacturer": R(), "ReleaseDate": R()}),
    "CertificateService": M(PropertyRequirements={"CertificateLocations": M()}, ActionRequirements={"GenerateCSR": R(), "ReplaceCertificate": R()}),
    "SecureBoot": R(Purpose="Neocloud-Trusted. Boot integrity; present on Supermicro ComputerSystem [rec].", PropertyRequirements={
        "SecureBootEnable": R(), "SecureBootCurrentBoot": R(), "SecureBootMode": R()}),
    "ComponentIntegrity": R(Purpose="Neocloud-Trusted. SPDM/TPM attestation of GPUs, NICs, baseboards. An audit job, not a scrape: attestation is pass/fail, not a time series [rec].", PropertyRequirements={
        "ComponentIntegrityType": M(), "ComponentIntegrityEnabled": M(), "TargetComponentURI": M(),
        "SPDM": R(), "Status": R()},
        ActionRequirements={"SPDMGetSignedMeasurements": R()}),
    "OutboundConnection": R(Purpose="Neocloud-Trusted. BMC-initiated mTLS call-home for management networks without inbound reachability (DSP0266 s12.10); today collection runs from a runner inside the BMC plane because nothing else can reach it [live]."),
}
service_core["Registries"] = {"Base": {"MinVersion": "1.0.0", "Repository": "redfish.dmtf.org/registries", "Messages": {}}}

# =====================================================================
# 2. OCPNeocloudPlatform — what any Redfish BMC in a GPU fleet must expose
# =====================================================================
platform = header(
    "OCPNeocloudPlatform",
    "Neocloud platform (host) tier: the DMTF-standard chassis, power, thermal, drive, memory and processor "
    "health any Redfish BMC in a GPU fleet must expose so that agentless, read-only monitoring reaches every "
    "node - tenant, unprovisioned, wedged or powered off - regardless of accelerator platform. Every "
    "requirement here is collected in production today from Supermicro, Dell and Lenovo BMCs with zero probe "
    "errors [live]. Requires OCPNeocloudServiceCore.",
    {"OCPNeocloudServiceCore": {"MinVersion": VERSION}},
)
platform["Protocol"] = {"MinVersion": "1.15"}
platform["Resources"] = {
    "ComputerSystem": M(PropertyRequirements={
        "PowerState": M(Purpose="Host power state from the BMC; a powered-off host with a live BMC is data, not a gap [live: A1-17]."),
        "Status": status(),
        "SystemType": M(), "Manufacturer": M(), "Model": M(), "SerialNumber": M(), "SKU": R(),
        "BiosVersion": M(), "Processors": M(), "Memory": M(), "Storage": R(),
        "MemorySummary": R(PropertyRequirements={"TotalSystemMemoryGiB": R(), "Status": R()}),
        "ProcessorSummary": R(PropertyRequirements={"Count": R(), "Status": R()}),
        "Links": M(PropertyRequirements={"ManagedBy": M(), "Chassis": M()}),
        "LogServices": M(),
        "SecureBoot": R(),
    }),
    "Chassis": M(PropertyRequirements={
        "ChassisType": M(), "Manufacturer": M(), "Model": M(), "SerialNumber": M(), "PartNumber": R(),
        "Status": status(),
        "PowerState": R(),
        "PowerSubsystem": R(Purpose="Modern power model. Supermicro exposes PowerSubsystem and ThermalSubsystem alongside the deprecated Power and Thermal [rec]; either satisfies this profile via the resource requirements below."),
        "ThermalSubsystem": R(), "EnvironmentMetrics": R(), "Sensors": R(),
        "Power": IF(), "Thermal": IF(),
        "Links": M(PropertyRequirements={"ComputerSystems": R(), "ManagedBy": M(),
            "ContainedBy": R(Purpose="Power scope. A node chassis reporting 3.3 kW and its accelerator tray chassis reporting 2.3 kW are both correct; containment is what lets a client label the scope instead of double counting [rec]."), "Contains": R()}),
    }),
    "Power": IF(Purpose="Deprecated schema, still the only power model on some shipping firmware. Requirements mirror PowerSupply/PowerSubsystem below.", PropertyRequirements={
        "PowerControl": M(PropertyRequirements={"PowerConsumedWatts": M(), "PowerCapacityWatts": R()}),
        "PowerSupplies": M(PropertyRequirements={
            "MemberId": M(),
            "Status": M(PropertyRequirements={
                "State": M(Purpose="An unpopulated bay shall report State=Absent so clients compare healthy supplies against installed ones, not against bay count: a 6-bay chassis with 4 supplies is correctly populated [rec]. A dead supply reports Enabled + Critical with ~5 W input [live: 13 PSUs on 11 nodes]."),
                "Health": M()}),
            "PowerInputWatts": R(), "PowerOutputWatts": R(), "LineInputVoltage": R(),
            "PowerCapacityWatts": R(), "Model": R(), "SerialNumber": R(), "FirmwareVersion": R()}),
    }),
    "PowerSubsystem": IF(PropertyRequirements={"PowerSupplies": M(), "Status": R(),
        "CapacityWatts": R(), "Allocation": R()}),
    "PowerSupply": IF(PropertyRequirements={
        "Status": M(PropertyRequirements={"State": M(Purpose="Absent for an empty bay; see Power.PowerSupplies."), "Health": M()}),
        "Metrics": R(), "Model": R(), "SerialNumber": R(), "FirmwareVersion": R(), "PowerCapacityWatts": R()}),
    "PowerSupplyMetrics": IF(PropertyRequirements={
        "InputPowerWatts": R(PropertyRequirements={"Reading": M()}),
        "OutputPowerWatts": R(PropertyRequirements={"Reading": M()}),
        "InputVoltage": R(PropertyRequirements={"Reading": M()})}),
    "Thermal": IF(PropertyRequirements={
        "Temperatures": M(PropertyRequirements={
            "MemberId": M(), "ReadingCelsius": M(), "Status": M(),
            "PhysicalContext": R(Purpose="OCPServerHardwareManagement 1.0.0 requires CPU, Intake and SystemBoard contexts; a GPU server may report CPU, GPU and SystemBoard only [rec: Dell]. This profile does not constrain the value set."),
            "UpperThresholdCritical": R()}),
        "Fans": M(PropertyRequirements={"MemberId": M(), "Reading": M(), "ReadingUnits": R(), "Status": M()}),
    }),
    "ThermalSubsystem": IF(PropertyRequirements={"Fans": M(), "ThermalMetrics": M(), "Status": R()}),
    "ThermalMetrics": IF(PropertyRequirements={
        "TemperatureSummaryCelsius": R(PropertyRequirements={"Intake": R(), "Exhaust": R()}),
        "TemperatureReadingsCelsius": R()}),
    "Fan": IF(PropertyRequirements={"Status": M(), "SpeedPercent": R(PropertyRequirements={"Reading": M()})}),
    "EnvironmentMetrics": R(Purpose="Chassis-level power and energy for showback and capacity: fleet chassis-consumed power is a sum over this or PowerControl [live: 555.5 kW at Site A].", PropertyRequirements={
        "PowerWatts": R(PropertyRequirements={"Reading": M()}),
        "EnergykWh": R(PropertyRequirements={"Reading": M()}),
        "TemperatureCelsius": R(PropertyRequirements={"Reading": M()})}),
    "Sensor": R(PropertyRequirements={
        "Reading": M(), "ReadingType": M(), "ReadingUnits": M(), "Status": M(), "PhysicalContext": R(),
        "Thresholds": R()}),
    "Processor": R(Purpose="Host CPUs: presence and health only. Accelerator requirements are in OCPNeocloudAccelerator.", PropertyRequirements={
        "ProcessorType": M(), "Status": status(conditions=False), "Model": R(), "Manufacturer": R()}),
    "Memory": R(Purpose="Host DIMMs: presence and health.", PropertyRequirements={
        "Status": status(conditions=False), "CapacityMiB": R(), "MemoryDeviceType": R(), "Manufacturer": R(), "PartNumber": R()}),
    "Storage": M(PropertyRequirements={"Drives": M(), "Status": M(), "StorageControllers": R()}),
    "Drive": M(Purpose="Coarse drive health for nodes where nvme-cli can never run. 5 fields versus 74 from an in-band SMART collector, but non-zero where there is otherwise nothing [gap 2.3].", PropertyRequirements={
        "Status": status(conditions=False),
        "FailurePredicted": M(),
        "PredictedMediaLifeLeftPercent": R(),
        "CapacityBytes": M(), "Protocol": M(), "MediaType": R(),
        "Model": M(), "Revision": R(Purpose="Drive firmware version, for fleet consistency."), "SerialNumber": R(),
        "PhysicalLocation": R(),
        "NVMe": R(Purpose="Where the BMC can read NVMe SMART (Dell exposes it through the NVMeSMARTData telemetry report [rec]), surface it; critical-warning, percentage-used and media errors are the fields the in-band model alerts on."),
    }),
}
platform["Registries"] = {"Base": {"MinVersion": "1.0.0", "Repository": "redfish.dmtf.org/registries", "Messages": {}}}

# =====================================================================
# 3. OCPNeocloudAccelerator — the GPU/accelerator RAS surface
# =====================================================================
accel = header(
    "OCPNeocloudAccelerator",
    "Neocloud accelerator tier. Applies to systems with GPU/accelerator Processors, whether the accelerator "
    "management controller's Redfish model is aggregated by the host BMC (NVIDIA HGX via Supermicro) or the "
    "BMC models the GPUs itself (Dell iDRAC). Composes OCP_UBB_BaselineManagement 2.0.0 (OCP System GPU "
    "Management workstream; being renamed from UBB) and adds the RAS content ClusterMAX Reliability and "
    "Monitoring weight most: HBM ECC, PCIe AER and link width, throttle durations, NVLink port health, "
    "active conditions, accelerator-subsystem liveness, and a conditional bulk-telemetry contract. "
    "Requirements are scoped to accelerator Processors by UseCase so host CPUs are not tested against them.",
    {
        "OCPNeocloudServiceCore": {"MinVersion": VERSION},
        "OCP_UBB_BaselineManagement": {"MinVersion": "2.0.0", "Repository": GPU_REPO},
    },
)
accel["Protocol"] = {"MinVersion": "1.15", "ExpandQuery": "Recommended"}

gpu_processor = M(
    UseCaseTitle="Accelerator Processor",
    UseCaseKeyProperty="ProcessorType", UseCaseKeyValues=ACCEL, UseCaseComparison="AnyOf",
    PropertyRequirements={
        "ProcessorType": M(), "Manufacturer": M(), "Model": M(), "SerialNumber": R(), "PartNumber": R(),
        "Metrics": M(Purpose="Raised from UBB Recommended: the GPU telemetry link must exist. Present on both fleet platforms [rec]."),
        "EnvironmentMetrics": M(),
        "MemorySummary": M(PropertyRequirements={"Metrics": M(Purpose="Link to the HBM MemoryMetrics for this accelerator (Dell shape) [rec]. HMC shape links HBM as Memory members of the accelerator baseboard system.")}),
        "Status": M(PropertyRequirements={"Health": M(), "State": M(Purpose="A device that left the PCIe bus shall not remain Enabled/OK: report UnavailableOffline or Absent (DSP0266 s9.11). A node with 4 of 8 GPUs off the bus reported 8 GPUs Enabled/OK [rec]; today the only OOB tell is PCIeInterface.LanesInUse=0 [live]."), "Conditions": R()}),
        "Ports": R(Purpose="NVLink ports. Mandatory in OCP_UBB_BaselineManagement (inherited). Dell iDRAC9 7.20 models NVLink state in Oem.Dell on ProcessorMetrics instead of Ports [rec] - the gap to raise with Dell."),
        "Links": R(PropertyRequirements={"PCIeDevice": R(), "Chassis": R()}),
        "SystemInterface": R(PropertyRequirements={"PCIe": R(PropertyRequirements={"PCIeType": R(), "MaxLanes": R(), "MaxPCIeType": R()})}),
    })

gpu_metrics = M(
    UseCaseTitle="Accelerator ProcessorMetrics",
    UseCaseType="ProcessorType", UseCaseKeyValues=ACCEL, UseCaseComparison="AnyOf",
    Purpose="Standard-schema GPU RAS. The NVIDIA HMC surface provides 14 of the 15 paths below [rec: Supermicro HGX B200]; iDRAC9 7.20 provides BandwidthPercent, OperatingSpeedMHz and CorrectableErrorCount only, carrying the rest in Oem.Dell/Oem.Nvidia [rec: Dell XE9680].",
    PropertyRequirements={
        "BandwidthPercent": M(),
        "OperatingSpeedMHz": M(),
        "PCIeErrors": M(Purpose="PCIe AER: link instability and 'fell off the bus' [gap 2.1].", PropertyRequirements={
            "CorrectableErrorCount": M(), "NonFatalErrorCount": M(), "FatalErrorCount": M(),
            "L0ToRecoveryCount": R(), "ReplayCount": R(), "ReplayRolloverCount": R(),
            "NAKSentCount": R(), "NAKReceivedCount": R(), "UnsupportedRequestCount": R()}),
        "PCIeInterface": R(Purpose="Negotiated link. LanesInUse=0 on all 8 GPUs of one node and on one GPU of another is the live 'GPU fell off the bus' signature, visible with no host agent [live: A1-96, A1-101].", PropertyRequirements={
            "LanesInUse": M(), "MaxLanes": M(), "PCIeType": R(), "MaxPCIeType": R()}),
        "PowerLimitThrottleDuration": R(Purpose="Power-cap throttling is normal under a cap; sustained thermal or hardware-violation throttling is a fault. Durations are ISO 8601 strings on the HMC [rec]."),
        "ThermalLimitThrottleDuration": R(),
        "ThrottlingCelsius": R(Purpose="Not provided by any platform in the fleet [rec]."),
        "CacheMetricsTotal": R(PropertyRequirements={"LifeTime": M(PropertyRequirements={
            "CorrectableECCErrorCount": M(), "UncorrectableECCErrorCount": M()})}),
        "TemperatureCelsius": R(), "ConsumedPowerWatt": R(),
    })

hbm_memory_metrics = {
    "BandwidthPercent": M(),
    "LifeTime": M(Purpose="The single most important GPU RAS signal [gap 2.1]. Present on the HMC surface; absent on iDRAC9 7.20.80.50, whose GPU MemoryMetrics carries BandwidthPercent and OperatingSpeedMHz only and whose GPUStatistics telemetry report is defined but empty [rec]. In production: 1 GPU with lifetime uncorrectable > 0, 7 with correctable > 0 (604 to 2.6e9), 10 with rows remapped [live].", PropertyRequirements={
        "CorrectableECCErrorCount": M(), "UncorrectableECCErrorCount": M()}),
    "CurrentPeriod": R(PropertyRequirements={"CorrectableECCErrorCount": M(), "UncorrectableECCErrorCount": M()}),
    "CapacityUtilizationPercent": R(), "OperatingSpeedMHz": R(),
    "HealthData": R(Purpose="Standard home for row-remap headroom once proposed to DMTF; today remap counts and bank availability are Oem.Nvidia.RowRemapping and drive the fleet's RMA-candidate alert (2 GPUs with no remap capacity left) [live].", PropertyRequirements={
        "PredictedMediaLifeLeftPercent": R(), "RemainingSpareBlockPercentage": R(),
        "AlarmTrips": R(PropertyRequirements={"CorrectableECCError": R(), "UncorrectableECCError": R(), "SpareBlock": R(), "Temperature": R()})}),
}
accel_port = M(
    UseCaseTitle="Accelerator Port", UseCaseType="ProcessorType", UseCaseKeyValues=ACCEL, UseCaseComparison="AnyOf",
    Purpose="NVLink (or other scale-up) ports of an accelerator. 19 per GPU plus NVSwitch ports on HGX B200 [rec].",
    PropertyRequirements={
        "PortProtocol": M(), "PortType": R(),
        "LinkStatus": M(Purpose="The HMC reports 'OK' where DSP2046 defines LinkUp/LinkDown [rec]; clients treat any value other than LinkDown/NoLink as up until the enum is fixed. Firmware misreporting of link state has been documented on GB200; corroborate with error counters [gap 8.7]."),
        "LinkState": R(Purpose="Not present in the HMC port reports [rec]."),
        "CurrentSpeedGbps": M(), "MaxSpeedGbps": R(), "Metrics": M(),
        "LinkTransitionIndicator": R(),
        "Status": status(),
    })
accel_port_metrics = M(
    UseCaseTitle="Accelerator PortMetrics", UseCaseType="ProcessorType", UseCaseKeyValues=ACCEL, UseCaseComparison="AnyOf",
    Purpose="Standard counters exist for bytes and RXErrors; the counters the fleet alerts on - link-downed, unintentional link-down, error recovery, symbol errors, effective BER, malformed packets, training/runtime errors - are Oem.Nvidia today [rec, live: NVSwitch link-down counters up to 978 per switch]. These are the DMTF proposal (see docs/dmtf-proposals.md).",
    PropertyRequirements={
        "RXBytes": M(), "TXBytes": M(), "RXErrors": M(), "TXErrors": R(),
        "Networking": R(PropertyRequirements={"RXFrames": R(), "TXFrames": R(), "TXDiscards": R()}),
    })

accel["Resources"] = {
    "Processor": {"UseCases": [gpu_processor]},
    "ProcessorMetrics": {"UseCases": [gpu_metrics]},
    "Memory": {"UseCases": [M(
        UseCaseTitle="Accelerator HBM", UseCaseKeyProperty="MemoryDeviceType", UseCaseKeyValues=HBM, UseCaseComparison="AnyOf",
        PropertyRequirements={"MemoryDeviceType": M(), "CapacityMiB": M(), "Metrics": M(), "Status": status(),
                              "Manufacturer": R(), "PartNumber": R(), "SerialNumber": R()})]},
    "MemoryMetrics": {"UseCases": [
        M(UseCaseTitle="HBM MemoryMetrics under an accelerator Processor (MemorySummary.Metrics)", UseCaseType="ProcessorType",
          UseCaseKeyValues=ACCEL, UseCaseComparison="AnyOf", PropertyRequirements=hbm_memory_metrics),
        M(UseCaseTitle="HBM MemoryMetrics under an HBM Memory member", UseCaseType="MemoryType",
          UseCaseKeyValues=HBM, UseCaseComparison="AnyOf", PropertyRequirements=hbm_memory_metrics),
    ]},
    "EnvironmentMetrics": {"UseCases": [M(
        UseCaseTitle="Accelerator EnvironmentMetrics", UseCaseType="ProcessorType", UseCaseKeyValues=ACCEL, UseCaseComparison="AnyOf",
        PropertyRequirements={
            "TemperatureCelsius": M(PropertyRequirements={"Reading": M()}),
            "PowerWatts": M(PropertyRequirements={"Reading": M()}),
            "EnergyJoules": R(PropertyRequirements={"Reading": M()}),
            "PowerLimitWatts": R(PropertyRequirements={"SetPoint": R(), "ControlMode": R()})})]},
    "Port": {"UseCases": [accel_port]},
    "PortMetrics": {"UseCases": [accel_port_metrics]},
    "Switch": IF(Purpose="NVSwitch or other scale-up switch inside the accelerator subsystem.", PropertyRequirements={
        "SwitchType": M(), "Ports": M(), "Status": status(), "FirmwareVersion": R(), "Metrics": R(), "Model": R()}),
    "Fabric": IF(Purpose="Intra-node scale-up fabric only. Rack-scale NVLink (NVL72) is owned by NVIDIA NMX-C/GFM outside the Redfish tree [gap 8.7].", PropertyRequirements={
        "FabricType": M(), "Switches": M(), "Status": status()}),
    "PCIeDevice": R(PropertyRequirements={
        "Status": M(PropertyRequirements={"State": M(Purpose="Absent / UnavailableOffline is the standard device-left-the-bus signal (DSP0266 s9.11)."), "Health": M()}),
        "PCIeInterface": R(PropertyRequirements={"LanesInUse": R(), "MaxLanes": R(), "PCIeType": R()}),
        "FirmwareVersion": R()}),
    "TelemetryService": IF(Purpose="License- or configuration-gated: do not hard-require streaming [gap 8.3]. If implemented, the content below is Mandatory and the service should cover every accelerator ProcessorMetrics and MemoryMetrics in bulk (HMC: 12 HGX reports, 11,609 values, 2.5 MiB, generated OnRequest; Dell: 29 definitions, ServiceEnabled shipped false) [rec].", PropertyRequirements={
        "ServiceEnabled": M(), "MetricReportDefinitions": M(), "MetricReports": M(), "MinCollectionInterval": M(),
        "SupportedCollectionFunctions": R(), "Triggers": R(), "Status": R()}),
    "MetricReportDefinition": IF(PropertyRequirements={
        "MetricReport": M(),
        "MetricReportDefinitionType": M(Comparison="AnyOf", Values=["Periodic", "OnChange", "OnRequest"]),
        "ReportUpdates": R(), "Metrics": R(), "Status": R()}),
    "MetricReport": IF(PropertyRequirements={
        "MetricReportDefinition": M(),
        "Timestamp": R(Purpose="Null on every HMC report; each MetricValue carries its own Timestamp and an Oem.Nvidia.MetricValueStale flag instead [rec]. Values are strings, including 'NA' for absent [rec]."),
        "MetricValues": M(PropertyRequirements={"MetricProperty": M(), "MetricValue": M(), "Timestamp": R(), "MetricId": R()})}),
    "Triggers": IF(PropertyRequirements={"MetricType": R(), "NumericThresholds": R(), "MetricProperties": R()}),
    "LogEntry": R(Purpose="Accelerator event log entries shall use a MessageId from an accelerator RAS registry (OCPAcceleratorRAS, AcceleratorFabric) rather than free text in a ResourceEvent message [rec], carry the vendor code in VendorCode (2026.2), and carry CPER payloads per OCP GPU & Accelerator RAS Requirements 1.7.", PropertyRequirements={"MessageId": M(), "Severity": M(), "Created": M(), "VendorCode": R(), "OriginOfCondition": R(), "DiagnosticDataType": R(), "AdditionalDataURI": R()}),
}
accel["Registries"] = {
    "OCPAcceleratorRAS": {"MinVersion": "1.0.0", "Repository": "github.com/opencomputeproject/neocloud-redfish/registries",
                          "Messages": {k: {} for k in ("AcceleratorSubsystemUnavailable", "AcceleratorSubsystemRestored", "GPUXidError", "NVSwitchSxidError",
                                                          "HBMUncorrectableECC", "HBMCorrectableECCRateHigh", "GPURowRemappingPending", "GPURowRemappingFailure",
                                                          "GPURowRemapCapacityExhausted", "GPUFellOffBus", "GPUPCIeLinkDegraded", "GPUThrottledSustained", "MetricValueStale")}},
    "AcceleratorFabric": {"MinVersion": "1.0.0", "Repository": "github.com/opencomputeproject/ocp-hm-system-gpu-management/docs",
                          "Messages": {k: {} for k in ("LinkTrainingFailed", "LinkFlapDetected", "DegradedConnectionEstablished", "ConnectionDropped", "ConnectionSpeedLow")}},
}

# =====================================================================
# 4. OCPAcceleratorRAS message registry (draft)
# =====================================================================
def msg(desc, message, sev, args, resolution):
    return {"Description": desc, "Message": message, "Severity": sev, "MessageSeverity": sev,
            "NumberOfArgs": len(args), "ParamTypes": args, "Resolution": resolution}

registry = {
    "@Redfish.Copyright": "Copyright 2026 Open Compute Project. Released under CC-BY-SA-4.0.",
    "@odata.type": "#MessageRegistry.v1_6_2.MessageRegistry",
    "Id": "OCPAcceleratorRAS.1.0.0",
    "Name": "OCP Accelerator RAS Message Registry",
    "Language": "en",
    "Description": "Standardized Redfish messages for accelerator (GPU, HBM, NVSwitch, accelerator management controller) RAS events. "
                   "Gives neutral MessageIds to conditions that today arrive as vendor free text or as Oem counters. Link/port events are "
                   "deliberately left to the OCP AcceleratorFabric registry (ocp-hm-system-gpu-management). DRAFT: the vendor code mapping "
                   "(NVIDIA XID/SXID, AMD equivalents) is the open work item with the OCP System GPU Management workstream.",
    "RegistryPrefix": "OCPAcceleratorRAS", "RegistryVersion": "1.0.0", "OwningEntity": "Open Compute Project",
    "Messages": {
        "AcceleratorSubsystemUnavailable": msg("The accelerator management controller or subsystem stopped answering while the host BMC remained healthy.",
            "Accelerator subsystem '%1' managed by '%2' is unavailable.", "Critical", ["string", "string"],
            "Check tray power, cabling and the accelerator management controller. Do not schedule accelerator work on this node until the subsystem is restored. Observed twice in six weeks on one fleet; without this event one occurrence went unnoticed nine days."),
        "AcceleratorSubsystemRestored": msg("The accelerator subsystem is answering again.",
            "Accelerator subsystem '%1' managed by '%2' is available.", "OK", ["string", "string"], "None."),
        "GPUXidError": msg("A GPU reported an NVIDIA XID error.", "GPU '%1' reported XID error %2: %3.", "Critical", ["string", "number", "string"],
            "Correlate the XID code with the NVIDIA XID reference. Drain and diagnose the node; replace the GPU if the fault is persistent or uncorrectable."),
        "NVSwitchSxidError": msg("An NVSwitch reported an SXID error.", "NVSwitch '%1' reported SXID error %2: %3.", "Critical", ["string", "number", "string"],
            "Assess NVLink fabric blast radius; drain affected GPUs and diagnose the NVSwitch."),
        "HBMUncorrectableECC": msg("An accelerator's HBM lifetime uncorrectable ECC count increased.",
            "GPU '%1' HBM uncorrectable ECC errors increased to %2.", "Critical", ["string", "number"],
            "Hard memory fault. Take the GPU out of service and run vendor diagnostics; replace if the count keeps rising."),
        "HBMCorrectableECCRateHigh": msg("An accelerator's HBM correctable ECC rate exceeded the operator's threshold.",
            "GPU '%1' HBM correctable ECC errors increased by %2 in the last %3 minutes.", "Warning", ["string", "number", "number"],
            "Watch for row remapping; schedule a reset in the next maintenance window if remaps are pending."),
        "GPURowRemappingPending": msg("A GPU has a pending HBM row remapping that requires a reset to take effect.",
            "GPU '%1' has a pending memory row remapping.", "Warning", ["string"],
            "Schedule a GPU reset during the next maintenance window to apply the remapping."),
        "GPURowRemappingFailure": msg("A GPU HBM row remapping operation failed.", "GPU '%1' memory row remapping failed.", "Critical", ["string"],
            "Drain the node and replace the GPU."),
        "GPURowRemapCapacityExhausted": msg("One or more HBM banks on a GPU have no remap capacity left.",
            "GPU '%1' has %2 HBM banks with no remaining row-remap capacity.", "Warning", ["string", "number"],
            "The next uncorrectable error in an exhausted bank cannot be remapped. Treat the GPU as an RMA candidate."),
        "GPUFellOffBus": msg("A GPU is no longer present on the PCIe bus.", "GPU '%1' is no longer responding on the PCIe bus.", "Critical", ["string"],
            "Drain the node; check PCIe AER counters and reseat or replace the GPU."),
        "GPUPCIeLinkDegraded": msg("A GPU's negotiated PCIe link is narrower or slower than its maximum.",
            "GPU '%1' PCIe link is %2 lanes at %3 (maximum %4 lanes at %5).", "Warning", ["string", "number", "string", "number", "string"],
            "A degraded link halves host-to-GPU bandwidth silently. Check retimers and reseat; a link at 0 lanes with the device still enumerated is a bus drop."),
        "GPUThrottledSustained": msg("A GPU spent more than the operator's threshold of wall-clock time throttled for a thermal or hardware-violation reason.",
            "GPU '%1' was throttled for reason '%2' for %3 percent of the last %4 minutes.", "Warning", ["string", "string", "number", "number"],
            "Power-cap throttling under a configured cap is expected; thermal or hardware-violation throttling indicates cooling or a hardware fault."),
        "MetricValueStale": msg("The management controller flagged a telemetry value as stale.",
            "Metric '%1' on '%2' is stale; last update %3.", "Warning", ["string", "string", "string"],
            "Do not record the value. If a whole report is stale, treat the accelerator subsystem as degraded."),
    },
}

os.makedirs("profiles", exist_ok=True)
os.makedirs("registries", exist_ok=True)
for prof in (service_core, platform, accel):
    path = f"profiles/{prof['ProfileName']}.v{VFILE}.json"
    with open(path, "w") as f:
        json.dump(prof, f, indent=2); f.write("\n")
    print("wrote", path, "resources:", len(prof["Resources"]))
with open("registries/OCPAcceleratorRAS.1.0.0.json", "w") as f:
    json.dump(registry, f, indent=2); f.write("\n")
print("wrote registries/OCPAcceleratorRAS.1.0.0.json messages:", len(registry["Messages"]))
