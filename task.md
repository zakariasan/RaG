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
Fire entry point. Registers `index` and `search` only. `KeyboardInterrupt` is caught separately
(correct, since it derives from `BaseException`, not `Exception`), but the `except Exception`
catch-all is **commented out**, so any bug now prints a full traceback instead of one line
(C.6). Missing from the command dict: `search_dataset`, `evaluate`, `answer`,
`answer_dataset`. Typo to keep in mind: `ERROR414`.

### `src/utils.py` — `[x]` logic, `[ ]` typing
- `ft_open(filename)` — read a whole file as UTF-8 text, via a context manager.
- `get_offsets(lines)` — cumulative character offset per line, so line numbers convert to
  character positions. Length is `len(lines) + 1`, with `[0]` first.
- `hard_split(s, e, line_offsets, max_size)` — greedy size-bounded split that prefers line
  boundaries, falling back to a mid-line cut only when a single line exceeds `max_size`.
  Rejects `max_size <= 0` with `ValueError` — the old infinite loop is **fixed**. No type
  hints anywhere in this file.

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
- `search(query, k, save_directory, load_dir)` — **works**. Loads `chunks.json` and the BM25
  index, tokenizes, clamps `k` to the corpus size, retrieves, prints `path [start:end]` per
  hit. Edge cases handled: `k <= 0`, empty query, missing index. The literal-f-string bug is
  fixed.
- `search_dataset(...)` — **now at module level** (no longer nested inside `search`), with the
  right default `dataset_path` (`UnansweredQuestions/dataset_docs_public.json`, never the
  ground truth), relative imports, one batched `retriever.retrieve` call, a correct
  `enumerate(tqdm(...))` loop and correct `MinimalSource` / `MinimalSearchResults` row
  construction. **Still does not run** — 7 bugs, C.1-C.5 and C.7.

### `src/models.py` — `[x]`
All 8 models from VI.4 present and verified: `MinimalSource`, `UnansweredQuestion`
(`question_id` defaults to `str(uuid.uuid4())` via `Field(default_factory=...)`),
`AnsweredQuestion`, `RagDataset`, `MinimalSearchResults`, `MinimalAnswer`,
`StudentSearchResults`, `StudentSearchResultsAndAnswer`. Checked: the ground truth parses
(100 questions, first row typed `AnsweredQuestion`) and
`StudentSearchResults(search_results=[], k=5).model_dump_json()` emits
`{"search_results":[],"k":5}`.

### Dependencies — `[~]`
Declared in `pyproject.toml`: `fire`, `tqdm`, `pudb`, `pydantic>=2.14.1` **and `bm25>=0.3.11`**
— which is a *shim* package whose only content is a dependency on `bm25s`, the library the code
actually imports. It works by accident (`uv sync` pulls `bm25s` transitively) but the manifest
names a package you never use, and `import bm25` would fail. See C.8. Missing for the answer
stage: `transformers`, `torch`.

## B.4 Stage checklist

**Indexing — `[x]`**
- [x] walk + gitignore filter · [x] Python AST chunker · [~] text chunker (no Markdown logic)
- [x] char offsets on every chunk · [x] size limit respected · [x] custom tokenizer
- [x] BM25 built and saved · [x] `chunks.json` in the same run · [x] two tqdm bars
- [x] `max_chunk_size <= 0` rejected in `index()` · [x] same guard inside `hard_split`
- [ ] `sorted()` on files and folders for reproducible chunk ids

**Retrieval — `[~]`**
- [x] `search` single query, edge cases clean, output formatting fixed
- [~] `search_dataset` written but cannot run (C.1-C.5, C.7) · [x] single batched `retrieve`
- [x] input basename kept on output · [x] `save_directory` scoped per dataset folder
- [ ] registered in Fire (C.6) · [ ] first valid output file produced

**Evaluation — `[ ]`** · **Answer generation — `[ ]`** · **Models — `[x]` 8/8**

---

# PART C — Open bugs

Ordered by severity. Every bug C.1-C.5 and C.7 lives in `search_dataset` (`src/search.py:49-83`)
— that one function is the only thing between you and a scorable output file.

**Fixed since the last pass**, keep for the defense: the `hard_split` infinite loop on
`max_size <= 0`; the `search` literal f-string; `search_dataset` being nested inside `search`;
the swapped `index()` print; `models.py` (now 8/8); the absolute `from models import ...`.

---

