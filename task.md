# task.md — what is left to do

**Next task:** list **B** — write `src/generation.py` and test it alone. Augmentation (list A)
works. Then C (`answer`), D (`answer_dataset`), E (polish), F (moulinette, before the defense).

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

Prompt check (no model needed) — **passes today**:
```sh
uv run python -c "
from src.search import search
from src.augmentation import Augmentation
q = 'What HTTP endpoint is used to dynamically load a LoRA adapter in vLLM?'
a = Augmentation()
a.read_sources(search(q, k=5))
p = a.build_prompt(q)
for m in p:
    print('=====', m['role']); print(m['content'])
c = p[1]['content']
print('endpoint:', '/v1/load_lora_adapter' in c, '| question:', q in c)
"
```
**Accept when:** roles `system`, `user` · sources numbered from 1 with their path · real chunk
text under each · `Question: ...` last · last line prints `endpoint: True | question: True`.

---

# A. `src/augmentation.py` — `[x]` works (checked 2026-10-22)

Prompt check passes: 2 roles, 5 sources, ~8700 chars (~2200 tokens), endpoint and question
present. flake8 clean. Leftovers, no rush:

| # | Line | What | Fix |
|---|---|---|---|
| A11 | 36 | `Question:{query}` — no space | `Question: {query}` |
| A12 | 15-16 | same file read once per chunk (`lora.md` read twice) | `cache: dict[str, str] = {}`; `if path not in cache: cache[path] = ft_open(path)` |
| A13 | 8, 24 | docstrings `pipeLine`, `Build prom for the llm can give us ans` | `"""Turn retrieved sources into chat messages for the LLM."""` style |
| A14 | 17 | label `file[1]: path` | `[1] path` is shorter and is what the system rule can refer to |

---

# B. `src/generation.py` — `[ ]` NEXT

Today: a stub. mypy says `generation.py:6: Missing return statement [empty-body]` — expected,
disappears when `generate` returns a string.

**What to write, in this order:**

| Step | Where | What exactly |
|---|---|---|
| B1 | top of file | `import torch` and `from transformers import AutoModelForCausalLM, AutoTokenizer` |
| B2 | `__init__` | `self.tok = AutoTokenizer.from_pretrained(name)` |
| B3 | `__init__` | `self.model = AutoModelForCausalLM.from_pretrained(name)` then `self.model.eval()` |
| B4 | `generate` signature | `def generate(self, msg: list[dict[str, str]], max_new_tokens: int = 256) -> str:` (bare `list[dict]` → fix the type) |
| B5 | `generate` | `text = self.tok.apply_chat_template(msg, tokenize=False, add_generation_prompt=True, enable_thinking=False)` |
| B6 | `generate` | `ids = self.tok(text, return_tensors='pt')` |
| B7 | `generate` | inside `with torch.inference_mode():` → `out = self.model.generate(**ids, max_new_tokens=max_new_tokens, do_sample=False)` |
| B8 | `generate` | `new = out[0][ids['input_ids'].shape[1]:]` — keep only the answer tokens |
| B9 | `generate` | `return self.tok.decode(new, skip_special_tokens=True).strip()` |

**Why each matters** (defense): B3 `eval()` turns off training behaviour · B5
`enable_thinking=False` stops the `<think>` block · B7 `inference_mode` no gradients,
`do_sample=False` same answer every run · B8 `generate` returns prompt + answer.

**mypy note:** `transformers` has no complete type stubs; `decode` / `apply_chat_template` may
come back as `Any` or a union. If `--warn-return-any` complains on B9, wrap: `str(...)`.

**Test B alone** (first run downloads ~1.2 GB into `~/.cache/huggingface/hub`):
```sh
uv run python -c "
import time
from src.generation import Generator
t = time.time(); g = Generator(); print('load', round(time.time() - t, 1), 's')
t = time.time(); print(g.generate([{'role': 'user', 'content': 'Say hello in 5 words.'}]))
print('gen', round(time.time() - t, 1), 's')
"
```
**Accept when:** one short sentence · no `<think>` · no echoed prompt · write down load and gen
times in `completed.md`.

**Then test B + A together** (the real thing, one question):
```sh
uv run python -c "
from src.search import search
from src.augmentation import Augmentation
from src.generation import Generator
q = 'What HTTP endpoint is used to dynamically load a LoRA adapter in vLLM?'
a = Augmentation(); a.read_sources(search(q, k=5))
print(Generator().generate(a.build_prompt(q)))
"
```
**Accept when:** the answer names `/v1/load_lora_adapter` (ground truth says so).

---

# C. `answer` command — `[ ]` after B

| Step | What exactly |
|---|---|
| C1 | new function `answer(query: str = '', k: int = 5) -> None` (file: `generation.py` or a new `answer.py`) |
| C2 | `sources = search(query, k=k)` |
| C3 | `a = Augmentation(); a.read_sources(sources); msg = a.build_prompt(query)` |
| C4 | `print(Generator().generate(msg))` |
| C5 | register in `__main__.py`: `'answer': answer` |

