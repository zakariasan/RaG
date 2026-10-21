# completed.md — how this project works, part by part

Reference document for the 42 project **RAG against the machine** (subject `en_subject.md`,
v2.0). This file explains the system and holds everything already built, verified and measured.
It is also the defense preparation: every "why" is here.

What is **left to do** is not in this file — that is `task.md`.
How to **test** each part is in `checker.md`.
How the **LLM / answer generation** works, with reading links, is in `explaination.md`.

---

# 1. What the project is

Build a question-answering system over the **vLLM** source tree.

The problem: an LLM frozen at training time knows nothing about this specific codebase. Two
ways out — retrain the model on it (expensive, slow, needs a GPU farm) or **retrieve** the few
relevant snippets at question time and hand them to the model as context. This project is the
second one. The model stays frozen; the intelligence is in the retrieval.

## 1.1 The four stages

| Stage | What happens here | Our code |
|---|---|---|
| **Indexing** | cut every corpus file into chunks, tokenize them, build a BM25 index on disk | `index.py`, both chunkers |
| **Retrieving** | tokenize a question, score it against the index, return the top-k chunk *locations* | `search.py` |
| **Augmenting** | read those chunks' text back from disk, pack them into a prompt | not written yet — planned in `rag_flow.py`, see `explaination.md` |
| **Generating** | Qwen3-0.6B reads that prompt, writes an answer | not written yet — planned in `rag_flow.py`, see `explaination.md` |

Each stage feeds the next and only the next. The LLM never sees the corpus or the index — only
the handful of sources retrieval already selected. That separation is the whole point of RAG:
the expensive, stupid component (the LLM) is given a tiny, highly relevant input.

## 1.2 What is actually graded

Almost entirely **retrieval**. A result is not text, it is a *source location*:

```json
{"file_path": "data/raw/vllm-0.10.1/docs/features/lora.md",
 "first_character_index": 4695,
 "last_character_index": 6098}
```

The grader checks whether your top-k contains the reference location. Answer text is judged
loosely, on purpose, because Qwen3-0.6B is a weak model by design — the subject wants to see
retrieval engineering, not model quality.

**Thresholds (chapter VII):**

| Requirement | Value |
|---|---|
| docs recall@5 | >= 0.80 |
| code recall@5 | >= 0.50 |
| indexing, whole corpus | <= 5 min |
| retrieval, 200 questions | <= 90 s |
| widest chunk | <= 2000 characters |

## 1.3 How recall@k is computed

Each public question has **exactly one** correct source, so recall@k is really a hit rate:
"did the right chunk appear in my top k?"

A hit needs **both** conditions:

1. `file_path` **identical** to the reference — compared verbatim as a string. `./data/raw/x`
   and `data/raw/x` are different strings and therefore a miss.
2. character ranges overlapping with **IoU >= 0.05**, where `IoU = overlap / union`.

```python
def iou(a, b, c, d):
    inter = max(0, min(b, d) - max(a, c))
    union = max(b, d) - min(a, c)
    return inter / union if union else 0.0
```

**Why the IoU floor matters so much.** It punishes chunks that are too small. A 62-character
chunk sitting inside a 1400-character reference span scores `62 / 1400 = 0.044`, which **fails**
— even though the chunk is literally inside the correct answer. We measured this: see 6.2.

---

# 2. Data flow

```
data/raw/vllm-0.10.1/**            corpus: 1969 .py/.md/.txt files (2693 counting all types)
        |
        |  index      chunkers -> (file, start, end) + text ; tokenizer -> token lists
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

---

# 3. Indexing — how it works

## 3.1 Why chunks store offsets, not text

Every chunk is a triple: `(file_path, first_character_index, last_character_index)`. The text
itself is **never** stored in the index.

Reasons:
- The grader compares locations, so locations are the product.
- `chunks.json` stays small relative to the corpus; duplicating 500 MB of source text would be
  pointless when the files are right there on disk.
- The text is recoverable exactly: `ft_open(path)[first:last]`.

The price: `chunks.json` and the BM25 index must stay in sync (see 3.6).

## 3.2 File discovery — `index_machine`, phase 1

```python
for path, folder, files in os.walk(main_path):
    folder[:] = [d for d in folder if not is_ignored(d, pattern)]
    for file in files:
        if is_ignored(file, pattern):
            continue
        files_work.append(os.path.join(path, file))
