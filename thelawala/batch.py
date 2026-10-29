"""Required query-file contract with atomic output and duplicate preservation."""

import json
import os
from pathlib import Path
import tempfile


def run_batch(engine, input_path: Path, output_path: Path) -> int:
    input_path, output_path = input_path.resolve(), output_path.resolve()
    if input_path == output_path:
        raise ValueError("Input and output paths must differ")
    # Validate every query before replacing any existing output.
    queries = input_path.read_text(encoding="utf-8-sig").splitlines()
    if any(len(query) > 500 for query in queries):
        raise ValueError("Each query must be at most 500 characters")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=output_path.parent, suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            for query in queries:
                result = engine.search(query)
                handle.write(json.dumps({"query": query, "results": [p["sku_id"] for p in result["results"]]},
                                        ensure_ascii=False) + "\n")
        os.replace(temp_path, output_path)
    finally:
        if temp_path and temp_path.exists():
            temp_path.unlink()
    return len(queries)
