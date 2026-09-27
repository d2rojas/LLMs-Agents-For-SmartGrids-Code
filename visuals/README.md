# visuals/

The one site the case studies share: `site/index.html` plus a page per case study.

```bash
python -m visuals.build                 # every case study
python -m visuals.build --case evagent  # one of them
open site/index.html
```

## Why it is shared

The case studies are read side by side. If two pages name a method differently,
group their metrics differently, or simply look different, a reader takes that
as a finding about the case studies rather than about how the pages were
written. So the chrome exists once, in `shell.py`: the stylesheet, the sidebar,
the tabs, the chips, the tables, the prompt blocks. A case study contributes
content and never chrome.

## How a case study joins

Each one has `evaluation/page_fragments.py` and writes the payload described at
the top of `build.py` to the path given as its only argument. The generators run
as subprocesses, in their own directory and with their own interpreter, for two
reasons: the projects have packages of the same name (`evaluation`, `config`,
`data`), so they cannot be imported into one process, and they pin different
dependencies, so no single environment reliably has all of them. `build.py`
picks `<case>/.venv/bin/python` when it exists and otherwise the interpreter it
was launched with.

| case study | folder | state |
|---|---|---|
| `pfagent` | `power-flow-agent/` | adapter: runs `evaluation/design_page.py` and lifts its tabs, stylesheet and script. To be moved onto `shell.py` directly. |
| `evagent` | `ev-scheduling/` | native: builds its tabs with `shell.py`. |
| `griddebug`, `wind` | — | not yet |

Every page is generated from the code that would run — the method registry, the
verification conditions, the scenario generator, the prompt builders, the result
files — so no page can describe a design that is not the one that runs. Nothing
on them is written by hand twice.
