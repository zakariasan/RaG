# RAG against the machine — project map, status, and remaining work

Single tracking file for the 42 RAG project. Subject: `en_subject.md` (v2.0).
Legend: `[x]` done · `[~]` partial · `[ ]` not started

---

# PART A — What the project is

Build a question-answering system over the vLLM source tree. A frozen LLM knows nothing about
this specific codebase, so instead of retraining it, we **retrieve** the few relevant snippets
at question time and let a small model answer from them.

Four stages, each feeding the next:

| Stage | Meaning here |
|---|---|
| **Indexing** | cut every corpus file into chunks, tokenize them, build a BM25 index on disk |
| **Retrieving** | tokenize a question, score it against the index, return the top-k chunk locations |
| **Augmenting** | read those chunks' text back from disk and pack them into a prompt |
| **Generating** | Qwen3-0.6B reads that prompt and writes an answer |

**What is graded.** Almost entirely retrieval. A result is a *source location* —
`file_path` + `first_character_index` + `last_character_index` — and the moulinette checks
whether your top-k contains the reference location. Answer text is judged loosely because
Qwen3-0.6B is weak by design.

**Thresholds (chapter VII):** docs recall@5 >= 0.80, code recall@5 >= 0.50,
indexing <= 5 min, 200 questions retrieved <= 90 s, no chunk wider than 2000 characters.

## How recall@k is computed

Each public question has **exactly one** correct source, so recall@k is just a hit rate.
A hit needs both:
1. `file_path` **identical** to the reference, compared verbatim as a string, and
2. character ranges overlapping with `IoU >= 0.05`, where `IoU = overlap / union`.

The IoU floor is what punishes very small chunks: a 62-character chunk inside a 1400-character
reference span gives `62/1400 = 0.044`, which **fails** even though the chunk is correct.
That is measured below.

## Data flow

```
data/raw/vllm-0.10.1/**            corpus, 1969 .py/.md/.txt files (2693 counting all types)
        |
        |  index        chunkers -> (file, start, end) + text ; tokenizer -> token lists
        v
data/processed/                    chunks.json  (flat list, element i == chunk i)
                                   data.csc.index.npy / indices / indptr / vocab / params
        |
        |  search_dataset          questions in  ->  ranked source locations out
        v
data/output/search_results/<Scope>/<dataset>.json          StudentSearchResults
        |
        |  ./moulinette evaluate_student_search_results    (official recall@k)
        |
        |  answer_dataset          reads the file above, reads source text from the corpus,
        v                          prompts Qwen3-0.6B
data/output/search_results_and_answer/<Scope>/<dataset>.json   StudentSearchResultsAndAnswer
```

Note the LLM never sees the corpus or the index — only the sources already retrieved.

---

# PART B — Where we are

## B.1 Score

| Metric | Measured | Required | Verdict |
|---|---|---|---|
| Indexing time, whole corpus | **7 s** | <= 5 min | pass |
| Retrieval, 100 questions | **< 0.1 s** | 200 q <= 90 s | pass |
| **docs recall@5** | **0.830** (83/100) | >= 0.80 | pass, margin 3 questions |
| **code recall@5** | **0.657** (65/99) | >= 0.50 | pass, margin 16 questions |
| Chunk ceiling (best possible) | docs 96/100, code 98/99 | — | chunking is not the limit |

Retrieval — the hard half — already clears both bars. Remeasure after any change to chunking,
the file filter, or the tokenizer.

## B.2 Experiment log (keep for the README's Performance analysis)

| Change | docs R@5 | code R@5 | Conclusion |
|---|---|---|---|
| filter `.py/.md/.rst/.txt` (15 837 chunks) | 0.850 | 0.657 | best docs score so far |
| index every non-ignored file (18 738 chunks) | 0.830 | 0.657 | +2901 noise chunks cost 2 docs questions |
| `bm25s.tokenize` instead of ours | 0.830 | **0.525** | identifier splitting is worth 13 points on code |
| `max_chunk_size` ~62 chars (404 096 chunks) | **0.460** | **0.434** | both fail — IoU floor, 37 docs hits rejected despite the right file |

Tokenizer overlap, average shared tokens between a question and its correct chunk:
`text.split()` → docs 6.9 / code 3.1 · ours → docs 8.9 / code 6.3.

## B.3 File-by-file inventory

