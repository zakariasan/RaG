# RAG against the machine — requirements & progress

Tracking file for the 42 RAG project. Subject: `en_subject.md` (v2.0).

Legend: `[x]` done · `[~]` partial · `[ ]` not started

---

## 0. Measured status (last check)

| Metric | Value | Required |
|---|---|---|
| Indexing time, whole corpus | 7 s | <= 5 min |
| Chunks @ max_chunk_size 2000 | 15 837 (filtered) / 18 738 (all files) | — |
| Retrieval, 100 questions | < 0.1 s | 200 q <= 90 s |
| **docs recall@5** | **0.830** | **>= 0.80** |
| **code recall@5** | **0.657** | **>= 0.50** |
| Chunk coverage ceiling | docs 96/100, code 98/99 | — |

Retrieval thresholds already pass. Remeasure after every chunking or tokenizer change.

Reference points measured along the way:
- extension filter `.py/.md/.rst/.txt` → docs 0.850; indexing every non-ignored file → docs 0.830 (2 questions lost to ranking noise)
- own tokenizer vs `bm25s.tokenize` → code R@5 0.657 vs 0.525 (identifier splitting is worth 13 points)
- `max_chunk_size` ~62 chars → docs 0.460 / code 0.434, **both fail**: chunk too small to reach IoU 0.05 against a ~1400-char reference span

---

## 1. Pipeline

### Indexing — `[x]`
- [x] walk `data/raw/`, skip gitignored names (`fnmatch`, patterns from `.gitignore`)
- [x] Python chunker: `ast` top-level nodes, recurse into oversized bodies, `hard_split` fallback
- [x] text chunker: line-boundary split
- [x] every chunk carries `(file_path, first_character_index, last_character_index)`
- [x] chunks never exceed `max_chunk_size`; slices reconstruct each file exactly
- [x] tokenizer: whole word + CamelCase parts, lowercased, 1-char tokens dropped
- [x] BM25 index via `bm25s`, saved to `data/processed/`
- [x] `chunks.json` written in the same run, position `i` ↔ chunk `i`
- [x] tqdm bars: one over files, one over chunks
- [ ] `--max_chunk_size <= 0` guard — **currently an infinite loop in `hard_split`**
- [ ] Markdown chunking as a distinct strategy (split on `#` headings, then merge to size)
- [ ] `sorted(files)` / `sorted(folder)` for reproducible chunk ids

### Retrieval — `[~]`
- [x] `search <query> --k` single query, prints `file_path [start:end]`
- [x] loads BM25 + `chunks.json` from disk, same tokenizer as indexing
- [x] edge cases: `k <= 0`, empty query, missing index → clean message, no traceback
- [ ] `search_dataset --dataset_path --k --save_directory` → `StudentSearchResults` JSON
- [ ] batch the retrieve call (one `retrieve(all_tokens, k)` for the whole dataset)
- [ ] output filename = input basename, scoped by dataset folder

### Evaluation — `[ ]`
- [ ] `evaluate --student_search_results_path --dataset_path` → own recall@k
- [ ] hit = same `file_path` AND IoU >= 0.05 with the reference span
- [ ] get the moulinette from the attachments, confirm `Student data is valid: True`
- [ ] chunk-size sweep (2000 / 1000 / 500 / 250) for the README

### Answer generation — `[ ]`
- [ ] load `Qwen/Qwen3-0.6B` via transformers (big download, slow on CPU)
- [ ] prompt from retrieved sources, inside the token budget
- [ ] `answer <query> --k`
- [ ] `answer_dataset --student_search_results_path --save_directory` → `StudentSearchResultsAndAnswer`

---

## 1b. Command contracts (input → output)

Every path below is a CLI argument with a default — never hardcoded. All commands run as
`uv run python -m src <command> [flags]` from the repo root.

### `index`

```
index --max_chunk_size 2000 --files data/raw --save_dir data/processed
```

| | |
|---|---|
| **In** | every non-ignored file under `--files`; `.gitignore` patterns |
| **Out** | `<save_dir>/chunks.json` + the 5 bm25s files |
| **Stdout** | 2 tqdm bars (`Chunking` over files, `Tokenizing` over chunks) then `Ingestion complete! Indexed <n> chunks under <save_dir>` |
| **Budget** | <= 5 min whole corpus (currently 7 s) |

`chunks.json` — a flat list, element `i` is chunk `i`:
```json
[{"file_path": "data/raw/vllm-0.10.1/setup.py",
  "first_character_index": 0, "last_character_index": 1894}, ...]
```
`file_path` must be written exactly as walked from the repo root (`data/raw/vllm-0.10.1/...`);
the grader compares it verbatim. `last - first <= max_chunk_size`, always.

