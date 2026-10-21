# task.md — what is left to do
Next task: evaluate — the command that does what I just ran by hand, so the feedback loop is yours.

- In: --student_search_results_path, --dataset_path (the AnsweredQuestions twin)
- Out: stdout only — Recall@1 / @3 / @5 / @10
- Load ground truth into a dict keyed by question_id, match by id, never list position
- Hit = file_path equal and IoU ≥ 0.05 over the character ranges
- Register it in __main__.py alongside the catch-all fix

def iou(a, b, c, d):
    inter = max(0, min(b, d) - max(a, c))
    union = max(b, d) - min(a, c)
    return inter / union if union else 0.0

Target: it must print 0.540 / 0.760 / 0.830 for docs and 0.354 / 0.566 / 0.657 for code. Those are the known-correct values, so they're your test.

Remaining work only, for every part of the project. How the system works and what is already
done live in `completed.md`. Shell tests per part live in `checker.md`.

Legend: `[ ]` not started · `[~]` partial · **BLOCKER** = nothing after it can be measured.

---

# Status in one line

Retrieval **verified end to end** on both public datasets: docs R@5 **0.830** (need 0.80),
code R@5 **0.657** (need 0.50). `index`, `search`, `search_dataset` and the 8 models are done.
`evaluate` works too, reproducing both scores exactly. Missing: the moulinette check, answer
generation, a real Markdown strategy, lint/typing, README.

---

# 0. Done — see `completed.md` section 6.5

The re-index and both search runs are finished and verified: docs R@5 **0.830**, code R@5
**0.657**, both above threshold. One item from that step is still open:

**0.1 `[ ]` Uncomment the catch-all in `__main__.py:14-15`.**
```python
    except Exception as e:
        print(f"ERROR414: {e}")
```
Still commented, so every bug prints a full traceback. The subject requires the program never
to crash on bad input. `except KeyboardInterrupt` stays as its own clause — it derives from
`BaseException`, not `Exception`, so the catch-all does not cover it.

---

# 1. Indexing — what remains

**1.1 `[ ]` A real Markdown strategy.** `txt_file_chunker.chunk_txt_file` is a 4-line wrapper
around `hard_split`, so today both code paths end in the same line-splitter — one strategy
wearing two hats. The subject names exactly two distinct strategies (line 207).

Approach: heading offsets with `re.finditer(r'^#{1,6} .*$', text, re.M)`, each
heading-to-next-heading span as a unit, merge consecutive small units up to `max_chunk_size`,
`hard_split` any single oversized section. Same merge logic as `chunk_nodes`, headings in place
of AST nodes.
**Watch out:** never split inside a fenced code block — a ``` fence opening in one chunk and
closing in another gives the LLM unusable context.
**Accept when:** `evaluate` shows docs R@5 >= 0.830. If it drops, keep the simple version and
say so in the README — a measured negative result is a legitimate finding.

**1.2 `[ ]` Blank lines slip through `git_file()`.** An empty line in `.gitignore` becomes the
pattern `''`. Harmless today, but filter it out.

**1.3 `[ ]` `except (FileNotFoundError)` in `git_file()` should be `except OSError` — a
missing file is not the only way reading `.gitignore` can fail.

**1.4 `[ ]` `sorted()` on files and folders in `index_machine`.** Not needed now (index and
`chunks.json` are written in the same walk), but it is a prerequisite for the incremental
indexing bonus.

---

# 2. Retrieval — what remains

**2.1 `[ ]` Type hints on `save_processed` and `saved_file`** in `search_dataset`. Both are
untyped in an otherwise annotated signature; mypy runs with `--disallow-untyped-defs`.

**2.2 `[ ]` Decide the empty-query case explicitly in `search_dataset`.** The tokenizer drops
1-character tokens, so a question like `"a b ?"` tokenizes to `[]`. Behaviour must be an empty
`retrieved_sources`, not a crash from `bm25s`.

**2.3 `[ ]` Wrap the dataset parse in `try/except ValidationError`** for a clean message on a
malformed dataset file instead of a pydantic traceback.

---

# 3. `evaluate` — WORKS, see `completed.md` section 6.6

Verified against both datasets, reproducing the known-correct values exactly:

```
docs   Recall@1 0.540 · @3 0.760 · @5 0.830
code   Recall@1 0.354 · @3 0.566 · @5 0.657
```

Polish still open, listed in section 3.5 below.

---

# 3.5 Fix all of this BEFORE running the moulinette

Nothing here changes a score. All of it changes whether the moulinette accepts the output and
whether `make lint` passes. Cheaper to fix now than after the answer stage is written.

## 3.5.1 Dataset paths moved — two defaults are now dead

The datasets are at **`data/datasets_public/public/`**, not `data/datasets/`:
```
data/datasets_public/public/AnsweredQuestions/dataset_{docs,code}_public.json
data/datasets_public/public/UnansweredQuestions/dataset_{docs,code}_public.json
```
`evaluate` already points at the new location. **`search_dataset` does not** — its
`dataset_path` default is still `data/datasets/UnansweredQuestions/dataset_docs_public.json`,
which no longer exists, so the next run fails with `FileNotFoundError`. Fix the default.

## 3.5.2 Regenerate both outputs with `--k 10`

Subject line 507 uses `--k 10` in its own `search_dataset` example, and line 553 says the
moulinette *"reports recall at several values of k"* — it reports from **your file**, it does
not retrieve anything itself. Your files hold 5 sources per row, so the moulinette's @10 is
capped at your @5 and you would be reporting a @10 that is not real.

Costs nothing: BM25 ranking is deterministic, so the top 5 of a top-10 run is identical to a
top-5 run. The thresholds are **@5** (docs 0.80, code 0.50) and they do not move.

**Do:** change `search_dataset`'s default `k` to 10, regenerate both files, re-run `evaluate`.
R@5 must still read 0.830 and 0.657 — if it moves, something else broke.

## 3.5.3 `max_context_length` — use it as the validity check

It is **not** a retrieval parameter. Subject line 222: *"the moulinette rejects any retrieved
source longer than 2000 characters (its max_context_length), and a single over-long source
makes your whole output invalid."* Currently unused in `evaluate`. Make it mirror the
moulinette so you catch the fatal case before handing the file over:
```python
oversized = [s for r in questions.search_results
             for s in r.retrieved_sources
             if s.last_character_index - s.first_character_index > max_context_length]
