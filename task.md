# task.md — what is left to do

**Next task:** finish `evaluate` — **one line** left (section 3), then the pre-moulinette list
(3.5), the moulinette (4), then answer generation (5, explained in `explaination.md`).

Remaining work only, for every part of the project. How the system works and what is already
done live in `completed.md`. Shell tests per part live in `checker.md`. How the LLM part works,
with links to read more, lives in `explaination.md`.

Legend: `[ ]` not started · `[~]` partial · **BLOCKER** = nothing after it can be measured.

---

# Status in one line

Retrieval **verified end to end**: docs R@5 **0.830** (need 0.80), code R@5 **0.657** (need
0.50). `index`, `search`, `search_dataset`, the models, and a clean `flake8 src` + `mypy src`
are done. **`evaluate` runs again and computes the right numbers, but prints them under the
wrong labels** — section 3, one line. Then: 3.5 list, moulinette, answer generation, Markdown
strategy, dead code, README.

---

# 0. Done — see `completed.md` section 6.5

**0.1 `[x]` Catch-all active in `__main__.py`.** `except Exception` prints `ERROR414: ...`,
`except KeyboardInterrupt` stays its own clause (it derives from `BaseException`).

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

**2.1 `[x]` Type hints** on `save_processed` and `saved_file` — done.

**2.2 `[ ]` Empty-query case in `search_dataset`.** The tokenizer drops 1-character tokens, so
`"a b ?"` tokenizes to `[]`. Behaviour must be an empty `retrieved_sources`, not a crash from
`bm25s`. Subject line 464 tests degenerate inputs.

**2.3 `[ ]` Wrap the dataset parse in `try/except ValidationError`** for a clean message on a
malformed dataset instead of a pydantic traceback.

**2.4 `[ ]` Use `ft_open`** in `search_dataset` instead of `open(...).read()` — it is imported
in `search.py` for exactly this.

---

# 3. `evaluate` — `[~]` one line left

The regression is fixed (see `completed.md` 6.8): ground truth parses into `MoulinetteDataset`,
the file-path comparison is correct, the validity check is in. Current output, both datasets:

```
docs   racll@3: 0.54   racll@5: 0.76   racll@10: 0.83   racll@15: 0.83
code   racll@3: 0.354  racll@5: 0.566  racll@10: 0.657  racll@15: 0.657
```
**The numbers are the right ones — under the wrong labels.** 0.54 is @1, not @3.

## 3.1 `[ ]` Delete the leftover increment — `evaluate.py:78`

```python
        for kk in (1, 3, 5, 10):
            out = recalling(questions, g_checker, kk)
            kk += 2 if kk < 5 else 5          # <- leftover from the old counter loop
            print(f"racll@{kk}: {out}")
```
The `for` already gives the right `kk`; this line bumps it after computing and before printing.
Delete it. **Accept when** the output reads exactly:
```
docs   Recall@1 0.540 · @3 0.760 · @5 0.830
code   Recall@1 0.354 · @3 0.566 · @5 0.657
```

## 3.2 `[ ]` Leftovers in the same function (no score change)

- `racll` → `Recall`, and format `{out:.3f}` (code prints `0.35353535…` today).
- `next(...)` in `recalling` scans all ~100 ground-truth rows per question. A dict
  `{q.question_id: q for q in g_checker.rag_questions}` built once in `evaluate` is O(1) per
  lookup and simpler — pass the dict to `recalling`.
