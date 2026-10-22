# task.md — what is left to do

**Next task:** fix `src/augmentation.py` (list **A** below), print the prompt for the LoRA
question, then load Qwen (5.4+). Moulinette (4) postponed — do it before the defense.

Remaining work only, for every part of the project. How the system works and what is already
done live in `completed.md`. Shell tests per part live in `checker.md`. How the LLM part works,
with links to read more, lives in `explaination.md`.

Legend: `[ ]` not started · `[~]` partial · **BLOCKER** = nothing after it can be measured.

---

# Working rules

- **I write all code.** Claude only reviews, explains and runs checks when asked — never edits
  `src/`.
- Before asking for a review, run the self-check below. Fix what it reports first.
- Known-good numbers are the test: any change to indexing/search must keep docs R@5 **0.830**
  and code R@5 **0.657**.

## Self-check — run all four, in order

```sh
uv run flake8 src                      # style + undefined names + syntax errors
make lint                              # flake8 + mypy with the subject flags (types)
uv run python -m src evaluate          # docs: 0.540 / 0.760 / 0.830 / 0.880, valid True
uv run python -m src evaluate \
  --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_code_public.json \
  --dataset_path data/datasets_public/public/AnsweredQuestions/dataset_code_public.json
                                       # code: 0.354 / 0.566 / 0.657 / ?, valid True
```

Prompt check (once list A is fixed — no model needed):
```sh
uv run python -c "
from src.search import search
from src.augmentation import Augmentation
q = 'What HTTP endpoint is used to dynamically load a LoRA adapter in vLLM?'
a = Augmentation()
a.read_sources(search(q, k=5), q)
for m in a.build_prompt():
    print('=====', m['role']); print(m['content'])
"
```
**Accept when:** two blocks (`system`, `user`), sources numbered `[1]..[5]` with their path,
the real chunk text under each, `Question: ...` last, and `/v1/load_lora_adapter` visible
somewhere in the text.

---

# A. Current fix list — `src/augmentation.py` (checked 2026-10-22)

`search()` is fixed (`MinimalSource(**c)` — returns real objects now). `evaluate` is fixed.
What `flake8` / runtime report on `augmentation.py` today:

| # | Line | Error | Why | Fix |
|---|---|---|---|---|
| A1 | 4 | `ModuleNotFoundError: No module named 'src.model'` (at import) | file is `models.py` | `from .models import MinimalSource` |
| A2 | 2 | `F401 '.search.search' imported but unused` | `read_sources` takes sources now — correct, so the import is dead | delete the line |
| A3 | 22 | `F821 undefined name 'query'` | `read_sources` has no `query` parameter | add `question: str` parameter, or store it and use it in `build_prompt` |
| A4 | 29-30 | `F541 f-string is missing placeholders` (29) **and** line 30 prints a literal `{self._context}` | the `f` is on the wrong line | remove `f` from 29, add it to 30 |
| A5 | 34 | `W391 blank line at end of file` | trailing empty line | delete it |
| A6 | 27 | — (silent) | no space after `codebase.` → `codebase.Use` | `'... codebase. '` |
| A7 | 7 | — | typo `Augmentaion` | `Augmentation` |
| A8 | 16 | — | `enumerate(sources)` starts at 0 → `file[0]` | `enumerate(sources, 1)`, label `[1] path` |
| A9 | 24-33 | — | one string with `SYSTEM:` / `USER:` labels — Qwen sees them as plain text, not roles | return `list[dict[str, str]]`: `[{"role": "system", ...}, {"role": "user", ...}]` |
| A10 | 15-20 | — (speed) | same file re-read per chunk (`lora.md` twice in the LoRA example) | `cache: dict[str, str]` — read each path once |

Order: A1-A5 (errors) → `make lint` clean → A6-A10 → prompt check above.

---

# Status in one line

Retrieval **verified end to end**: docs R@5 **0.830** (need 0.80), code R@5 **0.657** (need
0.50). `index`, `search`, `search_dataset`, `evaluate`, the models are done. docs search file
regenerated at `k=10` (R@10 **0.880**). **Now: augmentation (list A), then generation.**
Then: moulinette, Markdown strategy, dead code, README.

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

# 3. `evaluate` — `[x]` works, polish later

Output verified 2026-10-22, correct labels, 3 decimals:
```
docs   R@1 0.540   R@3 0.760   R@5 0.830   R@10 0.880   valid True  100 q
code   R@1 0.354   R@3 0.566   R@5 0.657   R@10 0.657   valid True   99 q
```

## 3.2 `[ ]` Polish (no score change) — "make it perfect later"

- `recalling(..., truth)` — `truth` has no type → `make lint` fails with `no-untyped-def`.
  Annotate `dict[str, MoulinetteAnsweredQuestion]` (import it).
- `g_checker` parameter of `recalling` is now unused — drop it.
- `truth[question.question_id]` → `.get()` + `continue` on `None` (no `KeyError` on unknown id).
- Catch `pydantic.ValidationError` next to `OSError` (import it).
- Delete `# print(questions)`, `# from tqdm import tqdm`; typo `SOmthing`; `iou` docstring
  ("march of hard chunk…" → "Intersection over Union of two character ranges").
