#!/usr/bin/env python3
"""Evidence matrix: which properties a Redfish interoperability profile requires vs. what a recorded
BMC tree actually contains.

Usage: evidence_matrix.py PROFILE.json RECORDING_DIR [RECORDING_DIR ...]

A fixture dir is a the reference collector `redfish record` output (mirrored `tree/redfish/v1/.../index.json[.gz]`,
or the older flat layout with `reports/*.json.gz`). Properties are taken from resource bodies and, for
bulk MetricReports, from the `MetricProperty` URI fragments, so the NVIDIA HMC surface counts even
though the recording holds reports rather than per-resource GETs.

Prints one block per profile resource with present/missing requirement paths per fixture, and writes
`evidence-props.json` (resource type -> property paths) beside the profile for reuse.
"""
import glob, gzip, json, os, re, sys


def load(p):
    op = gzip.open if p.endswith(".gz") else open
    with op(p, "rt") as f:
        return json.load(f)


def rtype(body):
    m = re.match(r"#([A-Za-z0-9_]+)\.", body.get("@odata.type", "") if isinstance(body, dict) else "")
    return m.group(1) if m else None


def props(obj, prefix=""):
    out = set()
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.startswith("@"):
                continue
            out.add(prefix + k)
            if k == "Oem":
                continue
            if isinstance(v, dict):
                out |= props(v, prefix + k + "/")
            elif isinstance(v, list) and v and isinstance(v[0], dict):
                out |= props(v[0], prefix + k + "/")
    return out


def uri_rtype(uri):
    seg = uri.partition("#")[0].rstrip("/").split("/")
    last = seg[-1]
    if last in ("ProcessorMetrics", "MemoryMetrics", "EnvironmentMetrics"):
        return last
    if last == "Metrics" and "Ports" in seg:
        return "PortMetrics"
    if last == "Metrics" and "Switches" in seg:
        return "SwitchMetrics"
    for key, name in (("Ports", "Port"), ("Sensors", "Sensor"), ("Processors", "Processor"),
                      ("Memory", "Memory"), ("Switches", "Switch"), ("Chassis", "Chassis")):
        if key in seg:
            return name
    return last


def collect(fixture_dir):
    ev = {}

    def add(rt, ps):
        ev.setdefault(rt, set()).update(ps)

    for p in glob.glob(os.path.join(fixture_dir, "**", "*.json*"), recursive=True):
        if p.endswith("_recording.json"):
            continue
        try:
            b = load(p)
        except Exception:
            continue
        if not isinstance(b, dict):
            continue
        rt = rtype(b)
        if rt and rt != "MetricReport":
            add(rt, props(b))
        if rt == "MetricReport" or "MetricValues" in b:
            add("MetricReport", props(b))
            for mv in b.get("MetricValues", []):
                u = mv.get("MetricProperty", "")
                if not u:
                    continue
                frag = re.sub(r"/\d+(/|$)", r"\1", u.partition("#")[2].strip("/"))
                parts = frag.split("/")
                add(uri_rtype(u), {frag, *["/".join(parts[:i]) for i in range(1, len(parts))]})
        for v in b.values():
            if isinstance(v, list):
                for m in v:
                    if isinstance(m, dict) and rtype(m):
                        add(rtype(m), props(m))
            elif isinstance(v, dict) and rtype(v):
                add(rtype(v), props(v))
    return ev


def reqs(node, prefix=""):
    out = []
    for name, spec in (node.get("PropertyRequirements") or {}).items():
        out.append((prefix + name, spec.get("ReadRequirement", "Mandatory")))
        out += reqs(spec, prefix + name + "/")
    return out


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    prof = json.load(open(sys.argv[1]))
    fixtures = {os.path.basename(os.path.normpath(d)): collect(d) for d in sys.argv[2:]}
    json.dump({k: {r: sorted(s) for r, s in v.items()} for k, v in fixtures.items()},
              open(os.path.join(os.path.dirname(sys.argv[1]) or ".", "evidence-props.json"), "w"), indent=1)
    print(f"# {prof.get('ProfileName')} {prof.get('ProfileVersion')}")
    for rt, spec in prof["Resources"].items():
        print(f"\n{rt} [{spec.get('ReadRequirement', 'Mandatory')}]")
        for name, ev in fixtures.items():
            have = ev.get(rt, set())
            if not have:
                print(f"  {name}: resource not in recording")
                continue
            rq = reqs(spec)
            hit = [n for n, _ in rq if n in have]
            miss = [f"{n}({r[0]})" for n, r in rq if n not in have]
            print(f"  {name}: {len(hit)}/{len(rq)} required paths present; missing: {', '.join(miss) or '-'}")


if __name__ == "__main__":
    main()
