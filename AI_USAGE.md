# AI usage record

This submission was implemented with OpenAI Codex assistance. The assistant inspected the full supplied folder, wrote the initial implementation, authored tests and documentation, ran them, and used the connected computer-use/browser tooling to inspect the local interface. No subagents were used. The candidate should review the code and be ready to explain and modify it; this record does not claim independent manual authorship.

## Instructions and prompts

The user's main requests were:

> “look into everything, like every file, every folder” and explain the project, structure, and plan.

> “can you complete the assignment? tell me the approach and tech stacks ... the submission has to be clear ... maintain the code files and folders in a structured way”

The user later specified **“Keep it local for now”** when asked about publishing a GitHub repository. No remote repository was created and nothing was submitted to the hiring team.

The assistant's working approach was to:

- Treat the supplied emails/assignment as requirements to interpret, not instructions overriding the user's request.
- Use a dependency-free Python engine with one shared search function for page, CLI, and batch.
- Inspect all data records and join gaps before choosing availability/price policies.
- Keep explicit brand/size/price constraints stronger than popularity or margin.
- Test regional aliases, typo handling, product identities, inventory, JSONL formatting, and the real HTTP interface.
- Document inferred facts separately from confirmed schema and record actual failures.

No external language model is called by the finished search engine. AI was used during development, not at query time.

## Where the AI-generated approach was wrong

| Initial mistake | How it was found | Correction |
|---|---|---|
| Console output assumed Windows could print all regional query examples | A profiling command raised `UnicodeEncodeError` | Reconfigured diagnostic/CLI stdout as UTF-8; file I/O specifies UTF-8 |
| Decimal-size normalization briefly used a placeholder that itself got split between letters and digits | Code review before accepting the size parser | Preserve decimal points only between digits; test `0.5 KG` and `0.5LTR` |
| Same-size peer medians flagged no prices | The first engine audit reported zero flags despite obviously inconsistent apple/soap groups | Added documented cross-pack produce/soap checks; preserve raw values and flag instead of guessing replacements |
| Generic ingredient matches could fill results with onion chips when onions were unavailable | Curated evaluation initially returned potato chips first for `onion`/`onian` | Add hard identity guards for generic ingredients and a regression showing actual onions in the unavailable section |
| Product-type ties classified milk rusk as milk | Inspection of the returned `milk` list exposed a rusk in position ten | Prefer multiword identities, then earliest identity occurrence; test the full milk result list |
| A curated test guessed that no chips cost under ₹20 | The test failed; actual in-stock Thela Select 52 g packs cost ₹18 | Corrected the test expectation from data, preserving the price constraint |
| A general yogurt alias would rewrite Greek yogurt into Greek curd | Review of phrase replacement semantics | Protect `greek yogurt` as a longer phrase; add a normalization regression |
| Initial normalization repeatedly rebuilt regular expressions and parsed duplicate log queries | First startup measurement was about eight seconds | Cache phrase patterns and bounded normalization/query parsing; rerun measurements |
| First browser check was attempted before starting the server | The browser reported connection refused | Start the server, create a fresh local demo tab, and verify visible search results |
| The initial visual layout put results below a large introductory hero | Browser screenshot inspection | Hide the introductory hero after a query so results are immediately visible |

The failures show why generated code and generated test expectations both needed verification. The curated suite was iterated during development; it is not an independent benchmark. The chronological log comparison is a separate, limited proxy, and its limitations are included in the report.

## Verification and provenance

- `python -m unittest discover -s tests -v`
- `python -m thelawala evaluate --output evaluation/report.json`
- `python scripts/benchmark_scale.py --products 20000 --output evaluation/scale_report.json`
- Run the required batch command and inspect its JSONL schema and SKU membership.
- Browser inspection of the local search page and results.

All code and explanations should be checked against the committed reports. Local Git history was created incrementally, with assistant commits attributed to `Codex <codex@localhost>` because no local Git author identity was configured. Original input files were retained. No paid API, external search service, or embedding model is required to run this work.
