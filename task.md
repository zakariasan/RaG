# task.md — what is left to do

**Next task:** list **G** — make one question fast enough that a dataset run is practical,
with **H** (see each answer live, save as you go, resume) next to it. **I** = every future
enhancement (5 bonuses + quality), with steps.
A (augmentation), B (generation), C (`answer`) work; D (`answer_dataset`) is written and lints,
but a 3-question run did not finish in 10 min. Then E (polish), F (moulinette, before defense).

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

# B. `src/generation.py` — `[x]` works (2026-10-23)

Test B passed: `Hello! How can I assist you today?` — no `<think>`, no echoed prompt.
First load 37.9 s (includes the 1.5 GB download, now cached in `~/.cache/huggingface/hub`);
generation of a ~15-token prompt: 4.8 s. `make lint` clean.
Leftover: the decode-check error message says "chat template".

The steps below are kept as the reference for the defense.

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

# C. `answer` command — `[x]` works (2026-10-23), slow

LoRA question → `The HTTP endpoint used to dynamically load a LoRA adapter in vLLM is
`/v1/load_lora_adapter`.` — correct, grounded. Took minutes (see G). `search()` prints its 5
hit lines before the answer (E). Leftover: docstring.

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

# D. `answer_dataset` command — `[~]` written, lints, not yet run to completion