**C.1 The whole write block sits inside the `for` loop** — `search.py:77-83`.

What the code does now:
```python
for i, q in enumerate(tqdm(questions.rag_questions, ...)):
    srcs = [MinimalSource(**chunks[j]) for j in res[i]]
    rows.append(MinimalSearchResults(...))
    out = StudentSearchResults(search_results=rows, k=k)   # <-- indented into the loop
    os.makedirs(save_directory, exist_ok=True)             # <-- so are these
    path = os.path.join(save_directory, os.path.basename(dataset_path))
    with open(path, 'w') as f:
        f.write(out.model_dump_json(indent=4))
    print(f'Saved student_search_results to {path}')
```
**Why it is wrong:** indentation *is* the loop body in Python. Those six statements therefore
run once per question. With the docs dataset (100 questions) you get 100 `makedirs` calls,
100 full-file rewrites and 100 identical `Saved ...` lines on stdout.

**Example of the cost:** iteration 1 serializes 1 row, iteration 2 serializes 2 rows,
iteration 100 serializes 100 rows — total work 1+2+...+100 = 5050 row serializations instead
of 100. That is quadratic: on a 1000-question dataset it is 500 500 serializations. The *final*
file is correct by accident (the last write holds every row), so a test on the file content
would pass while the command is still broken — this is exactly the class of bug the defense
asks about.

**Fix:** dedent those six lines one level, so they sit after the loop:
```python
    rows.append(MinimalSearchResults(...))

out = StudentSearchResults(search_results=rows, k=k)
os.makedirs(save_directory, exist_ok=True)
path = os.path.join(save_directory, os.path.basename(dataset_path))
with open(path, 'w', encoding='utf-8') as f:
    f.write(out.model_dump_json(indent=4))
print(f'Saved student_search_results to {path}')
```

---

**C.2 `StudentSearchResults` is used but never imported** — `search.py:8-12` vs `77`.

```python
from .models import (
    RagDataset,
    MinimalSource,
    MinimalSearchResults     # StudentSearchResults missing
)
...
out = StudentSearchResults(search_results=rows, k=k)   # line 77
```
**Why it is wrong:** a name only exists in a module if it is imported or defined there. Python
resolves it at *run* time, not import time, so the file imports cleanly and flake8 reports
`F821 undefined name` while the crash only happens when the loop reaches line 77:
```
NameError: name 'StudentSearchResults' is not defined
```
**Fix:** add `StudentSearchResults` to the import tuple.

---

**C.3 The dataset is handled as a raw dict, not as a model** — `search.py:57-59`, `63`, `69`.

```python
with open(dataset_path, encoding='utf-8') as f:
    questions = json.load(f)        # questions is now a dict
RagDataset.model_validate_json(questions)   # wrong input type, result thrown away
...
all_tokens = [tokenizer(q.question) for q in questions.rag_questions]   # AttributeError
```
**Three separate mistakes in three lines:**

1. `model_validate_json` expects **raw JSON text** (`str` / `bytes`). You hand it an already
   parsed `dict`, so pydantic raises
   `ValidationError: Invalid JSON: expected value at line 1 column 1`. The dict-shaped twin is
   `model_validate` — but you do not need it, see the fix.
2. The return value is **discarded**. `RagDataset.model_validate_json(...)` returns the parsed
   model; calling it as a bare statement validates and throws the result away. That is why the
   next lines fall back to the dict.
3. `questions` is a plain `dict`, and dicts have no attributes. `questions.rag_questions`
   raises `AttributeError: 'dict' object has no attribute 'rag_questions'`. The dict-style
   access would be `questions['rag_questions']`, but then each element is a dict too, so
   `q.question` fails next — and you lose the validation the subject asks for.

**Example of the difference:**
```python
raw = '{"rag_questions": [{"question_id": "a1", "question": "What is PagedAttention?"}]}'

d = json.loads(raw)
d.rag_questions          # AttributeError
d['rag_questions'][0].question   # AttributeError again (element is a dict)

ds = RagDataset.model_validate_json(raw)
ds.rag_questions[0].question     # 'What is PagedAttention?'  typed, validated
```
**Fix** — drop the `json.load`, parse once into the model, use `ds` everywhere:
```python
ds = RagDataset.model_validate_json(ft_open(dataset_path))
...
all_tokens = [tokenizer(q.question) for q in ds.rag_questions]
for i, q in enumerate(tqdm(ds.rag_questions, desc='Searching', unit=' question')):
```
`ft_open` is already imported on line 14. Wrap the parse in `try/except ValidationError` later
for a clean message on a malformed dataset.