Test: `uv run python -m src answer "What HTTP endpoint is used to dynamically load a LoRA adapter in vLLM?" --k 5`
Edge cases that must print one line, not traceback: `answer ""`, `answer "x" --k 0`.

---

# D. `answer_dataset` command — `[ ]` after C

| Step | What exactly |
|---|---|
| D1 | `answer_dataset(student_search_results_path: str = 'data/output/search_results/UnansweredQuestions/dataset_docs_public.json', save_directory: str = 'data/output/search_results_and_answer/UnansweredQuestions', k: int = 5) -> None` |
| D2 | `data = StudentSearchResults.model_validate_json(ft_open(student_search_results_path))` — **no search, no index** |
| D3 | `print(f'Loaded {len(data.search_results)} questions')` |
| D4 | create `Augmentation()` and `Generator()` **once, before the loop** |
| D5 | `for row in tqdm(data.search_results, desc='Answering', unit='question'):` |
| D6 | inside: `a.read_sources(row.retrieved_sources[:k])`, `msg = a.build_prompt(row.question)`, `ans = g.generate(msg)` |
| D7 | inside: `rows.append(MinimalAnswer(**row.model_dump(), answer=ans))` |
| D8 | after loop: `out = StudentSearchResultsAndAnswer(search_results=rows, k=data.k)` |
| D9 | `os.makedirs(save_directory, exist_ok=True)`; `path = os.path.join(save_directory, os.path.basename(student_search_results_path))` |
| D10 | write `out.model_dump_json(indent=4)`; `print(f'Saved student_search_results_and_answer to {path}')` |
| D11 | register in `__main__.py`: `'answer_dataset': answer_dataset` |

**Why `[:k]` in D6:** the search files now hold 10 sources; 10 × ~550 tokens ≈ 5500 tokens per
prompt = slow. 5 keeps R@5 = 0.830 and halves the time.

**Test small first** — make a 3-question copy so a run takes a minute, not 30:
```sh
uv run python -c "
import json
p = 'data/output/search_results/UnansweredQuestions/dataset_docs_public.json'
d = json.load(open(p)); d['search_results'] = d['search_results'][:3]
json.dump(d, open('/tmp/mini_docs.json', 'w'))
"
uv run python -m src answer_dataset --student_search_results_path /tmp/mini_docs.json --save_directory /tmp/out
uv run python -c "
from src.models import StudentSearchResultsAndAnswer
r = StudentSearchResultsAndAnswer.model_validate_json(open('/tmp/out/mini_docs.json').read())
print(len(r.search_results), all(x.answer for x in r.search_results))
"
```
**Accept when:** `3 True`. Then the full docs run (note the total time), then code.

**D12 `[ ]` Check answers.** Compare 5-10 answers with the `answer` field in
`data/datasets_public/public/AnsweredQuestions/dataset_docs_public.json`. Record in
`completed.md`: time per question, one good and one bad answer, any prompt change you tried.

---

# E. Polish — `[ ]` after D (details in 3.2, 6.3-6.6)

- `evaluate.py`: type `truth`, drop unused `g_checker`, `.get()`, catch `ValidationError`,
  delete commented lines, fix typos.
- Regenerate the **code** search file at `--k 10`, re-run evaluate (R@5 must stay 0.657).
- `search()` prints per hit — move the print into the CLI path so `answer` output is clean.
- Dead code (6.3), docstrings (6.4, 6.5), edge cases (6.6).

# F. Before the defense — `[ ]`

- `.flake8` config (3.5.6).
- Moulinette (4): unzip `~/Downloads/RAG/moulinette.zip`, run on docs and code, see
  `Student data is valid: True`.
- README, 10 sections (8).

---

# Status in one line

Retrieval **verified end to end**: docs R@5 **0.830** (need 0.80), code R@5 **0.657** (need
0.50). `index`, `search`, `search_dataset`, `evaluate`, the models, **augmentation** are done.
docs search file at `k=10` (R@10 **0.880**). **Now: B generation.** Then C, D, E, F.

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

1. **B** `generation.py`, test alone, then with A. *Current work.*
2. **C** `answer`, **D** `answer_dataset` (+ D12 check answers). *Biggest remaining piece.*
3. **3.2** `evaluate` polish + regenerate the code search file at `--k 10`.
4. **3.5.6** `.flake8` config, then **4** moulinette (`~/Downloads/RAG/moulinette.zip`), until
   `Student data is valid: True`. *Before the defense, no exceptions.*
5. **1.1** Markdown chunker, then re-run `evaluate` on docs. *Keep it only if the number rises.*
6. **6.3-6.6** dead code, docstrings, edge cases.
7. **8** the README's 10 sections — material is already written in `completed.md`.
8. **9** tests.
9. **11** bonus.
