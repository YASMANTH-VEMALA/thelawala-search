# Live walkthrough and submission handoff

## Before the interview

Read `README.md`, `docs/DECISIONS.md`, and `AI_USAGE.md`. Run the app and the tests yourself. Be comfortable explaining the actual implementation; AI assistance is disclosed rather than hidden. Original input files are in the repository so reviewers can reproduce the snapshot.

```sh
python -m unittest discover -s tests -v
python -m thelawala batch examples/queries.txt --output artifacts/results.jsonl
python -m thelawala serve
```

## Five-minute demonstration

1. `milk`: drinking milk only. Explain product identity versus ingredient matching.
2. `milk chocolate`: different intent, different products.
3. `godavari milk`: brand restriction is stronger than the own-label preference.
4. `panner`, `పాలు`, `pesara pappu`: typo repair and explicit regional aliases, not arbitrary language understanding.
5. `oil under 200`, `atta 5kg`, `butter without salt`: constraints extracted from the one search box.
6. `onion`: no purchasable results; actual onions appear as unavailable/unknown. No onion chips as filler.
7. `apple`: some prices are under review. `apple under 300` excludes those uncertain prices.
8. `iphone charger`: empty results are preferable to weak grocery matches.
9. Run the batch command and open its output: exactly `query` and an ordered SKU list.

## Explain the code in this order

`data.py` validates and joins records → `query.py` interprets text → `search.py` intersects postings and ranks → `behavior.py` supplies a bounded preference → `batch.py`/`web.py` expose the same result function. The browser uses `static/app.js`; it never implements its own ranking.

Explain why the engine needs neither an LLM nor a database server for 1,102 products. Distinguish the measured synthetic 20k candidate-volume test from a real 20k vocabulary/load evaluation. Be clear that 63 curated cases are regression checks and that held-out cart labels are incomplete.

## Small changes suitable for the live session

- Add a regional alias in `config/synonyms.json`, restart, and verify a query.
- Change the own-label weight in `search.py` and discuss why it cannot override an explicit brand.
- Add a case to `evaluation/cases.json` before changing price/pack semantics.
- Change inventory in a disposable data-directory copy; restart with `--data-dir` to demonstrate snapshot rebuild without editing source code.

Do not modify the original supplied files just for a demonstration.

## Publishing later

The user requested local-only preparation. This repository has a `main` branch and incremental commits; no remote is configured. When ready, create a GitHub repository under the intended account, ensure the reviewer can access it, and push this folder. Do not initialize the new remote with a separate README/history.

```sh
git status
git log --oneline
git remote add origin https://github.com/YOUR_ACCOUNT/YOUR_REPOSITORY.git
git push -u origin main
```

`YOUR_ACCOUNT` and `YOUR_REPOSITORY` are placeholders to replace. If the repository is private, invite the reviewer; a private URL alone is not sufficient. Do not include generated `__pycache__`, a virtual environment, or local scratch output. The `.gitignore` already excludes these.

## Suggested submission note

Replace the bracketed URL after publishing:

> Thelawala Search submission: [repository URL]
>
> The repository includes an offline Python search engine, a single-box web demo, and the required JSONL batch interface. The README covers setup, ranking, data assumptions, evaluation, and next steps. AI usage and discovered mistakes are documented in AI_USAGE.md. Please start with `python -m thelawala serve` or `python -m thelawala batch examples/queries.txt`.

This note has not been sent. The user remains responsible for choosing when and where to submit.
