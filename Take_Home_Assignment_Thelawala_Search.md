# Take-Home Assignment: Thelawala Search

**Entry-level Developer · Two Theta**

**Time:** about 4–6 hours.
**Stack:** any language, any tools.
**AI:** use AI coding tools and agents as much as you like. We expect you to.

---

## The situation

Thelawala is a grocery delivery app in Hyderabad. It is a fictional client.

Customers use the search box, and often they don't find what they want, even when it's on the shelf. Many give up and browse categories. Some leave the app.

Thelawala has asked us to build their product search. They sent us:

- their product data
- two months of search logs
- an email thread from their team

That is all the specification there is. Nobody from Thelawala can answer questions during this assignment. If something is unclear, make a call and write down what you decided.

## What's in the pack

| File | What it is |
|---|---|
| `emails.md` | The Thelawala team's thoughts on search |
| `thelawala-search-data/catalog.csv` | Products listed in the app |
| `thelawala-search-data/inventory.csv` | Stock information from their warehouse system |
| `thelawala-search-data/search_log.jsonl` | Searches made in the app from 15 Aug to 10 Oct 2026, and what customers did next |

There is no data dictionary.

Today is **12 Oct 2026**.

## What to build

Build a search for this catalog. A customer types something, and the search returns the products they're most likely looking for, best first.

We need two ways to run it:

1. **For a person.** Someone on Thelawala's team should be able to type a query and see the results. A simple web page or a CLI is fine.
2. **In batch.** We will run your search on our own list of queries. It should take a text file with one query per line. It should write `results.jsonl`, with one line per query:

   ```
   {"query": "...", "results": ["sku_id", "sku_id", ...]}
   ```

   `results` holds up to 10 `sku_id`s, best first.

## What to submit

A link to a Git repository containing:

- **Your code.** Commit as you go; we read the history.
- **`README.md`**, which covers:
  - how to run it
  - how your search works
  - the decisions you made and why
  - what you would do next
- **`AI_USAGE.md`**, which covers:
  - how you used AI tools
  - the main prompts or instructions you gave them
  - where they got things wrong, and how you found out

After you submit, we'll do a live session. You'll walk us through your work and make changes to it.

---

We care more about your judgement than about how much you build.