print(f"Student data is valid: {not oversized}")
```
Measured state: max span exactly 2000, **0 chunks over budget**, so this must print `True`.

## 3.5.4 mypy — 20 errors from 2 wrong annotations

`src/python_file_chunker.py` is fine; its annotations are not. Two lies cascade:

| Line | Wrong | Right | Fixes |
|---|---|---|---|
| 10 | `line_offsets: list[str]` | `list[int]` | 21, 33, 38, 41, 44 |
| 12, 54 | `-> list[tuple[str, int, int]]` | `-> list[tuple[int, int]]` | 35, 41, 47, 50, `index.py:77`, `index.py:79` |

`get_offsets` returns `list[int]`, so annotating it `list[str]` makes mypy treat every offset as
a string — hence `str > int`, `str - str`, and wrong argument types everywhere. And
`chunk_nodes` returns `(start, end)` **pairs**; the file path is attached later in
`index_machine`, not here.

**Then declare the containers**, because mypy locks in the type of the first `append`:
```python
starts: list[tuple[int, ast.stmt | None]] = []     # fixes lines 22, 23 (the None sentinel)
pairs: list[tuple[int, int, ast.stmt | None]] = []
cuts: list[tuple[int, int]] = []
curr: tuple[int, int] | None = None
```

**`node.body` (line 38), `"stmt" has no attribute "body"`** — real, not a mistake. `ast.stmt`
is the base class; only `FunctionDef`, `ClassDef`, `If` and friends have `.body`. mypy cannot
narrow from a `getattr` test, so keep the value instead of testing and re-reading it:
```python
body = getattr(node, 'body', None)
if body:
    cuts.extend(chunk_nodes(body, s, e, src_file, line_offsets, max_size))
```
`getattr` with a default returns `Any`, so it type-checks with no `cast` and no
`# type: ignore`. The `node is not None` test becomes redundant — `None` has no `.body`.

**`src/index.py:91` and `:126`** — `index_machine` returns `MinimalSource` objects, not tuples:
```python
) -> tuple[list[MinimalSource], list[str]]:
```
`:126` (`item.model_dump()`) only errored because mypy believed the list held plain tuples.

**`src/txt_file_chunker.py:4`** — no signature at all:
```python
def chunk_txt_file(filename: str, max_size: int) -> list[tuple[int, int]]:
```

**`src/evaluate.py` — `"UnansweredQuestion" has no attribute "sources"`** is mypy catching
something true: `RagDataset.rag_questions` is `List[AnsweredQuestion | UnansweredQuestion]` and
only the answered variant has `sources`. Filter while building the lookup:
```python
gt = {q.question_id: q for q in g_checker.rag_questions
      if isinstance(q, AnsweredQuestion)}
```
Correct behaviour too — a ground-truth row with no `sources` cannot be scored.

**Still missing annotations:** `iou`'s four params and return · `recalling`'s return ·
`evaluate`'s return (`-> None`) · `search_dataset`'s `save_processed` and `saved_file` ·
`index.py:30` `skip_file` and `:36` `skip_folder` (both being deleted anyway, see 6.1).

