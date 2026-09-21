# Upstream OCP profiles composed by this family (verbatim copies for the validator)

The DMTF Redfish-Interop-Validator resolves `RequiredProfiles` by file name in the directory of the
profile under test (`<ProfileName>.v<MAJOR>_<MINOR>_<PATCH>.json`), so the composed profiles are
mirrored here. Sources, as of 2026-09-20:

| File | Source | Note |
|---|---|---|
| `OCPServiceBaseline.v1_0_0.json` | HWMgmt-OCP-Profiles `main` (approved) | verbatim |
| `OCPBaselineHardwareManagement.v1_1_0.json`, `.v1_1_1.json` | HWMgmt-OCP-Profiles `main` (approved) | 1.1.1 content copied under both names (the 1.1.1 file self-declares `ProfileVersion` 1.1.0) |
| `OCPBaselineHardwareManagement.v1_0_1.json` | HWMgmt-OCP-Profiles `main` | required by Server 1.0.0 |
| `OCPServerHardwareManagement.v1_0_0.json` | HWMgmt-OCP-Profiles `main` (approved) | **patched**: upstream declares `"ProfileVersion": "1,0,0"`, which fails the profile JSON schema and aborts the validator. Upstream issue to file. |
| `OCP_UBB_BaselineManagement.v2_0_0.json` | ocp-hm-system-gpu-management `profiles/OCP_UBB_BaselineManagement.v2.0.0.json` (2026-08-28) | **patched**: upstream `UpdateService.ActionRequirements.SimpleUpdate` has `ReadRequirement: "IfImplement"` (typo) and `ParameterValues: ["HTTP??"]`, both rejected by the DSP0272 schema; the validator aborts. Upstream issue to file. The workstream is renaming UBB → MAS (PR #64) |

Do not edit these except to mirror upstream.
