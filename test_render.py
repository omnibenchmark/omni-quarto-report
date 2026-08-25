#!/usr/bin/env python3
"""Template resolution must not leave the benchmark directory. Run: ./test_render.py"""

import tempfile
from pathlib import Path

from render import benchmark_root, find_template, gathered


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

    # `--<output_id> p1 p2 …`, the gather CLI contract
    assert gathered(["--sens_json", "/a.json", "/b.json", "--other", "/c"]) == {
        "sens_json": ["/a.json", "/b.json"],
        "other": ["/c"],
    }
    print("ok")


if __name__ == "__main__":
    main()
