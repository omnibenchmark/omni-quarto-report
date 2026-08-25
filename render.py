#!/usr/bin/env python3
"""Render a Quarto/Rmd template over whatever a gather stage collected.

A generic terminal collector: it knows nothing about the benchmark. The
template comes from the *plan* as a parameter, the data comes from the gather,
and the two meet through a manifest the template reads:

    ./render.py --output_dir DIR --name ID --template report.Rmd \
        --<output_id> a.json b.json ...

Everything lands in DIR, which is also the render directory:

    report.Rmd      the template, copied in
    manifest.json   {"inputs": {"<output_id>": [abs paths]}, "lineage": {...}}
    report.html     the rendered page

Template resolution, in order: an http(s) URL, an absolute path, a path
relative to the working directory, then the same path tried against each parent
of it. The last case is the one that matters in practice -- omnibenchmark runs
a module from the benchmark's *output* directory, so a plan-relative
`report.Rmd` is found by walking back up to the plan.
"""

import argparse
import json
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output_dir", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--template", required=True, help="path or http(s) URL to a .Rmd/.qmd")
    p.add_argument("--to", default="html", help="quarto output format")
    return p.parse_known_args()


def gathered(unknown):
    """`--<id> p1 p2 … --<id2> …` -> {id: [paths]}.

    A gather module's inputs are named after the output ids it collects, which
    the plan chooses, so they cannot be declared up front.
    """
    groups, current = {}, None
    for token in unknown:
        if token.startswith("--"):
            current = token[2:]
            groups.setdefault(current, [])
        elif current is not None:
            groups[current].append(str(Path(token).resolve()))
    return {k: v for k, v in groups.items() if v}


def fetch_template(spec, dest):
    if spec.startswith(("http://", "https://")):
        with urllib.request.urlopen(spec) as r:
            dest.write_bytes(r.read())
        return spec
    candidate = Path(spec)
    if not candidate.is_absolute():
        for base in [Path.cwd(), *Path.cwd().parents]:
            if (base / spec).is_file():
                candidate = base / spec
                break
    if not candidate.is_file():
        raise SystemExit(
            f"error: template {spec!r} not found -- give an absolute path, a path "
            f"relative to the benchmark directory, or an http(s) URL"
        )
    shutil.copyfile(candidate, dest)
    return str(candidate)


def main():
    args, unknown = parse_args()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    template = out / "report.Rmd"
    source = fetch_template(args.template, template)
    print(f"  template: {source}")

    sidecar = out / "lineage.json"
    manifest = {
        "name": args.name,
        "template": source,
        "inputs": gathered(unknown),
        "lineage": json.loads(sidecar.read_text()) if sidecar.is_file() else None,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for oid, paths in manifest["inputs"].items():
        print(f"  {oid}: {len(paths)} file(s)")

    cmd = ["quarto", "render", template.name, "--to", args.to]
    print(f"  {' '.join(cmd)} (in {out})")
    result = subprocess.run(cmd, cwd=out)
    if result.returncode != 0:
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
