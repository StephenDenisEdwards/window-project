"""LLM-driven entity and relationship extraction over text chunks.

`extract_entities_and_relations` runs a single chunk through the LLM.
`extract_all` runs over a list of chunks with a resumable disk cache.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

import anthropic

from rag.pipeline.extract import Chunk
from rag.pipeline.llm import llm_chat

EXTRACTION_PROMPT = """Extract entities and relationships from this hardware catalog text.

ENTITY TYPES (use ONLY these exact values):
  product, manufacturer, feature, specification, material, certification, category

RELATIONSHIP TYPES (use ONLY these exact values):
  has_feature, manufactured_by, has_specification, compatible_with, part_of, variant_of

Return ONLY a valid JSON object with no markdown formatting, no code blocks, no extra text.
Use "relation" as the key for relationship type (not "type").

Example:
{"entities": [{"name": "Tiomos", "type": "product"}], "relationships": [{"source": "Tiomos", "relation": "manufactured_by", "target": "Grass"}]}

TEXT:
$TEXT$

JSON:"""


def extract_entities_and_relations(
    chunk_text: str,
    *,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
    retries: int = 2,
) -> dict:
    """Extract entities and relationships from a single chunk.

    Returns a dict ``{"entities": [...], "relationships": [...]}``. On
    repeated failure returns the empty form so callers can keep going.
    """
    for attempt in range(retries + 1):
        try:
            content = llm_chat(
                EXTRACTION_PROMPT.replace("$TEXT$", chunk_text),
                provider=provider,
                model=model,
                temperature=0.0,
                max_tokens=1024,
            )
            content = re.sub(r"^```json\s*", "", content)
            content = re.sub(r"\s*```$", "", content)
            match = re.search(r"\{[\s\S]*\}", content)
            if match:
                parsed = json.loads(match.group())
                entities = parsed.get("entities", [])
                relationships = parsed.get("relationships", [])
                for rel in relationships:
                    if "type" in rel and "relation" not in rel:
                        rel["relation"] = rel.pop("type")
                return {"entities": entities, "relationships": relationships}
        except anthropic.BadRequestError as e:
            if "credit balance" in str(e).lower():
                raise RuntimeError(
                    "Anthropic API credits exhausted. Top up at console.anthropic.com/settings/billing"
                ) from e
            if attempt == retries:
                print(f"API error: {e}")
        except anthropic.AuthenticationError as e:
            raise RuntimeError(f"Invalid API key. Check ANTHROPIC_API_KEY in .env: {e}") from e
        except anthropic.APIConnectionError as e:
            if attempt == retries:
                print(f"Connection error (check internet): {e}")
        except json.JSONDecodeError as e:
            if attempt == retries:
                print(f"JSON parse error: {e}")
        except Exception as e:
            if attempt == retries:
                print(f"Unexpected error: {type(e).__name__}: {e}")
    return {"entities": [], "relationships": []}


def extract_all(
    chunks: list[Chunk],
    cache_path: Path,
    *,
    provider: str = "anthropic",
    model: str = "claude-sonnet-4-20250514",
    force: bool = False,
    save_every: int = 50,
    abort_after_consecutive_failures: int = 10,
) -> list[dict]:
    """Extract entities for every chunk, resumable via `cache_path`.

    If `cache_path` exists and `force=False`, resumes from the cache.
    Persists progress every `save_every` chunks. Raises `RuntimeError`
    if `abort_after_consecutive_failures` chunks in a row return nothing
    (most often: API credits exhausted or upstream outage).
    """
    if cache_path.exists() and not force:
        all_extractions = json.loads(cache_path.read_text(encoding="utf-8"))
        total_e = sum(len(e.get("entities", [])) for e in all_extractions)
        if total_e > 0:
            print(f"Loaded {len(all_extractions)} extractions from {cache_path}")
        else:
            print("Cache has no entities — starting fresh")
            all_extractions = []
    else:
        all_extractions = []

    if len(all_extractions) >= len(chunks):
        print("Extraction already complete")
        return all_extractions

    start_idx = len(all_extractions)
    remaining = chunks[start_idx:]
    print(f"Extracting {len(remaining)} chunks (starting from {start_idx})...")

    start_time = time.time()
    consecutive_errors = 0

    for i, chunk in enumerate(remaining):
        result = extract_entities_and_relations(chunk.text, provider=provider, model=model)
        result["chunk_id"] = chunk.id
        result["source"] = chunk.source
        result["page"] = chunk.page
        all_extractions.append(result)

        if not result["entities"] and not result["relationships"]:
            consecutive_errors += 1
            if consecutive_errors >= abort_after_consecutive_failures:
                cache_path.write_text(json.dumps(all_extractions), encoding="utf-8")
                raise RuntimeError(
                    f"{consecutive_errors} consecutive extraction failures — check API credits. "
                    f"Saved {len(all_extractions)} extractions to {cache_path}."
                )
        else:
            consecutive_errors = 0

        elapsed = time.time() - start_time
        rate = (i + 1) / elapsed if elapsed > 0 else 0
        eta = (len(remaining) - i - 1) / rate if rate > 0 else 0
        total_e = sum(len(e.get("entities", [])) for e in all_extractions)
        total_r = sum(len(e.get("relationships", [])) for e in all_extractions)
        print(
            f"  [{start_idx + i + 1}/{len(chunks)}] "
            f"Entities: {total_e}, Relations: {total_r} (~{eta:.0f}s remaining)",
            end="\r",
        )

        if (i + 1) % save_every == 0:
            cache_path.write_text(json.dumps(all_extractions), encoding="utf-8")

    cache_path.write_text(json.dumps(all_extractions), encoding="utf-8")
    elapsed = time.time() - start_time
    total_e = sum(len(e.get("entities", [])) for e in all_extractions)
    total_r = sum(len(e.get("relationships", [])) for e in all_extractions)
    print(f"\nDone in {elapsed:.1f}s")
    print(f"Final: {len(all_extractions)} chunks, {total_e} entities, {total_r} relationships")
    return all_extractions