- `json.load` + `MoulinetteDataset(rag_questions=...)` works; `MoulinetteDataset.model_validate_json(f.read())`
  does the same in one step (same for `StudentSearchResults`, which also keeps the file's own `k`).
- `except (OSError, PermissionError, FileNotFoundError)` → `except OSError` (the other two are
  subclasses). Add `ValidationError` for a malformed file.
- Header `"Evaluation Results \n ===="` has a stray space at the start of the second line.

---

# 3.5 Fix all of this BEFORE running the moulinette

Nothing here changes a score. All of it changes whether the moulinette accepts the output.

## 3.5.1 `search_dataset` default path has the wrong case

```python
    'data/datasets_public/Public/UnansweredQuestions/dataset_docs_public.json',
```
The directory is **`public`**, lowercase. Linux filesystems are case-sensitive, so this is a
`FileNotFoundError` on the next run. `evaluate` has it right; `search_dataset` does not.

## 3.5.2 Regenerate both outputs with `--k 10`

`search_dataset` still defaults to `k: int = 5`. Subject line 507 uses `--k 10` in its own
example, and line 553 says the moulinette *"reports recall at several values of k"* — it reports
from **your file**; it does not retrieve anything itself. With 5 sources per row its @10 is
capped at your @5, so you would be reporting a @10 that is not real.

Free to change: BM25 ranking is deterministic, so the top 5 of a top-10 run is identical to a
top-5 run. The thresholds are **@5** (docs 0.80, code 0.50) and cannot move.

**Do:** default `k` to 10, regenerate both files, re-run `evaluate`. R@5 must still read 0.830
and 0.657. If it moves, something else broke.

## 3.5.3 `[x]` `max_context_length` as the validity check — done

`evaluate` now prints `Student data is valid: True` on both datasets (0 sources over 2000
characters), plus the question counts, mirroring the moulinette's header.

## 3.5.4 `[ ]` `evaluate` cosmetics — moved to 3.2

## 3.5.5 `lint-strict` still points at `.`

```make
lint-strict:
	flake8 src
	mypy . --strict
```
`mypy .` walks `data/raw/vllm-0.10.1/` — the whole vLLM source tree. Make it `mypy src --strict`.
`lint` is already correct (`flake8 src` / `mypy src`).

## 3.5.6 No flake8 config

There is no `.flake8`, `setup.cfg` or `tox.ini`. `flake8 src` works because the Makefile names
the directory, but bare `flake8 .` walks the corpus and never finishes (it blew past 120 s).
Cheap insurance:
```ini
[flake8]
exclude = .git,__pycache__,.venv,data,build,dist
max-line-length = 79
```

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

**Read `explaination.md` first** — what `torch`/`transformers` do, the 8 steps on a real
question, the class design, the speed table, links.

Budget real time: ~1.2 GB weights download on first run, then roughly 5–20 s per question on
this CPU (no GPU, 19 GB RAM) → 10–30 min per 100-question dataset.

Home for the code: **`src/rag_flow.py`** (today a 0-byte file).

**5.0 `[ ]` Dependencies.** `uv add transformers torch`. Prefer the CPU-only torch index (see
`explaination.md` §1) — the default Linux wheel pulls GBs of CUDA this machine cannot use.
**Accept when:** `uv run python -c "import torch, transformers; print(torch.__version__)"` works.

**5.1 `[ ]` `Generator` class in `rag_flow.py`.**

| Method | Does | Notes |
|---|---|---|
| `__init__(model_name='Qwen/Qwen3-0.6B')` | load tokenizer + model **once** | never inside a loop |
| `read_sources(srcs)` | `ft_open(path)[first:last]` per source | cache the file text if one file repeats |
| `build_prompt(question, texts)` | messages list: system rules, numbered sources with path, question last | see 5.3 |
| `answer(question, srcs) -> str` | template → tokenize → generate → decode new tokens only | see 5.4 |

Plain class, not pydantic (subject V.4: service classes are exempt).

**5.2 `[ ]` First milestone — print the prompt, no model.** Run `build_prompt` on the LoRA
question and read it: right text? paths present? question last? Only then load Qwen.

**5.3 `[ ]` Prompt shape.**
- System: answer **only** from the provided sources; say so if they do not contain the answer;
  be short; quote names/endpoints/flags exactly.
- User: `[1] <file_path>\n<text>` … then `Question: <question>`.
- Wrap with `tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True,
  enable_thinking=False)`.

**5.4 `[ ]` Generation settings.**
- `enable_thinking=False` — otherwise Qwen3 writes a long `<think>` block first.
- `do_sample=False` (greedy, reproducible), `max_new_tokens` ≈ 256.
- `with torch.inference_mode():` around `generate`.
- Decode `out[0][prompt_len:]` with `skip_special_tokens=True` — `generate` returns prompt + answer.

**5.5 `[ ]` Context budget.** Count tokens with the model's tokenizer; target ~2–3k for the
sources. Over budget → **drop the lowest-ranked source whole**, repeat. Never truncate mid-source.
Start with top 5 (R@5 = 0.830 already); try 3 vs 5 and keep the faster one if answers hold.

**5.6 `[ ]` `answer "<query>" --k`** — `search` → `Generator().answer()` → print.

**5.7 `[ ]` `answer_dataset --student_search_results_path --save_directory`**
- Read the `StudentSearchResults` file from `search_dataset` — **not** the index, no retrieval.
- Print `Loaded <n> questions`.
- One `Generator`, then a **tqdm** loop: `MinimalAnswer(**row.model_dump(), answer=...)`.
- Write `StudentSearchResultsAndAnswer(search_results=rows, k=data.k)` to
  `<save_directory>/<same input basename>`, `os.makedirs(..., exist_ok=True)`.
- Print `Saved student_search_results_and_answer to <path>`.
- Output scope: `data/output/search_results_and_answer/UnansweredQuestions/`.

**5.8 `[ ]` Register `answer` and `answer_dataset`** in `__main__.py`.

**5.9 `[ ]` Check answers.** For 5–10 questions compare with the ground-truth `answer` field in
`AnsweredQuestions/`. Note in `completed.md`: time per question, prompt variants tried, one good
and one bad example (README material).

**Accept when:** answers are coherent, grounded in the retrieved sources, and on point; the
output file parses back as `StudentSearchResultsAndAnswer` with an `answer` on every row. The
subject relaxes this bar because of the model's size; retrieval and prompt strategy carry the
weight.

---

# 6. Code quality — what remains

**6.1 `[x]` Type hints on every function** — `mypy src` with the subject's flags reports
`Success: no issues found in 10 source files`. See `completed.md` 6.7 for what the 20 errors
actually were.

**6.2 `[x]` flake8 clean** on `src` — all 7 findings gone.

**6.3 `[ ]` Dead code still present.**

| File | Dead |
|---|---|
| `src/index.py:30` | `skip_file` — superseded by the pattern-based `is_ignored` |
| `src/index.py:36` | `skip_folder` — same |
| `src/index.py` | the commented `bm25s.tokenize` line, the two commented lines at the end of `index_machine` |
| `src/evaluate.py:4` | `# from tqdm import tqdm` |
| `src/evaluate.py:22` | the commented `g_checker.rag_questions[...]` line |
| `src/rag_flow.py` | **0-byte file** — planned home of `Generator` (5.1) |
| `main.py` | `print("Hello from rag!")`, the `uv init` leftover; the entry point is `python -m src` |

flake8 does not flag commented-out code or an empty module, but the defense will ask what each
one is for.

**6.4 `[ ]` PEP 257 docstrings, and fix the typos:** `igonore`, `waht`, `breakk`, `probleme`,
`opend`, `march of hard chunk and overload` (in `iou` — it computes Intersection over Union),
`racll`. (`Moulinet` → `Moulinette` — done.)

**6.5 `[ ]` `chunk_nodes` has no docstring.** It is the most complex function in the project.

**6.6 `[ ]` Re-check every command's edge cases.** None may traceback: empty query, nonsensical
query, `k=0`, negative `k`, missing file, malformed JSON, missing index. The catch-all in
`__main__.py` is active now, so these print one line — verify each actually does.

---

# 7. Makefile — one line left

**7.1 `[x]` `run` passes `--max_chunk_size 2000`** explicitly — done.
**7.2 `[x]` `lint` targets `src`** rather than `.` — done, and that is what makes it finish.
**7.3 `[x]` `clean` does not touch `data/`** — correct, keep it that way.
**7.4 `[ ]` `lint-strict` still runs `mypy . --strict`** — walks the vLLM corpus. Use
`mypy src --strict`.

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
data/output/search_results/<Scope>/       both datasets at k=5, redo at k=10     [~]
data/output/search_results_and_answer/<Scope>/                                   [ ]
```
`.gitignore` has `/data/*` active and `git ls-files data` returns nothing — **nothing under
`data/` is tracked, which is correct.** Keep it that way: once a 100 MB blob is in history it
stays there, and a later `git rm` does not shrink the repo. Verify with
`git status --short` before any `git add`.

`[ ]` Add `transformers` and `torch` when starting part 5 (task 5.0).

---

# 11. Bonus — only after the mandatory part fully validates

- `[ ]` semantic embeddings (all-MiniLM-L6-v2) beside the lexical index
- `[ ]` hybrid retrieval, fusing the two rankings
- `[ ]` incremental indexing — needs 1.4 (`sorted()`) first
- `[ ]` caching: cold start and repeated queries
- `[ ]` local HTTP API

---

# Order of work

1. **3.1** delete `evaluate.py:78` — labels then match. **3.2** leftovers. *One line from done.*
2. **3.5** the pre-moulinette list: the `Public`/`public` path (`search.py:55`), `--k 10`
   default + regeneration (`search.py:56`), `lint-strict`, flake8 config.
3. **4** moulinette, until `Student data is valid: True`. *Catches format errors our own
   evaluator cannot see.*
4. **5** answer generation — read `explaination.md`, then 5.0 → 5.9 in order. *Biggest
   remaining piece.*
5. **1.1** Markdown chunker, then re-run `evaluate` on docs. *Keep it only if the number rises.*
6. **6.3-6.6** dead code, docstrings, edge cases.
7. **8** the README's 10 sections — material is already written in `completed.md`.
8. **9** tests.
9. **11** bonus.