### `src/__main__.py` — `[~]`
Fire entry point. Registers `index` and `search`. Wraps the dispatch in `except Exception` so a
bug prints one line instead of a traceback, and catches `KeyboardInterrupt` separately
(correct, since it derives from `BaseException`, not `Exception`).
Missing: `search_dataset`, `answer`, `answer_dataset`, `evaluate`. Typo: `ERROR414`.

### `src/utils.py` — `[x]` logic, `[ ]` typing
- `ft_open(filename)` — read a whole file as UTF-8 text, via a context manager.
- `get_offsets(lines)` — cumulative character offset per line, so line numbers convert to
  character positions. Length is `len(lines) + 1`, with `[0]` first.
- `hard_split(s, e, line_offsets, max_size)` — greedy size-bounded split that prefers line
  boundaries, falling back to a mid-line cut only when a single line exceeds `max_size`.
  **Bug: infinite loop when `max_size <= 0`** (see C.1). No type hints anywhere in this file.

### `src/python_file_chunker.py` — `[x]`
- `chunk_nodes(...)` — the real algorithm. Converts each top-level AST node's start line to a
  character offset (walking back to the first decorator when present), builds consecutive
  `(start, end, node)` spans so the gaps between nodes — comments, blank lines — are never
  lost, then: oversized span with a body → recurse into `node.body`; oversized span without →
  `hard_split`; otherwise merge greedily with the running chunk while it fits.
- `chunk_pfile(filename, max_size)` — read, `ast.parse`, offsets, call `chunk_nodes`.
- **Verified:** on 156 stdlib files, slices rebuild every file exactly (no gaps, no overlaps)
  and no chunk exceeds the limit.
- Leftovers: dead commented block at the end; no type hints.

### `src/txt_file_chunker.py` — `[~]`
`chunk_txt_file` reads the file and calls `hard_split` on the whole thing. Works, but it is
line-splitting, **not a Markdown strategy** — the subject requires two genuinely distinct
strategies (see D.5).

### `src/index.py` — `[x]` working, `[~]` clean
- `git_file()` — parse `.gitignore` into patterns, skipping comments; appends `.git` and
  `.gitignore`. Blank lines still slip through; `except (FileNotFoundError, Exception)` should
  be `except OSError`.
- `is_ignored(name, patterns)` — `fnmatch` against each pattern after stripping `/` and a
  trailing `/*`, so `*.py[oc]`, `__pycache__/` and `/data/*` all work.
- `index_machine(main_path, max_size)` — phase 1 walks the tree, prunes ignored directories
  in place via `folder[:] = ...` (the slice assignment is what makes `os.walk` skip them) and
  collects paths; phase 2 chunks each file under one tqdm bar, slices the text, and appends to
  two parallel lists. Returns `(chunk_meta, chunk_texts)`.
- `tokenizer(string)` — words via `[A-Za-z0-9]+`, each kept whole and lowercased, plus its
  CamelCase pieces when it actually splits, 1-character tokens dropped. The lookahead
  `[A-Z]+(?=[A-Z][a-z])` is what makes `HTTPServer` → `HTTP` + `Server` instead of `HTTPS` +
  `erver`.
- `index(...)` — validates `max_chunk_size > 0`, writes `chunks.json`, tokenizes the corpus
  under a second bar, builds `bm25s.BM25`, saves to `save_dir`.
- Dead: `skip_file`, `skip_folder`, `space`. Print on lines 115-116 has count and path swapped.

### `src/search.py` — `[~]`
`search(query, k, save_dir, load_dir)` loads `chunks.json` and the BM25 index, tokenizes,
clamps `k`, retrieves, prints each hit. Edge cases handled: `k <= 0`, empty query, missing
index. **Two bugs** (C.2, C.3) and `search_dataset` is a stub nested inside `search`.

### `src/models.py` — `[~]`
Only `MinimalSource`. 7 models still missing.

### Dependencies — `[~]`
`fire`, `tqdm`, `pudb`, and `bm25` — which is a **shim** that merely pulls `bm25s`, the package
the code actually imports. `pydantic` is not declared at all.

## B.4 Stage checklist

**Indexing — `[x]`**
- [x] walk + gitignore filter · [x] Python AST chunker · [~] text chunker (no Markdown logic)
- [x] char offsets on every chunk · [x] size limit respected · [x] custom tokenizer
- [x] BM25 built and saved · [x] `chunks.json` in the same run · [x] two tqdm bars
- [x] `max_chunk_size <= 0` rejected in `index()` · [ ] same guard inside `hard_split`
- [ ] `sorted()` on files and folders for reproducible chunk ids

