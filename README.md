# omni-quarto-report

A terminal **gather** collector (omnibenchmark api ≥ 0.7.0) that renders a
Quarto/Rmd template over whatever the gather collected. It knows nothing about
any particular benchmark: the template comes from the plan as a parameter, the
data comes from the gather, and the two meet through a manifest.

```yaml
  - id: REPORT
    prefix: report
    gather:
      - from: sens_json          # no group_by: every producer, one node
    modules:
      - id: quarto
        software_environment: quarto
        repository: {url: …, commit: …}
        parameters:
          - template: report.Rmd     # lives in the plan
    outputs:
      - id: report_html
        path: report.html
```

The module writes three files into the node's output directory, which is also
the render directory:

| file | |
|---|---|
| `report.Rmd` | the template, copied in |
| `manifest.json` | `{"inputs": {"<output_id>": [absolute paths]}, "lineage": {…}}` |
| `report.html` | what quarto produced |

`--link_as reports/foo.html` additionally points a short, stable path at the
rendered page, so a run has one place to open that carries no parameter hash.
The link is relative (`../report/REPORT/quarto/.<hash>/report.html`), so the
output tree stays movable; it is confined to the run directory like
`--template`, replaces its own link on a re-run, and refuses to overwrite a
path that is not already a symlink.

Two things it is not. It is not a declared output, so snakemake does not track
or clean it. And it is one path per value: on a *grouped* gather every node
would write the same link and the last would win — omnibenchmark substitutes
`{...}` in output paths but not in parameter values, so it cannot be templated
per group. Use it on the global (collector) form, or give each group its own
value.

## api 0.8.0

On a 0.8.0 plan the module is called with `--from-files <lineage.json>` and one
`--output id=PATH`, and runs from its own checkout:

- `manifest.json` keeps its shape. `inputs` is built from the members' `files`,
  and `lineage` is the whole gather manifest (lineage.json, version 2).
- The page is written to the declared output path; the stage declares exactly
  one output.
- `--template` is resolved against the benchmark directory found above that
  output path.
- `--link_as` is refused. Name the directory in the plan instead:
  `gather: {from: sens_json, path: reports}`.

The template reads `manifest.json` from its own working directory. `lineage` is
the engine's gather sidecar — every contributing node with its stage, module,
commit and directory — so a report can show its own provenance.

## Where the template comes from

A module runs from its own checkout, so "the .Rmd in the plan" is not a path
the module can see. `--template` is therefore resolved against the **benchmark
directory** — the nearest ancestor of the working directory containing `.git`,
since omnibenchmark runs collectors from the benchmark's *output* directory —
and is refused if it resolves anywhere else.

That confinement is deliberate, not defensive habit:

- The rendered page is an artifact people share. A template argument free to
  name any file on the host would quietly copy that file's contents into it.
- A `.Rmd` is executed by knitr. An earlier version of this module accepted an
  `http(s)` URL and the README recommended one, which made it unpinned remote
  code execution dressed up as convenience — while every other executable thing
  in omnibenchmark is pinned by commit sha. The URL branch is gone.

Neither is a privilege boundary: whoever writes the plan already names the git
repositories omnibenchmark clones and runs. It is about not turning a report
into an exfiltration primitive by accident, and about a template argument
failing loudly instead of silently rendering some other file.

A template that needs to travel belongs in a **module repository**, pinned by
commit like any other module asset — which is what
[design 010 §3.7](https://github.com/omnibenchmark/omnibenchmark/blob/main/docs/design/010-gather.md)
recommends. Keeping it in the plan is the trade this module supports; it is not
the only option.

## Tests

```sh
./test_render.py     # template confinement + the gather CLI contract
```