bm25s writes: `data.csc.index.npy` (weights), `indices.csc.index.npy` (chunk ids),
`indptr.csc.index.npy` (per-token offsets), `vocab.index.json` (token → column),
`params.index.json` (k1, b, method).

**Invariant:** `corpus_tokens[i]` ↔ `chunks.json[i]`. Both are written in the same run.
Never sort, filter or dedupe one without the other.

**Edge cases:** `max_chunk_size <= 0` → message, no hang. Missing `--files` → 0 chunks, no
traceback. Unparseable or binary file → skip and continue (count them).

### `search`

```
search "<query>" --k 10 --save_dir data/processed
```

| | |
|---|---|
| **In** | query string; the saved index |
| **Out** | nothing on disk |
| **Stdout** | `k` lines, best first: `data/raw/vllm-0.10.1/docs/features/lora.md [4745:6098]` |

Steps: load `chunks.json` + `BM25.load(save_dir)` → `tokenizer(query)` → `retrieve([tokens], k)`
→ map each returned id through `chunks.json`.

**Edge cases:** `k <= 0` → message, no retrieve. empty query (`tokenizer` returns `[]`) →
message. `k > len(chunks)` → clamp with `min`. missing or partial index → `index not found,
run index first`. nonsensical query → still returns top-k, which is correct behaviour.

### `search_dataset`

```
search_dataset --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json \
               --k 10 --save_directory data/output/search_results/UnansweredQuestions
```

**In** — `RagDataset` of questions only:
```json
{"rag_questions": [{"question_id": "1752...-7764-...", "question": "What HTTP endpoint ..."}, ...]}
```
100 questions in the docs set, 99 in the code set.

**Out** — `<save_directory>/<same basename as input>`, a `StudentSearchResults`:
```json
{"search_results": [
   {"question_id": "1752...", "question": "What HTTP endpoint ...",
    "retrieved_sources": [{"file_path": "...", "first_character_index": 0,
                           "last_character_index": 1403}]}],
 "k": 10}
```
`retrieved_sources` holds `k` entries, ranked best first. The same `file_path` may appear
several times with different ranges — that is correct, one entry per chunk.

**Stdout** — tqdm over questions, then `Saved student_search_results to <path>`.

**Rules:** keep the input basename, since the reference scripts pair files by name. Always
scope `--save_directory` by dataset (`UnansweredQuestions` / `AnsweredQuestions`) because the
two public datasets share filenames. Load the index **once**, outside the loop, and prefer a
single batched `retrieve(all_tokens, k=k)` call.

**Budget:** 200 questions <= 90 s.

**Edge cases:** missing file / malformed JSON → clean message. Empty `rag_questions` → write a
valid file with an empty list. A question whose text tokenizes to nothing → empty
`retrieved_sources`, not a crash.

### `evaluate` (own testing only)

```
evaluate --student_search_results_path <your output> --dataset_path <AnsweredQuestions file>
```

**In** — your `StudentSearchResults` + the ground truth, which adds `answer` and `sources`:
```json
{"question_id": "...", "question": "...", "answer": "The /v1/load_lora_adapter endpoint ...",
 "sources": [{"file_path": "data/raw/vllm-0.10.1/docs/features/lora.md",
              "first_character_index": 4695, "last_character_index": 6098}],
 "difficulty": "synthetic", "is_valid": true}
```
Exactly **one** source per question in both public datasets, so recall@k is simply the hit rate.

**Out** — stdout only: `Recall@1 / @3 / @5 / @10`.

**Hit rule:** same `file_path` **and** `IoU >= 0.05`, where
`IoU = overlap / union` over the character ranges. A different file never counts.
Match questions by `question_id`, not by list position.

Never import or call the moulinette from your code.

### `answer`

```
answer "<query>" --k 10
```
Retrieve, then generate with `Qwen/Qwen3-0.6B`. Stdout: the answer text. No disk output.

### `answer_dataset`

```
answer_dataset --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
               --save_directory data/output/search_results_and_answer/UnansweredQuestions
```

**In** — the `StudentSearchResults` file written by `search_dataset`. The corpus is read only to
fetch each source's text by `file_path` + range; the index is not needed.

**Out** — `<save_directory>/<same basename>`, a `StudentSearchResultsAndAnswer`: the same
entries plus `"answer": "..."` on each.

**Stdout** — `Loaded <n> questions`, progress, `Saved student_search_results_and_answer to <path>`.

