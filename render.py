#!/usr/bin/env python3
"""Render a Quarto/Rmd template over whatever a gather stage collected.

A generic terminal collector: it knows nothing about the benchmark. The
template comes from the *plan* as a parameter, the data comes from the gather,
and the two meet through a manifest the template reads:

    ./render.py --template report.Rmd \
        --from-files lineage.json --output report_html=DIR/report.html   # api 0.8.0
    ./render.py --output_dir DIR --name ID --template report.Rmd \
        --<output_id> a.json b.json ...                                  # api 0.7.0

Everything lands in DIR, which is also the render directory:

    report.Rmd      the template, copied in
    manifest.json   {"inputs": {"<output_id>": [abs paths]}, "lineage": {...}}
    report.html     the rendered page

`--template` names a file inside the benchmark directory and nowhere else. It
is resolved against the benchmark root found above the node's output directory
(api 0.8.0, where the module runs from its own checkout) or above the working
directory (api 0.7.0, where it runs from the run's output directory).
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def parse_args():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output_dir", help="api 0.7.0; ignored with --from-files")
    p.add_argument("--name")
    p.add_argument("--from-files", help="api 0.8.0: the gather manifest (lineage.json v2)")
    p.add_argument("--output", action="append", default=[],
                   help="api 0.8.0: id=PATH of the rendered page; exactly one")
    p.add_argument("--template", required=True,
                   help="path to a .Rmd/.qmd, relative to the benchmark directory")
    p.add_argument("--to", default="html", help="quarto output format")
    p.add_argument("--link_as",
                   help="also symlink the rendered page here, relative to the "
                        "run directory (e.g. reports/pca-cubes.html)")
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


def from_manifest(manifest):
    """lineage.json v2 -> {id: [paths]}, the shape `gathered` returns."""
    groups = {}
    for member in manifest["members"]:
        for oid, path in member["files"].items():
            groups.setdefault(oid, []).append(path)
    return groups


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


def link_report(target, spec):
    """Point a short, stable path at the rendered page.

    Relative and confined to the run directory, like `--template`: the module
    is writing outside its own node here, and the run it belongs to is the only
    place that is safe. The symlink itself is relative so the output tree stays
    movable.

    The link is a convenience pointer, not a declared output -- snakemake does
    not track it. One `--link_as` value means one link: on a *grouped* gather
    every node would write the same path and the last would win, and it cannot
    be templated per group, since omnibenchmark substitutes `{...}` in output
    paths but not in parameter values. Give each group its own value, or leave
    `--link_as` to the global (collector) form it was written for.
    """
    link = Path(spec)
    if link.is_absolute() or ".." in link.parts:
        raise SystemExit(
            f"error: --link_as must be a relative path inside the run "
            f"directory, got {spec!r}"
        )
    link.parent.mkdir(parents=True, exist_ok=True)
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        raise SystemExit(
            f"error: --link_as {spec!r} exists and is not a symlink; refusing "
            f"to replace it"
        )
    link.symlink_to(os.path.relpath(target, link.parent.resolve()))
    return link


def main():
    args, unknown = parse_args()
    target = None
    if args.from_files:  # api 0.8.0
        if len(args.output) != 1:
            raise SystemExit("error: the stage must declare exactly one output")
        if args.link_as:
            raise SystemExit(
                "error: --link_as is for api 0.7.0; on 0.8.0 name the directory "
                "in the plan instead: gather: {from: ..., path: reports}"
            )
        target = Path(args.output[0].split("=", 1)[1]).resolve()
        out = target.parent
        lineage = json.loads(Path(args.from_files).read_text())
        inputs = from_manifest(lineage)
        root = benchmark_root(out)
    else:
        if not args.output_dir:
            raise SystemExit("error: --from-files or --output_dir is required")
        out = Path(args.output_dir).resolve()
        sidecar = out / "lineage.json"
        lineage = json.loads(sidecar.read_text()) if sidecar.is_file() else None
        inputs = gathered(unknown)
        root = None
    out.mkdir(parents=True, exist_ok=True)

    template = out / "report.Rmd"
    source = find_template(args.template, root)
    shutil.copyfile(source, template)
    print(f"  template: {source}")

    manifest = {
        "name": args.name,
        "template": str(source),
        "inputs": inputs,
        "lineage": lineage,
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    for oid, paths in manifest["inputs"].items():
        print(f"  {oid}: {len(paths)} file(s)")

    cmd = ["quarto", "render", template.name, "--to", args.to]
    print(f"  {' '.join(cmd)} (in {out})")
    result = subprocess.run(cmd, cwd=out)
    if result.returncode != 0:
        sys.exit(result.returncode)
    if target and target.name != f"report.{args.to}":
        (out / f"report.{args.to}").replace(target)

    if args.link_as:
        link = link_report(out / f"report.{args.to}", args.link_as)
        print(f"  linked: {link} -> {os.readlink(link)}")


if __name__ == "__main__":
    main()