**Retrieval — `[~]`**
- [x] `search` single query, edge cases clean · [ ] output formatting bug (C.2)
- [ ] `search_dataset` · [ ] batched retrieve · [ ] output basename + dataset scoping

**Evaluation — `[ ]`** · **Answer generation — `[ ]`** · **Models — `[~]` 1/8**

---

# PART C — Open bugs

Ordered by severity.

**C.1 `hard_split` hangs forever on `max_size <= 0`** — `utils.py:34-35`.
`res.append((chunk_start, chunk_start + max_size))` then `chunk_start += max_size` moves
`chunk_start` **backwards**, so `while chunk_start < e` never ends and the list grows until the
OOM killer fires. `max_size == 0` never advances at all. Confirmed by timeout.
`index()` now rejects it at the CLI, but the function must guard itself — both chunkers call it.
Fix: `if max_size <= 0: raise ValueError(...)` at the top.

**C.2 `search` prints a literal f-string** — `search.py:31-34`. Only the first fragment is an
`f` string; the second is a plain literal, so output reads:
```
data/raw/.../test_serving_models.py [{c['first_character_index']}:{c['last_character_index']}]
```
Fix: one `f` string, or put `f` on both fragments.

**C.3 `search_dataset` is nested inside `search`** — `search.py:38-54`. Indented into the
function body after a `raise`, so it is unreachable and invisible to Fire. Also: `tqdm` is not
imported in this module; `save_dir` starts with `/` (filesystem root, `PermissionError`);
`dataset_path` defaults to `AnsweredQuestions/`, which is the **ground truth** and must never be
read while searching; and `json.load` returns `{"rag_questions": [...]}`, so iterating it yields
dict keys, not questions.

**C.4 `models.py` is 1/8 complete.** Blocks `search_dataset`, `answer_dataset` and every output
file.

**C.5 Dependency mismatch.** `pyproject.toml` declares `bm25`; the code imports `bm25s`.
`pydantic` undeclared. The moulinette runs only `uv sync`, so this must be exact.
Fix: `uv remove bm25 && uv add bm25s pydantic`.

**C.6 `index()` print swapped** — `index.py:115-116` emits
`Ingestion complete! Indexed chunks under 18738`.

**C.7 `.gitignore` has `data/` commented out.** Do not commit until restored; the corpus plus
index is hundreds of MB and git history keeps it forever.

**C.8 Dead code** — `index.py`: `skip_file`, `skip_folder`, `space`;
`python_file_chunker.py`: trailing commented block. flake8 will flag these.

**C.9 The index on disk may be stale.** Last inspection showed 404 096 chunks averaging 62
characters. Always re-run `index --max_chunk_size 2000` before measuring anything.

---

# PART D — Remaining work, in detail

Each task lists what it needs, what it produces, how to build it, and how to know it works.

## D.1 Finish `src/models.py` — pydantic data models

**Why:** these are the structures exchanged between stages and serialized to disk. The subject
mandates pydantic for them; service functions are explicitly exempt (V.4).

**Write, exactly as in VI.4:**
```python
class MinimalSource(BaseModel):            # done
    file_path: str
    first_character_index: int
    last_character_index: int

class UnansweredQuestion(BaseModel):
    question_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    question: str

class AnsweredQuestion(UnansweredQuestion):
    sources: List[MinimalSource]
    answer: str

class RagDataset(BaseModel):
    rag_questions: List[AnsweredQuestion | UnansweredQuestion]

class MinimalSearchResults(BaseModel):
    question_id: str
    question: str
    retrieved_sources: List[MinimalSource]

class MinimalAnswer(MinimalSearchResults):
    answer: str

class StudentSearchResults(BaseModel):
    search_results: List[MinimalSearchResults]
    k: int

class StudentSearchResultsAndAnswer(BaseModel):
    search_results: List[MinimalAnswer]
    k: int
```
Needs `import uuid`, `from typing import List`, `from pydantic import BaseModel, Field`.

**Careful:** the ground-truth files carry extra fields (`difficulty`, `is_valid`). Pydantic
ignores unknown fields by default, so `RagDataset` loads them fine. The union in `RagDataset`
is order-sensitive — pydantic tries `AnsweredQuestion` first and falls back, which is what you
want.