```

Two details that matter:

**`folder[:] = [...]` versus `folder = [...]`.** `os.walk` reads the directory list *after*
yielding it and descends into whatever is still in it. `folder[:] = [...]` mutates the list
in place, so the walk sees the change and never descends into `.git`, `__pycache__` or
`.venv`. `folder = [...]` would rebind a local name, the original list would be untouched, and
the walk would descend anyway — thousands of useless files, no error, just a slow index full of
junk.

**`.gitignore` as the filter.** `git_file()` parses `.gitignore` into patterns, skipping
comments, and appends `.git` and `.gitignore` itself. `is_ignored` then runs `fnmatch` after
`strip('/')` and `removesuffix('/*')`, which is what makes `*.py[oc]`, `__pycache__/` and
`/data/*` all match the plain names `os.walk` hands over.

## 3.3 Python chunking — AST based

`python_file_chunker.chunk_pfile` reads the file, `ast.parse`s it, builds line offsets, then
`chunk_nodes` does the work:

1. For each **top-level** AST node, convert its start line to a character offset — walking back
   to the **first decorator** when the node has them, so `@app.route(...)` stays attached to the
   function it decorates.
2. Build **consecutive** spans `(start, end, node)` so the gaps between nodes are never lost.
   Module docstrings, imports, licence headers and standalone comments are retrievable content;
   questions get asked about them.
3. Then per span:
   - oversized **and** the node has a body → recurse into `node.body`, so a 3000-line class
     becomes per-method chunks instead of one unusable blob;
   - oversized with **no** body (a giant dict literal, a long string) → `hard_split`;
   - otherwise → merge greedily with the running chunk while it still fits under `max_size`.

**Why AST rather than fixed-size cuts:** a function split in half mid-body gives the LLM
context that does not even parse, and splits the identifiers a lexical index relies on. Node
boundaries are semantic boundaries.

**Verified:** on 156 stdlib files and again on the whole corpus — the slices rebuild every file
**exactly**, with no gaps, no overlaps, and no chunk over the limit.

## 3.4 Text chunking

`txt_file_chunker.chunk_txt_file` reads the file and calls `hard_split` over the whole thing:
a greedy size-bounded split that prefers line boundaries and only cuts mid-line when a single
line is itself longer than `max_size`. It works, and it is the fallback for everything that is
not `.py`.

## 3.5 The tokenizer — and why we wrote our own

```python
def tokenizer(string: str) -> list[str]:
    res = []
    words = re.findall(r'[A-Za-z0-9]+', string)
    for item in words:
        res.append(item.lower())
        parts = re.findall(
            r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+', item)
        if len(parts) > 1:
            for part in parts:
                res.append(part.lower())
    return [ibm for ibm in res if len(ibm) > 1]
```

**What a tokenizer is for.** BM25 does not compare strings, it compares **bags of tokens**. The
tokenizer decides what counts as a word, and therefore what can ever match. Everything the
tokenizer throws away is invisible to retrieval forever.

**Why keep the whole identifier *and* its parts.** A question quoting code exactly
(`"what does get_num_layers do"`) needs the whole token `get_num_layers`. A question
paraphrasing (`"how are the number of layers counted"`) needs the pieces `num`, `layers`.
Emitting both covers both styles. Evidence: see the A/B in 6.1 — 13 recall points on code.

**Why the lookahead is `[A-Z]+(?=[A-Z][a-z])` and not `[A-Z]+(?=[a-z])`:**

| Identifier | `(?=[A-Z][a-z])` | `(?=[a-z])` |
|---|---|---|
| `HTTPServer` | `HTTP` + `Server` | `HTTPS` + `erver` |
| `parseJSONData` | `parse` + `JSON` + `Data` | `parse` + `JSOND` + `ata` |

The second form steals the capital that begins the next word. The first stops the run of
capitals one character early, which is exactly where the next word starts.

**Why `len(parts) > 1` and not `len(item) > 1`.** The guard asks "did this word actually
split?". Guarding on character count instead emits every plain word **twice**, doubling its term
frequency against identifier pieces and quietly distorting every BM25 score. That was a real
bug here; it is fixed.

**Why 1-character tokens are dropped:** `a`, `i`, `x` carry no retrieval signal and bloat the
vocabulary.

**Why no stopword list is needed:** BM25's IDF term already drives tokens that appear in almost
every chunk to a near-zero weight. A manual stopword list would duplicate the maths, badly.

## 3.6 BM25 and the index on disk

`bm25s.BM25()` with `method='lucene'`, `k1=1.5`, `b=0.75`. `retriever.index(corpus_tokens)`
then `retriever.save(save_dir)` writes five files:

| File | Content |
|---|---|
| `data.csc.index.npy` | the weights |
| `indices.csc.index.npy` | chunk ids |
| `indptr.csc.index.npy` | per-token offsets into the two above |
| `vocab.index.json` | token -> column |
| `params.index.json` | k1, b, method |

**How a lookup works:** a query token becomes a column via `vocab`, the column becomes a slice
via `indptr`, and the slice yields chunk ids plus scores from `indices` and `data`. No scan over
15 837 chunks — that is why retrieval is in milliseconds.

**THE INVARIANT — `corpus_tokens[i]` <-> `chunks.json[i]`.** Retrieval returns **integer row
ids**, not text. `res[i] == [417, 23, ...]` only means something if `chunks[417]` is the chunk
that was token-row 417 at index time. The two files are a matched pair written in a single
`index()` run. Never sort, filter or dedupe one without the other, and never mix a fresh index
with an old `chunks.json`: the result is wrong offsets with **no error at all**.

(`os.walk` ordering is not sorted and not guaranteed stable across machines. That does not
matter here, because both files are produced by the same walk in the same run. It *would* matter
for incremental indexing — which is why sorting is a prerequisite for that bonus.)

## 3.7 tqdm

The subject mandates progress bars on long operations. Two bars: one over files in the chunking
phase, one over chunks in the tokenizing phase.

**Rule learned the hard way:** create the bar **once**, over the outermost iterable. A `tqdm`
inside a per-file loop produced 1847 separate bars scrolling past.

---

# 4. Retrieval — how it works

## 4.1 `search` — one query, for humans

```
uv run python -m src search "<query>" --k 10 --save_directory data/processed
```

Loads `chunks.json` and the BM25 index, tokenizes the query **with the same tokenizer used at
index time** (non-negotiable: a different tokenizer means the question's tokens do not exist in
the vocabulary), clamps `k` to the corpus size, retrieves, and prints one line per hit:

```
data/raw/vllm-0.10.1/docs/features/lora.md [4745:6098]
```

Edge cases handled: `k <= 0`, empty query after tokenizing, missing index.

**Its role:** debugging and demonstration. Nothing can grade terminal output.

## 4.2 `search_dataset` — the command that gets scored

```
uv run python -m src search_dataset \
  --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json \
  --k 5 \
  --save_directory data/output/search_results/UnansweredQuestions \
  --save_processed data/processed
```

**In:** an `UnansweredQuestions` file — questions only, **no** `sources`, **no** `answer`.
Never point this at `AnsweredQuestions/`: that is the ground truth, i.e. the exam answers.

**Out:** `<save_directory>/<same basename as the input>`, holding a `StudentSearchResults`:

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

**How it works, and why each step is that way:**

1. Parse the dataset once into a `RagDataset`. Typed access (`q.question`, `q.question_id`)
   instead of dict juggling, and validation comes free.
2. Load `chunks.json` and `BM25.load(...)` **once, before** the loop. Inside the loop it would
   re-read the whole index per question.
3. `all_tokens = [tokenizer(q.question) for q in ds.rag_questions]`, then **one**
   `retriever.retrieve(all_tokens, k=k)` for the whole dataset. `bm25s` turns that into a single
   scoring pass over the sparse matrix instead of 100 separate passes. Measured: 100 questions
   in under 0.1 s against a 90 s budget for 200 — batching is why the margin is three orders of
   magnitude.
4. For row `i`, map each id in `res[i]` through `chunks.json` into a `MinimalSource`.
   **Why `MinimalSource(**chunks[j])` works:** `chunks.json` was written with
   `item.model_dump()`, so each entry already holds exactly the three keys the model declares,
   and `**` spreads them as keyword arguments.
5. **After** the loop: build `StudentSearchResults(search_results=rows, k=k)`, `os.makedirs`,
   write `model_dump_json(indent=4)`, print once. Inside the loop this is quadratic — 100
   questions means 1+2+...+100 = 5050 row serializations instead of 100 — and the file is
   correct only by accident, because the last write happens to contain every row.

**Two rules with teeth:**

- *Keep the input basename.* The reference scripts pair a student file with its ground truth
  **by filename**. `dataset_docs_public.json` in must be `dataset_docs_public.json` out. A
  renamed file scores zero with no error message.
- *Scope `save_directory` per dataset folder.* `UnansweredQuestions/dataset_docs_public.json`
  and `AnsweredQuestions/dataset_docs_public.json` share a basename, so flat output means the
  second run silently overwrites the first. `data/output/search_results/UnansweredQuestions/...`
  keeps them apart.

---

# 5. The data models — `src/models.py`

All 8 models from subject VI.4, verified working.

```python
class MinimalSource(BaseModel):
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

**Why pydantic.** These structures cross stage boundaries and get written to disk, where the
grader reads them. pydantic validates on construction and serializes to exactly the declared
shape, so a missing field fails at the point of the mistake instead of silently producing an
unscorable file. Subject V.4 exempts service/orchestration classes — indexer, retriever,
pipeline — so those stay plain functions.

**Three details worth knowing:**

- `Field(default_factory=lambda: str(uuid.uuid4()))` — a plain default would freeze one uuid
  for the whole class; the factory runs per instance.
- The ground-truth files carry extra fields (`difficulty`, `is_valid`). pydantic ignores unknown
  fields by default, so `RagDataset` loads them fine.
- The union in `RagDataset` is **order-sensitive**: pydantic tries `AnsweredQuestion` first and
  falls back to `UnansweredQuestion`, which is what we want — the richer type wins when the data
  supports it.

**Verified:** the ground truth parses (100 questions, first row typed `AnsweredQuestion`), and
`StudentSearchResults(search_results=[], k=5).model_dump_json()` emits exactly
`{"search_results":[],"k":5}`.

**`model_validate_json` vs `model_validate`:** the first takes raw JSON **text**, the second
takes an already-parsed dict. Handing a dict to `model_validate_json` gives
`ValidationError: Invalid JSON: expected value at line 1 column 1`.

## 5.1 Two extra models for the ground truth

```python
class MoulinetteAnsweredQuestion(BaseModel):
    question_id: str
    question: str
    answer: str
    sources: List[MinimalSource]
    difficulty: str
    is_valid: bool

class MoulinetteDataset(BaseModel):
    rag_questions: List[MoulinetteAnsweredQuestion]
```

Mirror the `AnsweredQuestions/` files exactly, extra fields included, so `evaluate` gets typed
objects (`q.sources[0].file_path`) instead of dicts. `RagDataset` would also parse these files
(pydantic drops the unknown fields), but the explicit model states what the scorer expects and
would let `is_valid` filter questions if ever needed. Verified: docs 100 and code 99 rows
parse; every row has exactly one source and `is_valid: true`.

**Why the wrapper is needed.** `BaseModel` on the row class alone changes nothing about
`json.load` output — dicts stay dicts. Pydantic only builds objects when something is *parsed
through* a model; `MoulinetteDataset` is that entry point for the whole file.

---

# 6. Measurements

## 6.1 Score

| Metric | Measured | Required | Verdict |
|---|---|---|---|
| Indexing time, whole corpus | **7 s** | <= 5 min | pass |
| Retrieval, 100 questions | **< 0.1 s** | 200 q <= 90 s | pass |
| **docs recall@5** | **0.830** (83/100) | >= 0.80 | pass, margin 3 questions |
| **code recall@5** | **0.657** (65/99) | >= 0.50 | pass, margin 16 questions |
| Chunk ceiling (best possible) | docs 96/100, code 98/99 | — | chunking is not the limit |

Retrieval — the hard half of the grade — already clears both bars. Measured at
`max_chunk_size 2000`; remeasure after any change to chunking, the file filter or the tokenizer.

## 6.2 Experiment log (this is the README's Performance analysis)

| Change | docs R@5 | code R@5 | Conclusion |
|---|---|---|---|
| filter `.py/.md/.rst/.txt` (15 837 chunks) | 0.850 | 0.657 | best docs score so far |
| index every non-ignored file (18 738 chunks) | 0.830 | 0.657 | +2901 noise chunks cost 2 docs questions |
| `bm25s.tokenize` instead of ours | 0.830 | **0.525** | identifier splitting is worth 13 points on code |
| `max_chunk_size` ~62 chars (404 096 chunks) | **0.460** | **0.434** | both fail — the IoU floor, 37 docs hits rejected despite the right file |

Tokenizer overlap, average shared tokens between a question and its correct chunk:
`text.split()` -> docs 6.9 / code 3.1 · ours -> docs 8.9 / code 6.3.

## 6.3 Other checks run

- **Chunk coverage property test.** Slices rebuild each file exactly — no gaps, no overlaps, no
  oversize — on 156 stdlib files and on the full corpus.
- **Ceiling test.** Best achievable recall given these chunks: docs 96/100, code 98/99.
  Chunking is not the limiting factor; ranking is.
- **Ground-truth-driven file filter.** docs sources are `.md` (97) + `.txt` (3); code sources
  are `.py` (99). So `.py/.md/.rst/.txt` is the evidence-backed filter.
- **No silent file drops.** 1969 eligible files on disk, 1847 in the index, and all 122 absent
  are 0-byte `__init__.py`.
- **Live demo.** For a LoRA question, the ground-truth chunk ranked **#1** at score 13.07.

## 6.4 Verified end-to-end run

Full pipeline run from a clean index, both public datasets, `--max_chunk_size 2000 --k 5`:

```
index                 18 738 chunks · avg 1339 chars · max 2000 · 0 over budget · 2693 files
search_dataset docs   100 rows · 5 sources each · span avg 1701
search_dataset code    99 rows · 5 sources each · span avg 1514
```

| Dataset | R@1 | R@3 | **R@5** | Threshold | Margin |
|---|---|---|---|---|---|
| docs | 0.540 (54/100) | 0.760 (76/100) | **0.830** (83/100) | 0.80 | +3 questions |
| code | 0.354 (35/99) | 0.566 (56/99) | **0.657** (65/99) | 0.50 | +16 questions |

Every `question_id` in both output files matches its ground-truth twin, and both files carry the
input basename. The numbers reproduce the earlier measurement exactly, which means the pipeline
is deterministic across runs — the parallel-list invariant holds.

**The R@1 -> R@5 climb is the point of k.** Only 54% of docs questions put the right chunk
first, but 83% have it somewhere in the top 5. BM25 ranks by lexical overlap, which is a coarse
signal; retrieving 5 and letting the LLM read all of them is what converts a mediocre ranker
into a usable system.

## 6.5 `evaluate` verified against both datasets

Our own `evaluate` reproduces the hand-computed values exactly:

```
docs   Recall@1 0.540 · @3 0.760 · @5 0.830 · @10 0.830
code   Recall@1 0.354 · @3 0.566 · @5 0.657 · @10 0.657
```

`@10 == @5` because the output files hold 5 sources per row — not a bug, just the ceiling of
what is in the file. (Regenerating with `--k 10` makes @10 meaningful; see `task.md` 3.5.2.)

**Why the climb from @1 to @5 is the point of k.** Only 54% of docs questions put the right
chunk first, but 83% have it somewhere in the top 5. BM25 ranks by lexical overlap, a coarse
signal. Retrieving 5 and letting the LLM read all of them is what turns a mediocre ranker into
a usable system.

## 6.6 A deliberate decision, recorded

Indexing **every** non-ignored file — `.json`, `.cu`, `.cuh`, `.h`, `.cpp` included — rather
than filtering to `.py/.md/.rst/.txt` costs 2 docs questions (0.850 -> 0.830) and leaves a
3-question margin over the threshold. Kept on purpose: those files contain information worth
retrieving, and the subject leaves file selection to the student
(line 205: *"Read the files you judge useful from the vLLM repository"*). The cost is measured
and documented rather than unknown.

---

# 6.7 Typing and linting clean

`flake8 src` reports nothing and `mypy src` with the subject's flags reports
**`Success: no issues found in 10 source files`**. Twenty mypy errors went to zero.

**What the 20 errors actually were: two wrong annotations, not twenty bugs.**

| Wrong | Right | Errors it caused |
|---|---|---|
| `line_offsets: list[str]` in `chunk_nodes` | `list[int]` | 21, 33, 38, 41 (×3), 44, 61 |
| `chunk_nodes`/`chunk_pfile` `-> list[tuple[str, int, int]]` | `-> list[tuple[int, int]]` | 35, 47, 50, `index.py:77`, `index.py:79` |

`get_offsets` returns `list[int]`, so annotating the parameter `list[str]` made mypy treat every
character offset as a string — hence `str > int`, `str - str`, and wrong argument types all the
way down. And `chunk_nodes` returns `(start, end)` **pairs**; the file path is attached later in
`index_machine`, not in the chunker. mypy's error on line 61 was the giveaway: *"Argument 5 has
incompatible type `list[int]`; expected `list[str]`"* — the caller was right, the signature was
lying.

**Three lessons worth keeping for the defense:**

1. **mypy gives a local variable one type for the whole function.** `node` was bound by
   `for node in nodes` as `ast.stmt`, so rebinding the same name to `ast.stmt | None` in two
   later loops was a contradiction. Renaming them to `nd` fixed it. Three loops had simply
   shared a name.
2. **An empty list gets its type from the first `append`.** `starts = []` became
   `list[tuple[int, ast.stmt]]`, which then rejected the deliberate `(start, None)` sentinel.
   Declaring `starts: list[tuple[int, ast.stmt | None]] = []` states the intent.
3. **`ast.stmt` is the base class and has no `.body`.** Only `FunctionDef`, `ClassDef`, `If`,
   `For`, `While`, `Try`, `With` do. The runtime guard `getattr(node, 'body', None)` is correct,
   but mypy cannot narrow a type from a `getattr` *test*. Keeping the value —
   `bd = getattr(nd, 'body', None)` then `if bd:` and passing `bd` — type-checks because
   `getattr` with a default returns `Any`. No `cast`, no `# type: ignore`.

**And one about where an annotation belongs:** `tuple[list[MinimalSource], list[str]]` was first
written on `chunk_pfile`, which caused six fresh errors. That signature belongs to
`index_machine` — the function that actually builds `MinimalSource` objects. The test is simply:
*what does this function return?*

`Makefile` now lints `src` rather than `.`; bare `flake8 .` walks the whole vLLM corpus under
`data/raw/` and never finishes.

## 6.8 `evaluate` regression — fixed, numbers verified

`evaluate` had regressed to `ERROR414: 'dict' object has no attribute 'question_id'`. Fixed in
four steps, each run and checked:

| Symptom | Cause | Fix |
|---|---|---|
| `'dict' object has no attribute 'question_id'` | `json.load` returns dicts; annotating `list[MoulinetAnsweredQuestion]` converts nothing, and the class was not even a `BaseModel` | `MoulinetteAnsweredQuestion(BaseModel)` + `MoulinetteDataset` wrapper, file parsed through it (5.1) |
| every recall `0.0` | `src.file_path == truth.sources[0]` compared a `str` to a `MinimalSource` — never equal | compare `truth.sources[0].file_path` |
| `Student data is valid: False` on clean data | `len(oversized) > 0` — inverted | `len(oversized) == 0` |
| crash on `search_result` / undefined `s` | typo + wrong comprehension variable | `search_results`, `[r for r in ...]` — **mypy flagged both before running** |

Current output (labels still shifted by one leftover line, `task.md` 3.1 — the values are the
right ones):

```
docs   valid True · 100 questions · R@1 0.540 · R@3 0.760 · R@5 0.830 · R@10 0.830
code   valid True ·  99 questions · R@1 0.354 · R@3 0.566 · R@5 0.657 · R@10 0.657
```
Identical to the hand-computed values in 6.4 — the evaluator agrees with the reference.
`flake8 src` clean, `mypy src` clean.

**Lessons for the defense:**

1. **A green mypy is not a correct program.** `json.load` returns `Any`, and `Any` satisfies
   every annotation — mypy stayed silent on the dict bug. Parsing through pydantic turns `Any`
   into real types, and then mypy *can* catch things: it found the `search_result` typo and the
   undefined `s` immediately.
2. **Annotations do not convert.** `x: list[Model] = json_data` is a promise to the reader, not
   a conversion. Only `Model.model_validate[_json](...)` builds objects.
3. **A score of exactly 0.0 is a comparison bug, not a retrieval bug.** Retrieval cannot get
   *every* question wrong; a type mismatch in the hit test can.
4. **Check the known values.** Having 0.540 / 0.830 and 0.354 / 0.657 as targets is what
   exposed both the 0.0 and the shifted labels in seconds.

---

# 7. Bugs already fixed — the defense material

Each of these was found by running or measuring, not by reading. "What went wrong?" is a
standard defense question.

**Silent data corruption — the worst one.**
`chunk_texts.append(ft_open(full_path[start:end]))` sliced the *path string* and opened the
result as a filename. The resulting `OSError` was swallowed by a broad `except`, so the chunk
metadata list and the text list drifted out of alignment — output `5 4` instead of `5 5`. No
crash, no message, just wrong data. Fixed by reading the file once (`src = ft_open(full_path)`)
and slicing the **text**. Lesson: a broad `except ... : continue` can turn a bug into corruption.

**Infinite loop in `hard_split` when `max_size <= 0`.** `chunk_start += max_size` moves
backwards, so `while chunk_start < e` never ends and the list grows until the OOM killer fires.
Confirmed by exit code 124 under `timeout`. Fixed with a `ValueError` guard in the function
itself, not only at the CLI, because both chunkers call it.

**Tokenizer emitted every plain word twice** — guard on `len(item) > 1` (characters) where
`len(parts) > 1` (pieces) was meant. Doubled term frequency, distorted every score.

**1847 tqdm bars** — the bar was created inside the per-file loop.

**Tiny-chunk catastrophe** — an index built at ~62 characters per chunk scored docs 0.460 /
code 0.434. 37 docs questions retrieved the **correct file** and were still rejected because
`IoU = 62/1400 = 0.044 < 0.05`. This is the clearest evidence for why the IoU floor dictates
chunk size.

**`class Indexer(MinimalSource)`** — inheritance where composition was meant. An indexer *has*
sources; it is not one.

**`search` printed a literal f-string** — only the first fragment carried the `f` prefix, so the
output read `path [{c['first_character_index']}:...]`.

**`search_dataset` nested inside `search`** — indented into the function body after a `raise`,
so it was unreachable and invisible to Fire.

**The whole write block inside the `for` loop** — 100 rewrites, 100 prints, quadratic work, file
correct only by accident.

**`dataset_path` turned into a directory with the filename hardcoded** — made
`dataset_code_public.json` unreachable, and `os.path.basename` then produced an output file
called `UnansweredQuestions` with no `.json`, which the grader cannot pair with anything.

**Smaller ones, same lesson each time — run it, do not assume:**

| Bug | Cause |
|---|---|
| `ModuleNotFoundError: No module named 'python_file_chunker'` | absolute imports inside a package; needed `src/__init__.py` + relative imports |
| `git_file()` returned `[]` | `tmp.strip().startswith('#')` tested the whole file instead of the current line |
| `SyntaxError: multiple exception types must be parenthesized` | `except A, B:` is 3.14 syntax; we are on 3.13 |
| `TypeError: expected str, not list` in `is_ignored` | `item.split('/')` where `item.strip('/')` was meant |
| `FileNotFoundError: 'utils.py'` | passed `file` instead of `os.path.join(path, file)` |
| `os.mkdir(..., exist_ok=True)` / `os.mkdirs` | the function is `os.makedirs` |
| `PermissionError: '/data/processed'` | a leading `/` means the filesystem root, not the project |
| wrong tuple unpack `for a, b, f in meta` | meta is `(file_path, start, end)` |
| `chunk[i]` instead of `chunks[i]` | NameError on every query |
| `from models import RagDataset` | absolute import took the whole CLI down |
| `import bm25` | `bm25` is a shim package; the real library is `bm25s` |

---

# 8. What exists on disk today

| Path | State |
|---|---|
| `src/` runnable as `python -m src` | works |
| `src/utils.py` | `ft_open`, `get_offsets`, `hard_split` — logic verified |
| `src/python_file_chunker.py` | AST chunker — verified exact |
| `src/txt_file_chunker.py` | line-based `hard_split` wrapper |
| `src/index.py` | walk + gitignore filter + chunk + tokenize + BM25 save |
| `src/search.py` | `search` and `search_dataset` |
| `src/models.py` | 8/8 subject models + `MoulinetteAnsweredQuestion`, `MoulinetteDataset` |
| `src/__main__.py` | Fire with `index`, `search`, `search_dataset`, `evaluate`; `except Exception` catch-all active |
| `src/evaluate.py` | `iou`, `recalling`, `evaluate` — correct numbers + validity check; labels off by one line (`task.md` 3.1) |
| `src/rag_flow.py` | 0 bytes — planned `Generator` class (`task.md` 5.1) |
| `explaination.md` | how answer generation works, step by step, with reading links |
| `Makefile` | `install run debug clean lint lint-strict` |
| `pyproject.toml` | `bm25s`, `fire`, `pudb`, `pydantic`, `tqdm` |
| `data/raw/vllm-0.10.1/` | corpus |
| `data/datasets/{Unanswered,Answered}Questions/` | 2 files each: docs + code |
| `.gitignore` | `/data/*` active — nothing under `data/` is tracked |

---

# 9. Command reference

All commands run from the repo root. Every path is a CLI argument with a default; nothing is
hardcoded.

## `index`
```
uv run python -m src index --max_chunk_size 2000 --files data/raw --save_dir data/processed
```
**In:** every non-ignored file under `--files`, plus `.gitignore` patterns.
**Out:** `<save_dir>/chunks.json` + the 5 bm25s files.
**Stdout:** two tqdm bars, then `Ingestion complete! Indexed <n> chunks under <save_dir>`.

`chunks.json` is a flat list where element `i` **is** chunk `i`:
```json
[{"file_path": "data/raw/vllm-0.10.1/setup.py",
  "first_character_index": 0, "last_character_index": 1894}, ...]
```
`file_path` exactly as walked from the repo root — compared verbatim by the grader.
`last - first <= max_chunk_size`, always.

## `search`
```
uv run python -m src search "<query>" --k 10 --save_directory data/processed
```
**Out:** nothing on disk. `k` lines on stdout, best first.
**Edges:** `k <= 0` -> message · empty query -> message · `k > len(chunks)` -> clamped ·
missing index -> `index not found, run index first` · junk query -> still returns top-k, which
is correct behaviour for BM25.

## `search_dataset`
```
uv run python -m src search_dataset \
  --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json \
  --k 5 \
  --save_directory data/output/search_results/UnansweredQuestions \
  --save_processed data/processed
```
**In:** `{"rag_questions": [{"question_id": "...", "question": "..."}, ...]}` — 100 docs,
99 code. **Out:** `<save_directory>/<input basename>` as `StudentSearchResults`.
Ranked best first; the same `file_path` may repeat with different ranges — one entry per chunk.
**Budget:** 200 questions <= 90 s.

## `evaluate` (works — labels fix pending, `task.md` 3.1)
```
uv run python -m src evaluate --student_search_results_path <your output> \
                              --dataset_path <AnsweredQuestions file>
```
Ground truth adds `sources`, `answer`, `difficulty`, `is_valid`:
```json
{"question_id": "...", "question": "...", "answer": "The /v1/load_lora_adapter endpoint ...",
 "sources": [{"file_path": "data/raw/vllm-0.10.1/docs/features/lora.md",
              "first_character_index": 4695, "last_character_index": 6098}],
 "difficulty": "synthetic", "is_valid": true}
```
**Out:** stdout `Student data is valid: <bool>`, question counts, then `Recall@1 / @3 / @5 /
@10`. Hit = same file **and** IoU >= 0.05, matched by `question_id` — never by list position.
Valid = no retrieved source longer than `--max_context_length` (2000), as the moulinette checks.

## `answer` / `answer_dataset` (to be written)
```
uv run python -m src answer "<query>" --k 10
uv run python -m src answer_dataset --student_search_results_path <out> --save_directory <dir>
```
**In:** the `StudentSearchResults` file; source text fetched from the corpus by path + range.
**Out:** `StudentSearchResultsAndAnswer` — the same rows plus `"answer"`.

## The moulinette (official scorer, never imported from our code)
```
./moulinette evaluate_student_search_results \
  data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  data/datasets/AnsweredQuestions/dataset_docs_public.json \
  --k 10 --max_context_length 2000
```
Look for `Student data is valid: True` before trusting any number.

---

# 10. Defense checklist — be able to explain

- Why chunks carry character offsets rather than text, and how `get_offsets` converts AST line
  numbers into them.
- Why the gaps between AST nodes are preserved — docstrings, imports and comments are
  retrievable content.
- Why the tokenizer keeps the whole identifier **and** its parts: exact quotes match the whole,
  paraphrases match the parts — 13 recall points on code as evidence.
- Why `[A-Z]+(?=[A-Z][a-z])` and not `[A-Z]+(?=[a-z])`: `HTTPServer` -> `HTTP` + `Server`
  instead of `HTTPS` + `erver`.
- Why BM25 needs no stopword list: IDF already drives common tokens to near-zero weight.
- Why the parallel-list invariant matters, and how a mismatch fails **silently**.
- Why tiny chunks destroy recall despite being more precise — the IoU 0.05 floor, measured.
- Why `folder[:] = [...]` prunes the walk but `folder = [...]` does not.
- Why indexing every non-ignored file was kept even though it costs 2 docs questions.
- Why batching `retrieve` once beats 100 calls.
- Why a green mypy did not catch the dict bug in `evaluate` (`json.load` → `Any`), and why
  parsing through pydantic made mypy useful again.
- The LLM side — see `explaination.md` §7.