- Header `"Evaluation Results \n ===="` — stray space before `====`.
- **Code search file is still `k=5`** — regenerate with `--k 10` (3.5.2), then R@10 for code is real.

---

# 3.5 Fix all of this BEFORE running the moulinette

Nothing here changes a score. All of it changes whether the moulinette accepts the output.

## 3.5.1 `[x]` `search_dataset` default path case — fixed (`public`)

```python
    'data/datasets_public/Public/UnansweredQuestions/dataset_docs_public.json',
```
The directory is **`public`**, lowercase. Linux filesystems are case-sensitive, so this is a
`FileNotFoundError` on the next run. `evaluate` has it right; `search_dataset` does not.

## 3.5.2 `[~]` `--k 10` — default changed, docs regenerated (k=10); **code file still k=5**

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

## 3.5.5 `[x]` `lint-strict` now runs `mypy src --strict` — fixed

```make
lint-strict:
	flake8 src
	mypy . --strict
```
`mypy .` walks `data/raw/vllm-0.10.1/` — the whole vLLM source tree. Make it `mypy src --strict`.
`lint` is already correct (`flake8 src` / `mypy src`).

## 3.5.6 `[ ]` No flake8 config

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

Two files, two stages (`rag_flow.py` deleted):
- **`src/augmentation.py`** — sources → prompt messages. No model. `[~]` in progress, list A.
- **`src/generation.py`** (to create) — messages → answer. Holds Qwen.

**5.0 `[x]` Dependencies.** `torch 2.14.1` + `transformers 5.20.2` in `pyproject.toml`, import
works. Note: the installed torch is the **CUDA build** (`+cu130`, `.venv` 5.7 GB, NVIDIA libs)
on a machine with no GPU — works, but optional switch to the CPU index
(`explaination.md` §1) makes `uv sync` far lighter for the reviewer.
Qwen weights **not downloaded yet** (`~/.cache/huggingface/hub` absent) — first
`from_pretrained` pulls ~1.2 GB; do it on a good connection.

**About `llm_sdk`** (deleted from the repo): it only offers `encode`/`decode`/
`get_logits_from_input_ids` — no `generate()`, no chat template, no KV cache. A token loop on
top of it re-runs the whole prompt per token (~100-200× more work than `generate`). Decision:
reuse its **loading** logic (device pick, dtype, `eval()`, no grad), generate with
`transformers` directly. Be ready to say this at the defense.

**5.1 `[~]` `Augmentation` class — `src/augmentation.py`.** See list **A** at the top.

| Method | Does |
|---|---|
| `__init__()` | settings only (later: tokenizer for the budget) — no per-question state needed |
| `read_sources(sources: list[MinimalSource], question: str)` | `ft_open(path)[first:last]` per source, numbered `[1] path`, cached per file |
| `build_prompt() -> list[dict[str, str]]` | `[{"role": "system", "content": RULES}, {"role": "user", "content": sources + "Question: ..."}]` |

Sources come **from the caller**: `search(q)` for `answer`, `row.retrieved_sources` for
`answer_dataset`. That is why `read_sources` must not call `search` itself.

**5.2 `[ ]` First milestone — print the prompt, no model.** Use the "Prompt check" command in
the Working rules section. Only then load Qwen.

**5.2b `[ ]` `Generator` class — `src/generation.py`.**

| Method | Does |
|---|---|
| `__init__(model_name='Qwen/Qwen3-0.6B')` | load tokenizer + model **once**, `model.eval()` |
| `generate(messages) -> str` | `apply_chat_template(..., enable_thinking=False)` → tokenize → `generate` in `torch.inference_mode()` → decode new tokens only |

Test alone first:
```sh
uv run python -c "
from src.generation import Generator
g = Generator()
print(g.generate([{'role': 'user', 'content': 'Say hello in 5 words.'}]))
"
```
Accept when: a short sentence, no `<think>`, no echoed prompt. Note the time it takes.

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

**5.6 `[ ]` `answer "<query>" --k`** — `search(q)` → `Augmentation` → `Generator.generate()` → print.

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
| `src/search.py` `search()` | prints one line per hit — fine for the CLI, noisy when `answer` calls it; move the print to the command later |
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

1. **A1-A10** fix `augmentation.py`, then the prompt check. *Current work.*
2. **5.2b** `generation.py`, test alone; then **5.6-5.9** `answer`, `answer_dataset`, register,
   check answers. *Biggest remaining piece.*
3. **3.2** `evaluate` polish + regenerate the code search file at `--k 10`.
4. **3.5.6** `.flake8` config, then **4** moulinette (`~/Downloads/RAG/moulinette.zip`), until
   `Student data is valid: True`. *Before the defense, no exceptions.*
5. **1.1** Markdown chunker, then re-run `evaluate` on docs. *Keep it only if the number rises.*
6. **6.3-6.6** dead code, docstrings, edge cases.
7. **8** the README's 10 sections — material is already written in `completed.md`.
8. **9** tests.
9. **11** bonus.