**Accept when:**
```python
RagDataset.model_validate_json(open('data/datasets/AnsweredQuestions/dataset_docs_public.json').read())
```
parses, and `StudentSearchResults(search_results=[], k=5).model_dump_json()` emits
`{"search_results":[],"k":5}`.

## D.2 `search_dataset` — the command the moulinette scores

**In:** `--dataset_path` (an `UnansweredQuestions` file), `--k`, `--save_directory`, plus the
index directory.
**Out:** `<save_directory>/<same basename as input>` holding a `StudentSearchResults`.

**Algorithm:**
1. Move it to module level — it must not be nested inside `search`.
2. Load the dataset, `RagDataset.model_validate_json(...)` inside `try/except` for a clean
   message on malformed JSON.
3. Load `chunks.json` and `BM25.load(save_dir)` **once**, before the loop.
4. `all_tokens = [tokenizer(q.question) for q in questions]`, then a **single**
   `retriever.retrieve(all_tokens, k=k)` for the whole dataset. Batching is what keeps 200
   questions far inside 90 s.
5. For row `i`, map each returned id through `chunks.json` into a `MinimalSource`, and build
   `MinimalSearchResults(question_id=..., question=..., retrieved_sources=[...])`.
6. `os.makedirs(save_directory, exist_ok=True)`, write
   `StudentSearchResults(search_results=rows, k=k).model_dump_json()`.
7. Print `Saved student_search_results to <path>`.

**Rules:** keep the input basename — the reference scripts pair files by name. Always scope
`--save_directory` by dataset folder, since the two public datasets share filenames and would
otherwise overwrite each other. A question tokenizing to nothing gets an empty
`retrieved_sources`, not a crash.

**Accept when:** both public datasets produce a file whose `search_results` length is 100 and
99, every `retrieved_sources` has `k` entries, and every `file_path` starts with
`data/raw/vllm-0.10.1/`.

## D.3 `evaluate` — your own recall@k

**In:** `--student_search_results_path`, `--dataset_path` (the `AnsweredQuestions` twin).
**Out:** stdout only, `Recall@1 / @3 / @5 / @10`.

**Algorithm:** index the ground truth by `question_id` into a dict — match by id, never by list
position. For each of your rows, take the first `k` sources in rank order and count a hit when
`file_path` matches and `IoU >= 0.05`. Divide hits by question count.

```python
def iou(a, b, c, d):
    inter = max(0, min(b, d) - max(a, c))
    union = max(b, d) - min(a, c)
    return inter / union if union else 0.0
```

**Why it matters:** this is your iteration loop. The moulinette is the official scorer, but you
cannot tune chunk size or tokenization without a fast local metric.

**Accept when:** it reproduces docs ~0.83 / code ~0.66 at `max_chunk_size 2000`, matching what
is in B.1.

## D.4 Validate against the moulinette

The executable is **not in the repo** — get it from the attachments, rename
`moulinette-ubuntu`/`-fedora` to `moulinette`, `chmod +x`.

```bash
./moulinette evaluate_student_search_results \
  data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  data/datasets/AnsweredQuestions/dataset_docs_public.json \
  --k 10 --max_context_length 2000
```
Look for `Student data is valid: True` before trusting any number. Do this **before** starting
on Qwen: a format mistake invalidates every output file, and one chunk wider than 2000
characters invalidates the whole run. Never import or call the moulinette from your code.

## D.5 Markdown chunking — a genuinely distinct strategy

The subject requires two strategies; today both paths end in `hard_split`. Markdown has
structure worth using, and the docs questions are the ones near the threshold.

**Approach:** find heading offsets with `re.finditer(r'^#{1,6} .*$', text, re.M)`, treat each
heading-to-next-heading span as a unit, merge consecutive small units up to `max_chunk_size`,
and `hard_split` any single oversized section. It is the same merge logic as `chunk_nodes`,
with headings in place of AST nodes.