**Rules:** fit the retrieved context into the model's token budget; answers must be grounded in
those sources only. Grading weighs retrieval and grounding over final phrasing.

---

## 2. Data models (pydantic) — `[~]`

- [~] `MinimalSource` — written, but `models.py` imports `BaseModel` from `abc` instead of `pydantic`
- [ ] `UnansweredQuestion`, `AnsweredQuestion`
- [ ] `RagDataset`
- [ ] `MinimalSearchResults`, `MinimalAnswer`
- [ ] `StudentSearchResults`, `StudentSearchResultsAndAnswer`

Service functions (indexer, retriever) do **not** have to be pydantic — subject V.4.

---

## 3. Common instructions (chapter V)

- [x] Python >= 3.10 (project is on 3.13)
- [x] `uv` as package manager, `pyproject.toml` + `uv.lock` at root
- [x] CLI built with Python Fire, invoked as `uv run python -m src <command>`
- [x] tqdm progress bars
- [x] `.gitignore` for Python artifacts
- [ ] **restore the `data/` entry in `.gitignore`** (currently commented out — do not commit the corpus)
- [ ] declare `bm25s` instead of the `bm25` shim; add `pydantic`
- [ ] flake8 clean
- [ ] mypy clean: `--warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs`
- [ ] type hints on every function
- [ ] PEP 257 docstrings
- [ ] no unhandled exception anywhere; context managers for all file access
- [ ] Makefile: `install`, `run`, `debug`, `clean`, `lint` (+ optional `lint-strict`)
- [ ] tests (not graded, but asked for): pytest over chunkers and tokenizer

---

## 4. Required layout (VI.7.1)

```
src/                                      runnable as python -m src
pyproject.toml, uv.lock, README.md        at root
data/raw/                                 corpus (vllm-0.10.1)
data/processed/                           index output
data/datasets/{UnansweredQuestions,AnsweredQuestions}/
data/output/search_results/<Scope>/
data/output/search_results_and_answer/<Scope>/
```
- [x] `src/`, `pyproject.toml`, `uv.lock`, `data/raw`, `data/processed`, `data/datasets`
- [ ] `data/output/...` (created by `search_dataset`)
- [ ] no hardcoded paths — every input/output path a CLI argument

---

## 5. README (chapter VIII) — `[ ]`

First line, italic: `This project has been created as part of the 42 curriculum by <login>.`

- [ ] Description
- [ ] Instructions (install / run)
- [ ] Resources + how AI was used, per task
- [ ] System architecture
- [ ] Chunking strategy
- [ ] Retrieval method
- [ ] Performance analysis (recall@k, chunk-size effect, timings)
- [ ] Design decisions — why index every non-ignored file; why a custom tokenizer
- [ ] Challenges faced — IoU floor on small chunks; parallel meta/token lists
- [ ] Example usage

---

## 6. Known bugs

1. `hard_split` loops forever when `max_size <= 0` — `chunk_start` moves backwards. Guard in the function and validate in the CLI.
2. `models.py`: `from abc import BaseModel` → `from pydantic import BaseModel`.
3. `index()` print: count and path are swapped.
4. Dead code in `index.py`: `space`, `skip_file`, `skip_folder`, the `is_ignored(full_path, ...)` half.
5. `pyproject.toml` declares `bm25` (a shim that pulls `bm25s`) but the code imports `bm25s`.
6. Index currently on disk may be the ~62-char one — re-index at 2000 before measuring.

---

## 7. Bonus (only once mandatory fully validates)

- [ ] semantic embeddings (all-MiniLM-L6-v2) alongside the lexical index
- [ ] hybrid retrieval
- [ ] incremental indexing
- [ ] caching
- [ ] local HTTP API

---

## 8. Commands

```bash
uv sync
uv run python -m src index --max_chunk_size 2000
uv run python -m src search "How to configure OpenAI server?" --k 5

uv run python -m src search_dataset \
  --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json \
  --k 10 --save_directory data/output/search_results/UnansweredQuestions

./moulinette evaluate_student_search_results \
  data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  data/datasets/AnsweredQuestions/dataset_docs_public.json \
  --k 10 --max_context_length 2000

uv run python -m src answer_dataset \
  --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  --save_directory data/output/search_results_and_answer/UnansweredQuestions
```

---

## 9. Next up

1. Fix `models.py` import; write the remaining 7 models.
2. `search_dataset` → `StudentSearchResults`.
3. `evaluate` (own recall@k), then validate against the moulinette.
4. Qwen answer generation.
5. Markdown chunker, then re-measure.
6. Makefile, README, flake8, mypy.
