# task.md — what is left to do

Remaining work only, for every part of the project. How the system works and what is already
done live in `completed.md`. Shell tests per part live in `checker.md`.

Legend: `[ ]` not started · `[~]` partial · **BLOCKER** = nothing after it can be measured.

---

# Status in one line

Retrieval passes both thresholds (docs R@5 **0.830** / need 0.80, code **0.657** / need 0.50).
`index`, `search`, `search_dataset` and the 8 models are done. Missing: `evaluate`, the
moulinette check, answer generation, a real Markdown strategy, lint/typing, README.

---

# 0. Do this first — BLOCKER

**0.1 Re-index. The index on disk is stale.**
`data/processed/` currently holds **404 096 chunks, average 62 characters, max 88** — the bad
run that scores docs 0.460 / code 0.434, i.e. **both thresholds failed**. Every number measured
against it is meaningless.
```sh
uv run python -m src index --max_chunk_size 2000
```
Expect ~18 700 chunks, ~7 s. Then regenerate both search outputs:
```sh
uv run python -m src search_dataset \
  --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json --k 5 \
  --save_directory data/output/search_results/UnansweredQuestions --save_processed data/processed
uv run python -m src search_dataset \
  --dataset_path data/datasets/UnansweredQuestions/dataset_code_public.json --k 5 \
  --save_directory data/output/search_results/UnansweredQuestions --save_processed data/processed
```
**Accept when:** both files exist, named `dataset_docs_public.json` and
`dataset_code_public.json`, with `search_results` length 100 and 99, every `retrieved_sources`
holding exactly 5 entries, and **one** `Saved ...` line printed per run.

**0.2 Uncomment the catch-all in `__main__.py:14-15`.**
```python
    except Exception as e:
        print(f"ERROR414: {e}")
```
It is commented out right now, so every bug prints a full traceback. The subject requires the
program never to crash on bad input. `except KeyboardInterrupt` stays as its own clause —
`KeyboardInterrupt` derives from `BaseException`, not `Exception`, so it is not covered by the
catch-all.

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

# 3. `evaluate` — not started, build it next

**In:** `--student_search_results_path`, `--dataset_path` (the `AnsweredQuestions` twin).
**Out:** stdout only — `Recall@1 / @3 / @5 / @10`.

**Algorithm:** index the ground truth by `question_id` into a dict, then match **by id, never by
list position**. For each of your rows, take the first `k` sources in rank order and count a hit
when `file_path` matches **and** IoU >= 0.05. Hits divided by question count.
```python
def iou(a, b, c, d):
    inter = max(0, min(b, d) - max(a, c))
    union = max(b, d) - min(a, c)
    return inter / union if union else 0.0
```
**Why it is the next thing to build:** it is the feedback loop. Without it, every later change
to chunk size, the file filter or the tokenizer is a guess. The moulinette is the official
scorer but too slow and too coarse to iterate against.
**Accept when:** it reproduces docs ~0.83 / code ~0.66 at `max_chunk_size 2000`.
**Then register it** in `__main__.py`.

---

# 4. Validate against the moulinette — not started

The executable is **not in the repo** — get it from the subject attachments, rename
`moulinette-ubuntu` / `moulinette-fedora` to `moulinette`, `chmod +x`.
```sh
./moulinette evaluate_student_search_results \
  data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  data/datasets/AnsweredQuestions/dataset_docs_public.json \
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
data/processed/                           index output                           [x] stale
data/datasets/{Unanswered,Answered}Questions/                                    [x]
data/output/search_results/<Scope>/       from search_dataset                    [ ]
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

1. **0.1** re-index at 2000 and regenerate both search outputs. *Nothing can be measured before
   this.*
2. **0.2** uncomment the catch-all. *One line.*
3. **3** `evaluate`. *The feedback loop — everything after this becomes measurable instead of
   guessed.*
4. **4** moulinette, until `Student data is valid: True`. *Catches format errors our own
   evaluator cannot see, e.g. a renamed output file.*
5. **5** answer generation. *Biggest remaining piece, and it depends on the output format from
   step 1.*
6. **1.1** Markdown chunker, then re-run `evaluate` on docs. *Keep it only if the number goes
   up.*
7. **6** dead code, type hints, lint clean.
8. **7, 8** Makefile fixes and the README's 10 sections.
9. **9** tests.
10. **11** bonus.