**Watch out:** do not split inside a fenced code block — a ```` ``` ```` fence that opens in one
chunk and closes in another produces unusable context for the LLM.

**Accept when:** `evaluate` shows docs R@5 at or above 0.830. If it drops, keep the simpler
version and say so in the README — a measured negative result is a legitimate finding.

## D.6 Answer generation with Qwen3-0.6B

**Budget real time here:** the weights are a large download and CPU generation is slow.

**`answer <query> --k`:** retrieve, read each source's text back from its file and range, build
the prompt, generate, print.

**`answer_dataset --student_search_results_path --save_directory`:** read the
`StudentSearchResults` file from D.2 — not the corpus index — fetch each source's text, prompt
per question under a tqdm bar, and write `StudentSearchResultsAndAnswer` with an `answer` on
every row. Print `Loaded <n> questions` and `Saved student_search_results_and_answer to <path>`.

**Prompt shape:** system instruction to answer only from the provided sources and to say so
when they do not contain the answer; then the numbered sources; then the question. Keep the
context inside the model's token budget — count tokens with the tokenizer and drop the
lowest-ranked sources until it fits, rather than truncating mid-source.

**Accept when:** answers are coherent, grounded in the retrieved sources, and on point. The
subject explicitly relaxes this bar because of the model's size; retrieval and prompt strategy
are what is weighted.

## D.7 Robustness, flake8, mypy, type hints

- Type hints on **every** function. `utils.py` and both chunkers currently have none, and mypy
  runs with `--disallow-untyped-defs`.
- PEP 257 docstrings; fix the typos in the current ones (`igonore`, `waht`, `breakk`).
- Delete the dead code from C.8.
- Every file access through a context manager — already true, keep it so.
- Re-check the subject's edge cases per command: empty query, nonsensical query, `k=0`,
  negative `k`, missing file, malformed JSON, missing index. None may traceback.

## D.8 Makefile (V.2) — all rules mandatory

```make
install:      uv sync
run:          uv run python -m src index --max_chunk_size 2000
debug:        uv run python -m pdb -m src ...
clean:        rm -rf __pycache__ .mypy_cache ...
lint:         flake8 . && mypy . --warn-return-any --warn-unused-ignores \
                --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
lint-strict:  flake8 . && mypy . --strict        # optional
```
`clean` must not delete `data/`.

## D.9 README (chapter VIII)

First line, italic: `*This project has been created as part of the 42 curriculum by <login>.*`

Required sections: Description · Instructions · Resources **and how AI was used, per task** ·
System architecture · Chunking strategy · Retrieval method · Performance analysis ·
Design decisions · Challenges faced · Example usage. English only.

Material already available: the tables in B.1 and B.2 are your Performance analysis; the IoU
floor and the parallel-list invariant are your Challenges; "index every non-ignored file" and
"custom tokenizer over `bm25s.tokenize`" are your Design decisions, both with numbers behind
them.

## D.10 Tests (asked for, not graded)

pytest over: chunk slices reconstruct a file exactly; no chunk exceeds the limit;
`tokenizer('getHTTPResponseCode')` splits as expected; `hard_split` rejects `max_size <= 0`;
a chunker handles an empty file, a one-line file, and a file with no trailing newline.

## D.11 Bonus — only after the mandatory part fully validates

- [ ] semantic embeddings (all-MiniLM-L6-v2) beside the lexical index
- [ ] hybrid retrieval (fuse the two rankings)
- [ ] incremental indexing (re-index one changed file) — needs the `sorted()` ordering first
- [ ] caching (cold start + repeated queries)
- [ ] local HTTP API

---

# PART E — Command contracts

Every path is a CLI argument with a default; nothing hardcoded. All commands run from the repo
root as `uv run python -m src <command> [flags]`.

## `index`
```
index --max_chunk_size 2000 --files data/raw --save_dir data/processed
```
**In:** every non-ignored file under `--files`, plus `.gitignore` patterns.
**Out:** `<save_dir>/chunks.json` and 5 bm25s files.
**Stdout:** two tqdm bars, then `Ingestion complete! Indexed <n> chunks under <save_dir>`.

`chunks.json` — flat list, element `i` **is** chunk `i`:
```json
[{"file_path": "data/raw/vllm-0.10.1/setup.py",
  "first_character_index": 0, "last_character_index": 1894}, ...]