---

**C.4 Two default paths start with `/`** — `search.py:52-53`.

```python
save_directory: str = '/data/output/search_results/UnansweredQuestions',
save_processed='/data/processed/chunks.json'
```
**Why it is wrong:** a leading `/` is an **absolute** path — it means the filesystem root, not
your project. `os.path.join('/data/...', x)` stays absolute, and `os.makedirs` then tries to
create `/data` next to `/home` and `/etc`:
```
PermissionError: [Errno 13] Permission denied: '/data'
```
This is the same bug that already bit `index()` once. **Fix:** remove the leading slash on
both. Also give `save_processed` a type hint (`save_processed: str = ...`) — mypy flags an
untyped parameter in an otherwise annotated signature.

---

**C.5 BM25 is loaded from the output folder, and `save_processed` points at a file** —
`search.py:53`, `61`, `64`.

```python
save_processed='/data/processed/chunks.json'   # a FILE
...
with open(save_processed, encoding='utf-8') as f:   # ok, it is a file
    chunks = json.load(f)
retriever = bm25s.BM25.load(save_directory)         # WRONG dir: that is the OUTPUT folder
```
**Why it is wrong:** `bm25s.BM25.load(d)` expects the directory holding the five artifacts
`index()` wrote — `data.csc.index.npy`, `indices.csc.index.npy`, `indptr.csc.index.npy`,
`vocab.index.json`, `params.index.json`. `save_directory` is where *results* go and holds none
of them, so you get `FileNotFoundError: .../vocab.index.json`. The index lives in
`data/processed`, which is what `save_processed` should name — as a **directory**, with
`chunks.json` joined onto it, exactly like `search` already does on line 30.

**Fix:**
```python
save_processed: str = 'data/processed'
...
with open(os.path.join(save_processed, 'chunks.json'), encoding='utf-8') as f:
    chunks = json.load(f)
retriever = bm25s.BM25.load(save_processed)
```
**Why `chunks.json` and the index must come from the same directory:** retrieval returns
**integer row ids**, not text. `res[i] == [417, 23, ...]` only means something when
`chunks[417]` is the chunk that was token-row 417 at index time. The two files are a matched
pair written in one `index()` run; mixing a new index with an old `chunks.json` silently
returns the wrong offsets with no error at all.

---

**C.6 `search_dataset` is not reachable from the CLI, and errors are unhandled** —
`__main__.py:3-10`.

```python
from .index import index
from .search import search

fire.Fire({'index': index, 'search': search})
# except Exception as e:
#    print(f"ERROR414: {e}")
```
**Why it is wrong:** Fire only exposes the keys of that dict. `uv run python -m src
search_dataset ...` therefore dies with Fire's usage error, not your code — the command the
moulinette needs does not exist. Separately, the commented-out `except Exception` means every
bug above prints a 20-line traceback instead of one message; the subject asks the program never
to crash on bad input.

**Fix:**
```python
from .search import search, search_dataset
...
    fire.Fire({'index': index, 'search': search, 'search_dataset': search_dataset})
    except Exception as e:
        print(f"ERROR414: {e}")
```
Keep `except KeyboardInterrupt` **after** it only if it stays a separate clause — it is not a
subclass of `Exception`, so order does not matter here, but it must not be removed.

---

**C.7 `open(path, 'w')` with no encoding** — `search.py:81`.
Python picks the platform default (`locale.getpreferredencoding()`). On a machine with
`LC_ALL=C` that is ASCII, and a single non-ASCII character in a question explodes:
`UnicodeEncodeError: 'ascii' codec can't encode character`. Every other `open` in the project
already passes `encoding='utf-8'`. **Fix:** pass it here too.

---

**C.8 Dependency mismatch** — `pyproject.toml`.
Declares `bm25>=0.3.11`; the code imports `bm25s`. `bm25` is a **shim** package whose only
content is a dependency on `bm25s`, so `uv sync` happens to install the real library and the
import works today — but `import bm25` would fail, and the declaration describes a package you
never use. The moulinette runs only `uv sync`, so the manifest must be exact.
**Fix:** `uv remove bm25 && uv add bm25s` (you run it, not me).

---