## 3.5.5 flake8 — 7 findings in our own code

```
src/__init__.py:1:1   W391 blank line at end of file
src/evaluate.py:4:1   F401 'tqdm.tqdm' imported but unused
src/evaluate.py:48:80 E501 line too long (89 > 79)
src/evaluate.py:59:1  W391 blank line at end of file
src/search.py:15:1    F401 '.utils.ft_open' imported but unused
src/search.py:31:80   E501 line too long (84 > 79)
src/search.py:51:80   E501 line too long (99 > 79)
```
`tqdm` in `evaluate.py` — either wrap the loop in it or drop the import. `ft_open` in
`search.py` is unused because `search_dataset` reads with `open(...).read()`; use `ft_open`
there instead and the import earns its place.

## 3.5.6 flake8 has no exclude — `make lint` is unusable

`flake8 .` walks **`data/raw/vllm-0.10.1/`** — the entire vLLM source tree. It ran past 120
seconds and had to be killed. There is no `.flake8`, `setup.cfg` or `tox.ini` in the repo, so
the linter has no idea what to skip.

Add a `.flake8` (or `[flake8]` in `setup.cfg`):
```ini
[flake8]
exclude = .git,__pycache__,.venv,data,build,dist
max-line-length = 79
```
Without it `make lint` never finishes, which is a problem the moulinette may well hit.

## 3.5.7 `evaluate` cosmetics

- `racll@` typo in the print — should read `Recall@`.
- The `Evaluation Results ===...` header prints **after** the numbers; move it above the loop.
- `except (OSError, PermissionError, FileNotFoundError)` — the last two are subclasses of
  `OSError`, so just `OSError`. It prints the error and then **falls through** to the header;
  `raise ValueError(...)` or `return`.
- Line 48 rebuilds the model with the CLI `k`, overwriting the file's own `k`. Use
  `StudentSearchResults.model_validate_json(f.read())`.
- The `gt` dict is rebuilt on all 4 calls to `recalling` — build it once in `evaluate` and pass
  it in.

## 3.5.8 Still open from step 0

**`__main__.py:14-15`** — the `except Exception` catch-all is still commented out, so every bug
prints a full traceback. Subject line 464: the CLI *"must never crash with an unhandled
traceback"*, and it is tested with edge cases.

---

# 4. Validate against the moulinette — not started

**Do section 3.5 first.** The executable is **not in the repo** — get it from the subject
attachments, rename `moulinette-ubuntu` / `moulinette-fedora` to `moulinette`, `chmod +x`.
```sh
./moulinette evaluate_student_search_results \
  data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  data/datasets_public/public/AnsweredQuestions/dataset_docs_public.json \
  --k 10 --max_context_length 2000
```
**Look for `Student data is valid: True` before trusting any number.** Do this **before**
starting on Qwen: a format mistake invalidates every output file, and one chunk wider than 2000
characters invalidates the whole run. Never import or call the moulinette from our code.

---

# 5. Answer generation — not started, biggest remaining piece

Budget real time: the Qwen3-0.6B weights are a large download and CPU generation is slow.
Needs `transformers` and `torch` added to `pyproject.toml`.

**5.1 `[ ]` `answer "<query>" --k`** — retrieve, read each source's text back from its file and
range, build the prompt, generate, print.

**5.2 `[ ]` `answer_dataset --student_search_results_path --save_directory`** — read the
`StudentSearchResults` file from `search_dataset`, **not** the corpus index; fetch each source's
text; prompt per question under a tqdm bar; write `StudentSearchResultsAndAnswer` with an
`answer` on every row. Print `Loaded <n> questions` and
`Saved student_search_results_and_answer to <path>`.

**5.3 Prompt shape:** a system instruction to answer **only** from the provided sources and to
say so when they do not contain the answer; then the numbered sources; then the question.

**5.4 Context budget:** count tokens with the model's tokenizer and **drop the lowest-ranked
sources until it fits**, rather than truncating mid-source — half a function is worse than no
function.

**Accept when:** answers are coherent, grounded in the retrieved sources, and on point. The
subject relaxes this bar because of the model's size; retrieval and prompt strategy carry the
weight.

**5.5 `[ ]` Register `answer` and `answer_dataset`** in `__main__.py`.

---

# 6. Code quality — what remains

**6.1 `[ ]` Dead code to delete.**

| File | Dead |
|---|---|
| `src/index.py` | `skip_file`, `skip_folder` (both superseded by the pattern-based `is_ignored`), `space`, the commented `bm25s.tokenize` line |
| `src/python_file_chunker.py` | the trailing commented block |
| `src/rag_flow.py` | **empty file** — delete it or use it |
| `main.py` | `print("Hello from rag!")` — the `uv init` leftover; the entry point is `python -m src` |

