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

`--template` names a file inside the benchmark directory and nowhere else. The
module runs from the run's *output* directory, so the path is resolved against
the benchmark root found above it.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output_dir", required=True)
    p.add_argument("--name", required=True)
    p.add_argument("--template", required=True,
                   help="path to a .Rmd/.qmd, relative to the benchmark directory")
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


def benchmark_root(start=None):
    """The plan's directory. `.git` marks it; without one, stop at the output
    directory's parent rather than walking up to `/`."""
    cwd = (start or Path.cwd()).resolve()
    for base in [cwd, *cwd.parents]:
        if (base / ".git").exists():
            return base
    return cwd.parent


def find_template(spec, root=None):
    """Resolve `--template` inside the benchmark directory, and refuse to leave it.

    Confined on purpose. The rendered page is an artifact people share, so a
    template argument free to name any file on the host would quietly copy that
    file's contents into it -- and a `.Rmd` is executed by knitr, so an
    unpinned remote one would be remote code execution recommended as
    convenience. Templates that need to travel belong in a module repository,
    pinned by commit like any other module asset (design 010 §3.7).
    """
    root = root or benchmark_root()
    path = Path(spec)
    path = path.resolve() if path.is_absolute() else (root / path).resolve()
    if not path.is_relative_to(root):
        raise SystemExit(
            f"error: template {spec!r} resolves to {path}, outside the benchmark "
            f"directory ({root})"
        )
    if not path.is_file():
        raise SystemExit(f"error: template {spec!r} not found under {root}")
    return path


def main():
    args, unknown = parse_args()
    out = Path(args.output_dir).resolve()
    out.mkdir(parents=True, exist_ok=True)

    template = out / "report.Rmd"
    source = find_template(args.template)
    shutil.copyfile(source, template)
    print(f"  template: {source}")

    sidecar = out / "lineage.json"
    manifest = {
        "name": args.name,
        "template": str(source),
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
