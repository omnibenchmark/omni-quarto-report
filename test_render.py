#!/usr/bin/env python3
"""Template resolution must not leave the benchmark directory. Run: ./test_render.py"""

import os
import tempfile
from pathlib import Path

from render import benchmark_root, find_template, from_manifest, gathered, link_report, run_dir


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp).resolve() / "plan"
        (root / ".git").mkdir(parents=True)
        (root / "report.Rmd").write_text("---\ntitle: t\n---\n")
        (root / "sub").mkdir()
        (root / "sub" / "nested.Rmd").write_text("x")
        out = root / "out" / "report" / "node"
        out.mkdir(parents=True)

        assert benchmark_root(out) == root, benchmark_root(out)
        assert find_template("report.Rmd", root) == root / "report.Rmd"
        assert find_template("sub/nested.Rmd", root) == root / "sub" / "nested.Rmd"

        for escape in ("/etc/passwd", "../../etc/passwd", "../outside.Rmd"):
            try:
                find_template(escape, root)
            except SystemExit as e:
                assert "outside the benchmark" in str(e), (escape, e)
            else:
                raise AssertionError(f"{escape} was allowed out of {root}")

        try:
            find_template("absent.Rmd", root)
        except SystemExit as e:
            assert "not found" in str(e), e
        else:
            raise AssertionError("a missing template must fail, not resolve elsewhere")

    # --link_as: confined like --template, and relative so the tree stays movable
    with tempfile.TemporaryDirectory() as tmp:
        run = Path(tmp).resolve()
        node = run / "report" / "REPORT" / "quarto" / ".abc123"
        node.mkdir(parents=True)
        rendered = node / "report.html"
        rendered.write_text("<html></html>")

        cwd = Path.cwd()
        os.chdir(run)
        try:
            link = link_report(rendered, "reports/pca.html")
            assert link.is_symlink() and link.resolve() == rendered, link
            assert not os.readlink(link).startswith("/"), os.readlink(link)

            # a re-run replaces its own link rather than failing
            link_report(rendered, "reports/pca.html")

            for escape in ("/tmp/evil.html", "../escape.html"):
                try:
                    link_report(rendered, escape)
                except SystemExit as e:
                    assert "relative path inside the run" in str(e), (escape, e)
                else:
                    raise AssertionError(f"{escape} was allowed out of the run dir")

            # never clobber something that is not our own link
            (run / "real.html").write_text("someone else's file")
            try:
                link_report(rendered, "real.html")
            except SystemExit as e:
                assert "not a symlink" in str(e), e
            else:
                raise AssertionError("a real file must not be replaced by a link")
        finally:
            os.chdir(cwd)

    # `--<output_id> p1 p2 …`, the gather CLI contract
    assert gathered(["--sens_json", "/a.json", "/b.json", "--other", "/c"]) == {
        "sens_json": ["/a.json", "/b.json"],
        "other": ["/c"],
    }
    # `--from-files lineage.json`, the gather contract from api 0.8.0
    record = {"version": 2, "members": [
        {"files": {"scores": "/a.txt", "table": "/a.tsv"}, "lineage": []},
        {"files": {"scores": "/b.txt"}, "lineage": []},
    ]}
    assert from_manifest(record) == {"scores": ["/a.txt", "/b.txt"], "table": ["/a.tsv"]}

    # without .git, the benchmark is the directory holding the run directory,
    # whatever directory the module is started from
    with tempfile.TemporaryDirectory() as tmp:
        plan = Path(tmp).resolve() / "plan"
        node = plan / "out" / "report.quarto-abc123"
        node.mkdir(parents=True)
        (plan / "out" / "Snakefile").write_text("")
        assert run_dir(node) == plan / "out", run_dir(node)
        assert benchmark_root(node) == plan, benchmark_root(node)
        link = link_report(node / "report.html", "reports/r.html", run_dir(node))
        assert link == plan / "out" / "reports" / "r.html", link
    print("ok")


if __name__ == "__main__":
    main()