**C.9 `.gitignore` has `data/` commented out.** Do not commit until it is restored. The corpus
plus the index is hundreds of MB, and git keeps a blob forever once it is in history — a later
`git rm` does not shrink the repo. Verify with `git status --short | head` before any `git add`.

---

**C.10 Dead code** — `index.py`: `skip_file`, `skip_folder` (both superseded by `is_ignored`,
which is pattern-based instead of exact-match) and `space`; `python_file_chunker.py`: the
trailing commented block; `index.py:135`: the commented `bm25s.tokenize` line. flake8 flags
unused names, and the defense will ask what they are for.

---

**C.11 The index on disk may be stale.** One earlier run left 404 096 chunks averaging 62
characters, which fails both thresholds (docs 0.460, code 0.434 — see B.2). Always rebuild with
`uv run python -m src index --max_chunk_size 2000` before measuring anything, and re-measure
after any change to chunking, the file filter or the tokenizer.

---

# PART D — Remaining work, in detail

Each task lists what it needs, what it produces, how to build it, and how to know it works.

## D.1 `src/models.py` — pydantic data models — **DONE**

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

## D.2 `search_dataset` — the command the moulinette scores — **next task**

**Why this command exists.** `search` answers *one* query typed by a human and prints to the
terminal. Nothing can grade that. `search_dataset` is the batch form: it takes a whole file of
questions, retrieves for all of them, and writes **one JSON file in the exact shape the
reference scripts expect**. Everything downstream — your `evaluate`, the moulinette's
`check_data_validity`, the answer stage — reads that file. It is the deliverable, `search` is
the debugging tool.

**In:**
- `--dataset_path` — an `UnansweredQuestions` file (questions only, **no** `sources`, **no**
  `answer`). Never point this at `AnsweredQuestions/`: that is the ground truth, and reading it
  while searching would be reading the exam answers.
- `--k` — how many chunks to return per question (5 for the graded runs).
- `--save_directory` — where the output file goes.
- `--save_processed` — the index directory from `index()`, holding the BM25 artifacts **and**
  `chunks.json`.

**Out:** `<save_directory>/<same basename as the input>`, containing a `StudentSearchResults`:
```json
{
    "search_results": [
        {
            "question_id": "e3b0c442-...",
            "question": "How does vLLM implement LoRA?",
            "retrieved_sources": [
                {"file_path": "data/raw/vllm-0.10.1/vllm/lora/layers.py",
                 "first_character_index": 10421,
                 "last_character_index": 12380}
            ]
        }
    ],
    "k": 5
}
```
`retrieved_sources` is ordered best-first and has `k` entries. The offsets are character
indices into the file named by `file_path` — the chunk text itself is never stored, which is
why `chunks.json` and the index must be the matched pair from one `index()` run (C.5).

**Algorithm, with what is already true of your code:**
1. `[x]` module level, not nested inside `search`.
2. `[ ]` parse the dataset **once** into a `RagDataset` and keep the result (C.3).
3. `[ ]` load `chunks.json` and `BM25.load(...)` once, before the loop, from the index
   directory (C.5). Loading inside the loop would re-read the whole index per question.
4. `[x]` `all_tokens = [tokenizer(q.question) for q in ds.rag_questions]`, then a **single**
   `retriever.retrieve(all_tokens, k=k)`.
   **Why batch:** `bm25s` turns the list of token lists into one scoring pass over the sparse
   matrix instead of 100 separate passes. Measured: 100 questions in under 0.1 s, against a
   budget of 90 s for 200 — batching is the reason the margin is three orders of magnitude.
5. `[x]` for row `i`, map each id in `res[i]` through `chunks.json` into a `MinimalSource`, and
   build one `MinimalSearchResults`.
   **Why `MinimalSource(**chunks[j])` works:** `chunks.json` was written with
   `item.model_dump()`, so each entry already has exactly the three keys the model declares —
   `{"file_path": ..., "first_character_index": ..., "last_character_index": ...}` — and `**`
   spreads them onto the constructor as keyword arguments.
6. `[ ]` **after** the loop (C.1), build `StudentSearchResults(search_results=rows, k=k)`,
   `os.makedirs(save_directory, exist_ok=True)`, write `model_dump_json(indent=4)` with
   `encoding='utf-8'` (C.7).
7. `[ ]` print `Saved student_search_results to <path>` **once**.
8. `[ ]` register it in `__main__.py` (C.6).

**Rules and the reason for each:**
- *Keep the input basename.* The reference scripts pair a student file with its ground truth by
  filename, so `dataset_docs_public.json` in must come out as `dataset_docs_public.json`. A
  renamed file scores zero without any error message.