```
`file_path` exactly as walked from the repo root; compared verbatim by the grader.
`last - first <= max_chunk_size`, always.

bm25s files: `data.csc.index.npy` (weights), `indices.csc.index.npy` (chunk ids),
`indptr.csc.index.npy` (per-token offsets into those two), `vocab.index.json` (token → column),
`params.index.json` (k1, b, method). A query token becomes a column, the column becomes a slice,
the slice gives chunk ids and scores — no scan over 15 837 chunks, hence millisecond retrieval.

**Invariant:** `corpus_tokens[i]` ↔ `chunks.json[i]`, both written in the same run. Never sort,
filter or dedupe one without the other; a mismatch corrupts every result silently.

## `search`
```
search "<query>" --k 10 --save_dir data/processed
```
**In:** query string + saved index. **Out:** nothing on disk.
**Stdout:** `k` lines, best first — `data/raw/vllm-0.10.1/docs/features/lora.md [4745:6098]`.
**Edges:** `k <= 0` → message; empty query → message; `k > len(chunks)` → clamp; missing index
→ `index not found, run index first`; junk query → still returns top-k, which is correct.

## `search_dataset`
```
search_dataset --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json \
               --k 10 --save_directory data/output/search_results/UnansweredQuestions
```
**In:** `{"rag_questions": [{"question_id": "...", "question": "..."}, ...]}` — 100 docs, 99 code.
**Out:** `<save_directory>/<input basename>`:
```json
{"search_results": [
   {"question_id": "...", "question": "...",
    "retrieved_sources": [{"file_path": "...", "first_character_index": 0,
                           "last_character_index": 1403}]}],
 "k": 10}
```
Ranked best first; the same `file_path` may repeat with different ranges — one entry per chunk.
**Budget:** 200 questions <= 90 s.

## `evaluate`
```
evaluate --student_search_results_path <your output> --dataset_path <AnsweredQuestions file>
```
**In:** your results + ground truth, which adds:
```json
{"question_id": "...", "question": "...", "answer": "The /v1/load_lora_adapter endpoint ...",
 "sources": [{"file_path": "data/raw/vllm-0.10.1/docs/features/lora.md",
              "first_character_index": 4695, "last_character_index": 6098}],
 "difficulty": "synthetic", "is_valid": true}
```
**Out:** stdout `Recall@1 / @3 / @5 / @10`. Hit = same file **and** IoU >= 0.05. Match by
`question_id`.

## `answer` / `answer_dataset`
```
answer "<query>" --k 10
answer_dataset --student_search_results_path <search output> --save_directory <out dir>
```
**In:** the `StudentSearchResults` file; source text fetched from the corpus by path + range.
**Out:** `StudentSearchResultsAndAnswer` — same rows plus `"answer"`.

---

# PART F — Required layout (VI.7.1)

```
src/                                      runnable as python -m src        [x]
pyproject.toml, uv.lock, README.md        at root                          [x] / [ ] README empty
Makefile                                  install run debug clean lint     [ ]
data/raw/vllm-0.10.1/                     corpus                           [x]
data/processed/                           index output                      [x]
data/datasets/{UnansweredQuestions,AnsweredQuestions}/                     [x]
data/output/search_results/<Scope>/       from search_dataset              [ ]
data/output/search_results_and_answer/<Scope>/                             [ ]
```
Never commit `data/`, model weights, or generated output.

---

# PART G — Be able to explain at the defense

- Why chunks carry character offsets rather than text, and how `get_offsets` converts AST line
  numbers into them.
- Why gaps between AST nodes are preserved — module docstrings, imports, comments are
  retrievable content.
- Why the tokenizer keeps the whole identifier **and** its parts: exact quotes match the whole,
  paraphrases match the parts, with 13 recall points on code as evidence.
- Why `[A-Z]+(?=[A-Z][a-z])` rather than `[A-Z]+(?=[a-z])`: `HTTPServer` → `HTTP` + `Server`
  versus `HTTPS` + `erver`.
- Why BM25 needs no stopword list: IDF drives common tokens to near-zero weight.
- Why the parallel-list invariant matters and how a mismatch fails silently.
- Why tiny chunks destroy recall despite being more precise — the IoU 0.05 floor.
- Why `folder[:] = [...]` prunes the walk but `folder = [...]` does not.

---

# PART H — Order of work

1. **C.5** `uv remove bm25 && uv add bm25s pydantic` — unblocks everything.
2. **D.1** finish `models.py`.
3. **C.2** fix the `search` f-string; **C.1** guard `hard_split`.
4. **C.9** re-index at 2000; confirm B.1 still holds.
5. **D.2** `search_dataset`.
6. **D.3** `evaluate`, then **D.4** validate with the moulinette.
7. **D.6** Qwen answer generation.
8. **D.5** Markdown chunker, then re-measure.
9. **D.7 / D.8 / D.9** lint, Makefile, README.
10. **C.7** restore `data/` in `.gitignore`, then commit and push.
11. **D.11** bonus, only once the mandatory part fully validates.
