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

The template reads `manifest.json` from its own working directory. `lineage` is
the engine's gather sidecar — every contributing node with its stage, module,
commit and directory — so a report can show its own provenance.

## Where the template comes from

A module runs from its own checkout, so "the .Rmd in the plan" is not a path
the module can see. `--template` is resolved as: an http(s) URL; an absolute
path; a path relative to the working directory; then that path against each
parent directory in turn. The last rule is what makes a plan-relative
`report.Rmd` work — omnibenchmark runs collectors from the benchmark's *output*
directory, which sits under the plan.

Pass a pinned raw URL instead when the plan and the run are not on the same
filesystem.
