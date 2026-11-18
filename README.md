# omni-quarto-report

A terminal **gather** collector (omnibenchmark api ≥ 0.7.0, 0.8.0 included) that renders a
Quarto/Rmd template over whatever the gather collected. It knows nothing about
any particular benchmark: the template comes from the plan as a parameter, the
data comes from the gather, and the two meet through a manifest.

```yaml
  - id: REPORT
    gather:
      from: sens_json            # no group_by: every producer, one node
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

On api 0.7.0 the stage also needs `prefix: report`, and the gather is written
as a list (`gather: [{from: sens_json}]`).

The module follows the gather contract of the plan's api version. From 0.8.0
it reads the members from `--from-files <lineage.json>` and writes the page to
the path given by `--output`; on 0.7.0 it takes them as `--<output_id> p1 p2 …`.
The template sees the same `manifest.json` either way.

The module writes three files into the node's output directory, which is also
the render directory:

| file | |
|---|---|
| `report.Rmd` | the template, copied in |
| `manifest.json` | `{"inputs": {"<output_id>": [absolute paths]}, "lineage": {…}}` |
| `report.html` | what quarto produced |

`--link_as reports/foo.html` additionally points a short, stable path at the
rendered page, so a run has one place to open that carries no parameter hash.
The link is relative (`../REPORT.quarto.<hash>/report.html`), so the
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
- `--output_dir` is optional: without it the node's directory is where
  `--output` points.
- `--link_as` works as on 0.7.0. Naming the directory in the plan,
  `gather: {from: sens_json, path: reports}`, gives a stable path without a link.

The template reads `manifest.json` from its own working directory. `lineage` is
the engine's `lineage.json` for the gather: every contributing node with its
commit and directory and, from api 0.8.0, its files and the stage, module and
parameter values of each of its ancestors. A report can label results and show
its own provenance from it.

## Where the template comes from

A module runs from its own checkout, so "the .Rmd in the plan" is not a path
the module can see. `--template` is therefore resolved against the **benchmark
directory** — the nearest ancestor of the node's output directory containing
`.git` — and is refused if it resolves anywhere else.

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