flake8 flags unused names, and the defense will ask what each one is for.

**6.2 `[ ]` Type hints on every function.** `utils.py` and both chunkers have none. mypy runs
with `--disallow-untyped-defs`.

**6.3 `[ ]` PEP 257 docstrings, and fix the typos** in the existing ones: `igonore`, `waht`,
`breakk`, `probleme`, `opend`.

**6.4 `[ ]` flake8 + mypy clean** — `make lint` must pass:
```
flake8 .
mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports \
        --disallow-untyped-defs --check-untyped-defs
```

**6.5 `[ ]` Re-check every command's edge cases.** None may traceback: empty query, nonsensical
query, `k=0`, negative `k`, missing file, malformed JSON, missing index.

---

# 7. Makefile — nearly done

Exists with all 6 rules. Two fixes:

**7.1 `[ ]` `run` has no `--max_chunk_size`** — it runs `uv run python -m src index` and relies
on the default. Make it explicit: `--max_chunk_size 2000`.

**7.2 `[ ]` Trailing whitespace** after `index ` in the `run` rule.

**7.3 `[x]` `clean` does not touch `data/`** — correct, keep it that way.

---

# 8. README — empty file, 0 bytes

**First line, italic, exactly:**
```
*This project has been created as part of the 42 curriculum by <login>.*
```

**All 10 sections required (chapter VIII), English only:** Description · Instructions ·
Resources **and how AI was used, per task** · System architecture · Chunking strategy ·
Retrieval method · Performance analysis · Design decisions · Challenges faced · Example usage.

**Material already written, lift it from `completed.md`:**

| Section | Source in `completed.md` |
|---|---|
| Performance analysis | the two tables in 6.1 and 6.2 |
| Chunking strategy | 3.3 and 3.4 |
| Retrieval method | 3.5, 3.6 and 4 |
| Design decisions | 6.4 (index everything) and 6.2 (own tokenizer over `bm25s.tokenize`), both with numbers |
| Challenges faced | 7 — the IoU floor, the parallel-list invariant, the silent corruption |
| System architecture | the data flow diagram in 2 |

---

# 9. Tests — asked for, not graded

`[ ]` pytest over: chunk slices reconstruct a file exactly · no chunk exceeds the limit ·
`tokenizer('getHTTPResponseCode')` splits as expected · `hard_split` rejects `max_size <= 0` ·
each chunker handles an empty file, a one-line file, and a file with no trailing newline.

---

# 10. Layout and git

```
src/                                      runnable as python -m src              [x]
pyproject.toml, uv.lock                   at root                                [x]
README.md                                 at root                                [~] empty
Makefile                                  install run debug clean lint           [x]
data/raw/vllm-0.10.1/                     corpus                                 [x]
data/processed/                           index output, 18 738 chunks            [x]
data/datasets/{Unanswered,Answered}Questions/                                    [x]
data/output/search_results/<Scope>/       both datasets, verified                [x]
data/output/search_results_and_answer/<Scope>/                                   [ ]
```
`.gitignore` has `/data/*` active and `git ls-files data` returns nothing — **nothing under
`data/` is tracked, which is correct.** Keep it that way: once a 100 MB blob is in history it
stays there, and a later `git rm` does not shrink the repo. Verify with
`git status --short` before any `git add`.

`[ ]` Add `transformers` and `torch` when starting part 5.

---

# 11. Bonus — only after the mandatory part fully validates

- `[ ]` semantic embeddings (all-MiniLM-L6-v2) beside the lexical index
- `[ ]` hybrid retrieval, fusing the two rankings
- `[ ]` incremental indexing — needs 1.4 (`sorted()`) first
- `[ ]` caching: cold start and repeated queries
- `[ ]` local HTTP API

---

# Order of work

1. **3.5** the whole pre-moulinette list: dead dataset paths, `--k 10` regeneration,
   `max_context_length` as the validity check, 20 mypy errors from 2 wrong annotations, 7 flake8
   findings, the missing flake8 exclude, the catch-all. *All of it is cheap now and blocks or
   distorts the moulinette run.* *The feedback loop — everything after this becomes measurable instead of
   guessed.*
2. **4** moulinette, until `Student data is valid: True`. *Catches format errors our own
   evaluator cannot see, e.g. a renamed output file.*
3. **5** answer generation. *Biggest remaining piece, and it depends on the output format from
   step 1.*
4. **1.1** Markdown chunker, then re-run `evaluate` on docs. *Keep it only if the number goes
   up.*
5. **6** dead code, remaining type hints, lint clean.
6. **7, 8** Makefile fixes and the README's 10 sections.
7. **9** tests.
8. **11** bonus.