Code matches D1-D11 (parse with `StudentSearchResults`, one `Generator`, tqdm, write once
after the loop, `k=questions.k`, subject's print texts). The 3-question test was **stopped
after 10 min without finishing** — speed problem, not a code bug. Do G first, then re-run the
3-question test. Leftovers: `unit=' Question'` → `'question'`, closing `)` indent at line 59,
docstrings.

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

# G. Speed — `[ ]` NEXT

**Why it is slow — the machine, measured:** Intel i7-7600U (2017 laptop), **2 cores / 4
threads**, torch uses 2 threads, no GPU. "Say hello" (~15 prompt tokens) = 4.8 s. A real question
= ~2200 prompt tokens (5 sources × ~2000 chars) + up to 256 answer tokens → minutes.

Two costs (see `explaination.md` §5):
- **prefill** — reading the prompt. Grows with prompt length → fewer/shorter sources.
- **decode** — writing the answer, one full model pass per token → fewer answer tokens.

Do **G1 first** so every later change is a measured number, not a guess.

| # | Change | Where | Expected effect |
|---|---|---|---|
| G1 | **Measure.** In `generate`, time the call and print `prompt_tokens`, `new_tokens`, seconds: `ids['input_ids'].shape[1]` and `len(new)` | `generation.py` | tells you if prefill or decode dominates |
| G2 | `max_new_tokens` 256 → **128** | `generation.py` default | decode capped at half |
| G3 | System rule: *"Answer in 1 to 3 sentences."* | `augmentation.py` system content | model stops earlier on its own — real answers are 1-2 sentences |
| G4 | **k = 3** instead of 5 in `answer` / `answer_dataset` | `answer.py` defaults | prompt ~40% shorter. Cost: right chunk in top 3 for 76% of docs questions vs 83% in top 5 — measure answer quality, not just time |
| G5 | **Token budget**: count tokens with `self.tokenizer`, drop the lowest-ranked source **whole** while over e.g. 1500 tokens | `augmentation.py` (needs the tokenizer passed in) | caps worst-case prompts (some chunks are code = more tokens per char) |
| G6 | Try `torch.set_num_threads(4)` once, compare with 2 | `generation.py` `__init__` | maybe faster, maybe slower (2 physical cores) — keep only if G1 says so |

**Test after each change** — one question, compare with the G1 baseline:
```sh
time uv run python -m src answer "What HTTP endpoint is used to dynamically load a LoRA adapter in vLLM?"
```
Accept when: still names `/v1/load_lora_adapter`, and time drops. Record every row
(change → prompt tokens → new tokens → seconds) in `completed.md` — that table is README
*Performance analysis* material.

**Running a full dataset anyway.** Even fast, 100 questions on this CPU is long. Run it detached
and let it go overnight:
```sh
nohup uv run python -m src answer_dataset > answer_docs.log 2>&1 &
tail -f answer_docs.log        # tqdm shows progress + time left
```
The subject relaxes answer quality because of the model; it does not set a time limit on
`answer_dataset` (limits are on indexing 5 min and retrieval 90 s).

Not worth it here: bf16/fp16 on this CPU (no native support → slower), batching (complex,
little gain on 2 cores).

---

# H. Live feedback and safe long runs — `[ ]` with / right after G

None of these makes a single question faster (only G does). They make a long run **visible**
(see each answer as it comes, stop early if bad) and **safe** (Ctrl+C or a crash loses nothing).

## H1 `[ ]` Print each answer as soon as it is generated — `answer.py`, `answer_dataset`

Inside the loop, right after `ans = g.generate(msg)`:
```python
tqdm.write(f'Q: {question.question}\nA: {ans}\n')
```
**Why `tqdm.write`, not `print`:** `print` breaks the progress bar into many lines;
`tqdm.write` prints above the bar and redraws it.
Optional: a `verbose: bool = True` parameter so the CLI can turn it off (`--verbose False`).
**Accept when:** the 3-question test shows 3 Q/A blocks above one clean bar.

## H2 `[ ]` Save as you go — `answer_dataset`

Today the file is written once at the end → a stop at question 80 loses 80 answers.

| Step | What exactly |
|---|---|
| H2.1 | compute `path` (and `os.makedirs`) **before** the loop, not after |
| H2.2 | move the write into a small helper `save(rows, k, path)` that builds `StudentSearchResultsAndAnswer` and writes `model_dump_json(indent=4)` |
| H2.3 | inside the loop: `if len(rows) % 10 == 0: save(rows, questions.k, path)` |
| H2.4 | after the loop: `save(...)` once more (the last <10 rows) + the `Saved ...` print |

**Why every 10, not every 1:** rewriting the whole file each question costs more as it grows;
every 10 bounds the loss to 10 answers and the cost to 10 writes per 100 questions.
**Accept when:** Ctrl+C after ~12 questions leaves a valid file with 10 answered rows.

## H3 `[ ]` Resume after a stop — `answer_dataset` (needs H2)

| Step | What exactly |
|---|---|
| H3.1 | before the loop: `if os.path.exists(path):` load it with `StudentSearchResultsAndAnswer.model_validate_json(ft_open(path))` |
| H3.2 | `done = {r.question_id: r for r in old.search_results}`; start `rows = list(old.search_results)` |
| H3.3 | in the loop: `if question.question_id in done: continue` |
| H3.4 | `print(f'Resuming: {len(done)} already answered')` |
| H3.5 | **wrap H3.1 in `try/except ValidationError`** — a half-written or old-format file must not crash; start fresh instead |
| H3.6 | parameter `resume: bool = True`, so `--resume False` forces a fresh run |

**Watch out:** output row order must stay the input order. Simplest: build the final list by
walking `questions.search_results` and taking each answer from `done` or the new result.
**Accept when:** stop at 12, re-run → prints `Resuming: 10 already answered`, the bar starts at
10/100, final file has 100 rows in input order.

## H4 `[ ]` Stream the words — `generation.py`, used by `answer` only

```python
from transformers import TextStreamer
streamer = TextStreamer(self.tokenizer, skip_prompt=True, skip_special_tokens=True)
out = self.model.generate(**ids, streamer=streamer, max_new_tokens=..., do_sample=False)
```
- Add a parameter `stream: bool = False` to `generate`; pass `streamer` only when `True`.
- `answer` calls `generate(msg, stream=True)` and **does not print the return value again**
  (the streamer already printed it).
- `answer_dataset` keeps `stream=False` — streaming would fight with the tqdm bar.
**Accept when:** words appear one by one on `answer "..."`, total time unchanged.

## H5 `[ ]` Interactive mode — new command `chat` (optional, good for the defense demo)

Every `answer` call reloads the index and the model. A loop loads both once:

| Step | What exactly |
|---|---|
| H5.1 | `chat(k: int = 3) -> None` in `answer.py`; create `Augmentation()` and `Generator()` once |
| H5.2 | `while True: q = input('answer> ').strip()` |
| H5.3 | `if q in ('', 'exit', 'quit'): break` |
| H5.4 | `search` → `read_sources` → `build_prompt` → `generate(msg, stream=True)` |
| H5.5 | catch `ValueError` from `search` (short/empty query) per question: print it, keep looping |
| H5.6 | `EOFError` (Ctrl+D) → break cleanly |
| H5.7 | register `'chat': chat` in `__main__.py` |

**Accept when:** 3 questions in a row, the model loads once, `exit` and Ctrl+D both quit
without a traceback.

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

Subject chapter IX: graded **only** if the whole mandatory part validates; each is 1 point,
must **work** (not just be described), may be demoed, CPU-only machine. Details in list **I**.

- `[ ]` I1 semantic embeddings (all-MiniLM-L6-v2) beside the lexical index
- `[ ]` I2 hybrid retrieval, fusing the two rankings
- `[ ]` I3 incremental indexing — needs 1.4 (`sorted()`) first
- `[ ]` I4 caching: cold start and repeated queries
- `[ ]` I5 local HTTP API

---

# I. Future enhancements — the full list, with how

Two kinds: **I1-I5 = the 5 official bonuses** (points), **I6-I12 = quality** (no points by
themselves, but they raise recall, answer quality or the defense). Every retrieval change is
judged by `evaluate`: docs R@5 0.830 / code R@5 0.657 are the numbers to beat — keep a change
only if it wins, and record it in `completed.md` either way (a measured "no" is a result).

## I1 `[ ]` Bonus 1 — Semantic embeddings

**Idea:** BM25 matches **words**; embeddings match **meaning** ("load adapter" ≈ "register
LoRA"). Each chunk becomes a vector of 384 numbers; a question too; nearest vectors = similar.

| Step | What exactly |
|---|---|
| I1.1 | `uv add sentence-transformers` (pulls on the torch you already have) |
| I1.2 | in `index`: after chunking, `m = SentenceTransformer('all-MiniLM-L6-v2')`; `emb = m.encode(chunk_texts, batch_size=64, show_progress_bar=True, normalize_embeddings=True)` |
| I1.3 | save `np.save(save_dir/'embeddings.npy', emb)` — **row i = chunk i**, same invariant as BM25 (`completed.md` 3.6) |
| I1.4 | new `search_semantic(query, k)`: encode the query (normalized), `scores = emb @ q`, `np.argsort(-scores)[:k]` → chunk ids → `MinimalSource` |
| I1.5 | flag `--method bm25|semantic|hybrid` on `search` / `search_dataset` |
| I1.6 | measure with `evaluate` on both datasets, record the table |

**Watch out:** ~18 700 chunks on this CPU = several minutes of encoding — check it stays under
the **5-minute indexing limit**; if not, embed only `.py/.md/.txt`. MiniLM reads max 256 tokens
→ a 2000-char chunk is partly cut; note it in the README.
**Expect:** better on paraphrased docs questions, worse on exact identifiers.

## I2 `[ ]` Bonus 2 — Hybrid retrieval (needs I1)

**Idea:** take both rankings and merge them. Use **Reciprocal Rank Fusion** — it needs only the
ranks, so BM25 scores (0-30) and cosine scores (0-1) never have to be compared.

| Step | What exactly |
|---|---|
| I2.1 | get top 50 from BM25 and top 50 from semantic |
| I2.2 | `score[chunk] += 1 / (60 + rank)` for each list it appears in (rank from 1; 60 is the standard constant) |
| I2.3 | sort by fused score, take top k |
| I2.4 | `evaluate` both datasets: BM25 vs semantic vs hybrid, one table |

**Accept when:** hybrid R@5 ≥ the best of the two alone on at least one dataset. If not,
keep it as an option and report the numbers.

## I3 `[ ]` Bonus 3 — Incremental indexing (needs 1.4)

**Idea:** a changed file re-indexes only that file.

| Step | What exactly |
|---|---|
| I3.1 | 1.4 first: `sorted()` files and folders so the order is stable |
| I3.2 | save a manifest `data/processed/manifest.json`: `{path: {"mtime": ..., "size": ..., "sha1": ..., "chunks": [first_id, last_id]}}` |
| I3.3 | on `index --incremental`: walk, compare with the manifest → lists `added`, `changed`, `deleted` |
| I3.4 | keep the chunks of unchanged files, re-chunk only `added + changed`, drop `deleted` |
| I3.5 | **rebuild the BM25 matrix** from the kept + new token lists (bm25s cannot patch in place; tokenizing is the slow part, BM25 build is fast) — so also save the token lists per file |
| I3.6 | rewrite `chunks.json`, BM25 files, embeddings (if I1) **in the same order** |
| I3.7 | print `Re-indexed <n> files, kept <m>` |

**Accept when:** `touch` one file → incremental run re-chunks 1 file, far faster than a full
index, and `evaluate` gives the **same** numbers as a full rebuild.
**Watch out:** the parallel-list invariant — this is where it breaks silently.

## I4 `[ ]` Bonus 4 — Caching

| Step | What exactly |
|---|---|
| I4.1 | **cold start:** measure today: time to load `chunks.json` + BM25 + model |
| I4.2 | index cache: keep the loaded retriever/chunks in a module-level object so `chat` / the API (I5) load once; optional `mmap=True` on `BM25.load` |
| I4.3 | query cache: `functools.lru_cache` on a `retrieve(query, k)` that returns a **tuple** (lists are unhashable / mutable) |
| I4.4 | answer cache on disk: `data/cache/answers.json` keyed by `sha1(question + source ids + model + prompt version)` → a repeated question returns instantly |
| I4.5 | measure: first vs second call of the same query, write both times in `completed.md` |

**Watch out:** the cache key must include the **prompt version** — change the prompt, old
cached answers must not come back.

## I5 `[ ]` Bonus 5 — Local HTTP API

| Step | What exactly |
|---|---|
| I5.1 | `uv add fastapi uvicorn` |
| I5.2 | `src/api.py`: load index + `Generator` **once at startup** |
| I5.3 | `GET /search?q=...&k=5` → `list[MinimalSource]` (pydantic models serialize directly) |
| I5.4 | `POST /answer` body `{"question": "...", "k": 3}` → `MinimalAnswer` |
| I5.5 | errors → HTTP 400 with the message (empty query, bad k), never a 500 traceback |
| I5.6 | command `serve --host 127.0.0.1 --port 8000` registered in `__main__.py` |
| I5.7 | flake8 + mypy apply to this file too (subject) |

Test: `curl 'http://127.0.0.1:8000/search?q=lora+adapter&k=3'` and
`curl -X POST http://127.0.0.1:8000/answer -H 'Content-Type: application/json' -d '{"question":"What HTTP endpoint loads a LoRA adapter?"}'`.
**Bind to `127.0.0.1`**, not `0.0.0.0` — "local" API, and nothing on the network should reach
a model server.

## I6 `[ ]` Markdown chunker — same as 1.1 (mandatory-ish: two distinct strategies)

Heading-based splitting, never inside a ``` fence. Keep only if docs R@5 ≥ 0.830. See 1.1.

## I7 `[ ]` Prompt improvements (answer quality)

- Tell the model the source numbers: *"Cite the source number like [2]."* — answers become
  checkable at the defense.
- Put the **highest-ranked source last**, next to the question (small models attend most to
  the end of the prompt). Measure on the same 10 questions.
- For code questions, add the language hint: *"Sources may be Python code."*
- Keep a `PROMPT_VERSION = 'v1'` constant; bump it on every change (needed by I4.4).

## I8 `[ ]` Answer evaluation (measure answers, not only retrieval)

| Step | What exactly |
|---|---|
| I8.1 | command `evaluate_answers --answers_path ... --dataset_path ...` |
| I8.2 | per question: word overlap between our answer and the ground-truth `answer` (lowercase tokens, `|ours ∩ truth| / |truth|`) |
| I8.3 | print the mean, plus the 3 worst questions to read by hand |
| I8.4 | use it to compare prompt versions (I7) and k=3 vs k=5 (G4) with a number |

Crude, but turns "the answers look better" into a figure for the README.

## I9 `[ ]` Retrieval tuning (cheap, measurable)

- BM25 parameters: try `k1` ∈ {1.2, 1.5, 2.0}, `b` ∈ {0.5, 0.75, 0.9}; a loop over 9
  combinations, `evaluate` each, keep the best. Record the grid in `completed.md`.
- Re-try the `.py/.md/.rst/.txt` filter: 0.850 vs 0.830 docs (`completed.md` 6.2) — decide again
  once everything else is fixed.
- Boost the file path: add path tokens (`docs`, `features`, `lora`) to each chunk's tokens —
  questions often name the feature that is also the file name.

## I10 `[ ]` Tests — same as section 9

pytest, run with `uv run pytest`; add a `test` rule to the Makefile. Start with
`hard_split`, `tokenizer`, `iou`, chunk reconstruction.

## I11 `[ ]` Robustness pass (the reviewer "pushes it in odd directions")

Every command, each must print one line, never a traceback: empty query, 1-char query, `k=0`,
`k=-1`, `k=100000`, missing index, missing dataset file, malformed JSON, dataset with 0
questions, a question in another language, Ctrl+C during `answer_dataset` (with H2 the file
must still be valid).

## I12 `[ ]` Smaller wins

- `search()` print → move to the CLI path (E).
- `.flake8` config (3.5.6).
- `make lint-strict` with `uv run` (7).
- CPU-only torch wheel → `uv sync` GBs lighter for the reviewer (`explaination.md` §1).

---

# Order of work

1. **G** speed: G1 measure, then G2-G6 one at a time. *Current work.*
   **H1** (print each answer) alongside — 1 line, makes every test readable.
2. **H2 + H3** save as you go + resume. *Makes the long run safe.*
3. **D** re-run the 3-question test, then the full datasets (overnight, `nohup`), D12 check
   answers. **H4** streaming for `answer`.
3. **3.2** `evaluate` polish + regenerate the code search file at `--k 10`.
4. **3.5.6** `.flake8` config, then **4** moulinette (`~/Downloads/RAG/moulinette.zip`), until
   `Student data is valid: True`. *Before the defense, no exceptions.*
5. **1.1** Markdown chunker, then re-run `evaluate` on docs. *Keep it only if the number rises.*
6. **6.3-6.6** dead code, docstrings, edge cases.
7. **8** the README's 10 sections — material is already written in `completed.md`.
8. **9** tests (I10), **I11** robustness pass.
9. **I7, I8, I9** quality: prompt, answer evaluation, BM25 tuning.
10. **I1-I5** bonus — only once the mandatory part validates in full. Suggested order:
    I4 caching (smallest) → I5 API (reuses I4) → I1 embeddings → I2 hybrid → I3 incremental
    (hardest). **H5** `chat` fits with I4/I5.