- *Scope `save_directory` per dataset folder.* `UnansweredQuestions/dataset_docs_public.json`
  and `AnsweredQuestions/dataset_docs_public.json` share a basename. Flat output means the
  second run silently overwrites the first. Example of the trap:
  `data/output/search_results/dataset_docs_public.json` — whose results are those? Use
  `data/output/search_results/UnansweredQuestions/...`.
- *A question that tokenizes to nothing gets an empty `retrieved_sources`, not a crash.* Your
  `tokenizer` drops 1-character tokens, so a question like `"a b ?"` yields `[]`. Decide the
  behaviour explicitly rather than letting `bm25s` raise.

**Fix order — smallest number of edits to a working command:**
1. C.2 add `StudentSearchResults` to the import. (1 line)
2. C.3 replace lines 57-59 with `ds = RagDataset.model_validate_json(ft_open(dataset_path))`,
   then `questions.rag_questions` → `ds.rag_questions` twice. (3 lines)
3. C.4 drop the two leading slashes. (2 lines)
4. C.5 `save_processed: str = 'data/processed'`, join `chunks.json`, load BM25 from it.
   (3 lines)
5. C.1 dedent the write block. (6 lines)
6. C.7 add `encoding='utf-8'`. (1 line)
7. C.6 register in `__main__.py` and uncomment the catch-all. (3 lines)

**Run it:**
```sh
uv run python -m src search_dataset \
  --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json \
  --k 5 \
  --save_directory data/output/search_results/UnansweredQuestions \
  --save_processed data/processed
```

**Accept when:** both public datasets produce a file printing **one** `Saved ...` line, whose
`search_results` length is 100 (docs) and 99 (code), every `retrieved_sources` has exactly `k`
entries, every `question_id` matches the input dataset, and every `file_path` starts with
`data/raw/vllm-0.10.1/`. Check block 7 in `checker.md` runs all of that.

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
               --k 5 \
               --save_directory data/output/search_results/UnansweredQuestions \
               --save_processed data/processed
```
**Defaults today:** `k=5`, and `save_directory` / `save_processed` still carry a leading `/`
(C.4). `save_processed` must be the **directory** that `index()` wrote, because both
`chunks.json` and the five BM25 artifacts are read from it (C.5).
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

Each step is small and leaves the project in a runnable state.

1. **C.2, C.3, C.4, C.5, C.1, C.7** — the seven `search_dataset` edits, in the order listed at
   the end of D.2. *Reason:* nothing downstream can be built or measured until one valid
   output file exists.
2. **C.6** register `search_dataset` in `__main__.py` and uncomment `except Exception`.
   *Reason:* the function is unreachable from the CLI until this is done, so step 1 is
   untestable without it — do both in the same sitting.
3. **C.11** re-index at `--max_chunk_size 2000`, then run `search_dataset` on **both** public
   datasets. *Reason:* the index on disk may still be the 404 096-chunk run that fails both
   thresholds; measuring against it would send you chasing a problem that does not exist.
4. **D.3** `evaluate` — your own recall@k with the IoU >= 0.05 rule, matched by `question_id`.
   *Reason:* this is the feedback loop. Without it, every later change to chunking or
   tokenizing is a guess.
5. **D.4** validate with the moulinette (`Student data is valid: True`). *Reason:* catches
   shape errors your own evaluator would never notice, e.g. a renamed output file.
6. **C.8** `uv remove bm25 && uv add bm25s`. *Reason:* the moulinette runs only `uv sync`.
7. **D.6** Qwen3-0.6B answer generation. *Reason:* biggest remaining chunk of the mandatory
   part, and it depends on step 1's output format.
8. **D.5** Markdown chunker as a genuinely distinct strategy, then re-measure docs recall.
   *Reason:* the subject names exactly two strategies; `chunk_txt_file` is currently just
   `hard_split`, i.e. one strategy wearing two hats.
9. **C.10, D.7** remove dead code, type hints everywhere, flake8 + mypy clean.
10. **D.8, D.9** Makefile rules and the README's 10 sections, including the B.2 experiment
    table as the Performance analysis.
11. **C.9** restore `data/` in `.gitignore`, verify with `git status --short`, then commit and
    push. *Reason:* once a 100 MB blob is in history it stays there.
12. **D.11** bonus, only after the mandatory part fully validates.
