# test.md — test every part + mandatory checklist

Last full retest: **2026-10-23** on uncommitted work after `c20ca0c`. Tests never modify
`src/` or `data/` (outputs go to `/tmp/ragt`). lint-strict skipped by decision.
How to read: run a block, compare with **Expect**, tick the box. `[x]` = passed at last retest.

```sh
mkdir -p /tmp/ragt          # scratch dir for every test below
```

---

## 1. Mandatory checklist (subject chapters V, VI, VII, VIII)

`[x]` OK · `[~]` partial · `[ ]` missing. Each line names the test in §4 that proves it.

### V — common rules
- [x] Python ≥ 3.10 (3.13)
- [~] flake8 clean — `src` clean except `search.py:16 F401`; **`flake8 .` (subject) fails**: no `.flake8` exclude, `test.py:4` (T1)
- [x] mypy with subject flags on `src` (T1) — [ ] on `.` as subject's `lint` rule says
- [x] exceptions handled, no traceback on edge cases (T5–T9)
- [x] context managers for files
- [~] type hints everywhere (`retrieve`/`generate` OK; `Generator.generate` still `-> Any` is weak)
- [ ] **docstrings PEP 257 (Google/NumPy) on every function and class** — many missing / typos
- [~] Makefile: `install run debug clean lint` exist — `lint` uses `src` not `.`, no `uv run`; `debug` uses pudb (subject: pdb e.g.) (T2)
- [x] `.gitignore` present
- [ ] test programs (pytest) — not graded, recommended
- [x] pydantic for data models (T10)
- [x] uv only, `uv sync` works
- [x] Python Fire CLI + tqdm on long ops
- [x] Qwen/Qwen3-0.6B default

### VI.1 indexing
- [x] whole corpus ≤ 5 min (~7 s) (T3)
- [x] Python chunking (AST)
- [ ] **Markdown / text chunking as a distinct strategy** — today same line splitter (risk at defense)
- [x] BM25
- [x] `--max_chunk_size` default 2000, no chunk > 2000 (T3)
- [x] index persisted in `data/processed/`

### VI.2 retrieval
- [x] single query `search` (T4)
- [x] batch `search_dataset` from JSON (T6)
- [x] `file_path` exact corpus path `data/raw/vllm-0.10.1/...`
- [x] docs R@5 ≥ 0.80 → **0.830**; code R@5 ≥ 0.50 → **0.657** (T7)
- [x] 200 questions ≤ 90 s (~40 s incl. startup) (T6)

### VI.3 answer generation
- [x] Qwen3-0.6B answers single query, grounded (T8)
- [ ] **"within its token budget"** — fixed k=3 only, no token count / budget
- [ ] **full `answer_dataset` run on docs + code never completed**
- [ ] `Processed i of N questions` print (shown in subject VI.7.2 step 4)

### VI.4 / VI.5 models + output
- [x] all model field names match (T10)
- [x] `StudentSearchResults` file valid
- [ ] `StudentSearchResultsAndAnswer` files exist for docs + code (after full run)
- [~] `k` in files: docs 10, **code file in `data/output` still 5** → regenerate

### VI.6 CLI
- [x] 6 commands, every path a CLI arg (T4–T9)
- [x] edge cases: empty query, nonsense query, k=0, k<0, huge k, missing file, missing index, malformed JSON, empty dataset (T5, T9)
- [~] malformed JSON message = 3-line pydantic dump + `Error404` tag (works, ugly)
- [x] never imports the moulinette

### VI.7 layout + walkthrough
- [x] `src/`, `pyproject.toml`, `uv.lock`, `README.md`, `data/raw/`, `data/processed/`
- [ ] **`data/datasets/UnansweredQuestions/` + `data/datasets/AnsweredQuestions/`** — today `data/datasets_public/public/...`
- [x] `data/output/search_results/<Scope>/`
- [ ] `data/output/search_results_and_answer/<Scope>/` (after full run)
- [ ] VI.7.2 four commands pasted **verbatim** work (T12)

### VII evaluation
- [x] own `evaluate` matches hand recompute
- [ ] **moulinette run, `Student data is valid: True`** (T11)

### VIII README
- [x] first line italic login
- [ ] Description · Instructions · Resources + AI usage · System architecture · Chunking strategy · Retrieval method · Performance analysis · Design decisions · Challenges faced · Example usage (outline §7)

### IX bonus — only after everything above is `[x]`
- [ ] embeddings · [ ] hybrid · [ ] incremental · [ ] caching · [ ] HTTP API

---

## 2. Bug status

### Fixed and re-tested 2026-10-23
| # | Bug | Where | Status |
|---|---|---|---|
| 1 | `ft_open` swallowed OSError → `src_file` unbound | `utils.py` | FIXED |
| 2 | exit code always 0 | `__main__.py` | FIXED (1 / 130) |
| 3 | torch loaded for every command (22–46 s `search`) | `answer.py` lazy import | FIXED (~1.4 s) |
| 4 | `search` printed twice | `search.py` | FIXED |
| 5 | `search_dataset` k ≤ 0 / k not capped / empty dataset / `"a ?"` hang or random sources | `search.py` keep/hits | FIXED |
| 6 | `answer` got 0 sources | `retrieve` | FIXED |
| 7 | `answer_dataset` k not checked | `answer.py` | FIXED |
| 8 | `evaluate` inverted check, missing file rc 0 | `evaluate.py` | FIXED |
| 9 | bf16 on CPU never finished | `generation.py` | FIXED (fp32) |
| 10 | `generate` typed `list[dict]` | `generation.py` | FIXED (`Any`; `str` better) |

### Still open — mandatory-relevant
| # | Where | Bug | Fix |
|---|---|---|---|
| M1 | `search.py:16` | F401 unused `typing.Any` → `make lint` fails | delete line |
| M2 | `__main__.py:23` | ValidationError: `Error404` + 3-line dump, stdout | `ERROR414: invalid JSON/dataset: {e.errors()[0]['msg']}`, `file=sys.stderr` |
| M3 | `evaluate.py:33-37` | only `sources[0]` checked; divides by student count, not truth count | loop all truth sources, mean over truth (moulinette is the reference) |
| M4 | `evaluate.py:31` | KeyError if student has an id not in truth | `truth.get(id)` + `continue` |
| M5 | `answer.py` | no partial save / resume; Ctrl-C at q80 loses 80 answers | task.md H2/H3 |
| M6 | `augmentation.py` | no token budget | count tokens, drop lowest source while > ~1200 |
| M7 | `generation.py:21` | `-> Any` | `-> str` + `str(decode(...))` |

### Open — fix later (not blocking)
| # | Where | Bug | Fix idea |
|---|---|---|---|
| L1 | `index.py:18` | uses project `./.gitignore` (cwd-relative); `/data/*` could hide corpus dirs named `data` | corpus-relative / extension allow-list |
| L2 | `index.py:64` | `os.walk` unsorted → order differs per machine | sort `folder[:]` and `files` |
| L3 | `index.py:87` | syntax-error / non-UTF8 `.py` silently skipped | fall back to text chunker, count skips |
| L4 | `index.py:98` | tokenizer splits on `_`, drops 1-char (`top_p` → `top`), no whole snake identifier | also keep `[A-Za-z0-9_]+`; measure code recall |
| L5 | `utils.py:30` | empty file → zero-length chunk (`.gitkeep [0:0]`) | skip empty files |
| L6 | `index.py:122-138` | missing raw dir → empty `chunks.json`, bm25s crash | check `len(chunks) > 0` |
| L7 | `models.py:14` | `question_id` default random uuid → can't match truth | required in input models |
| L8 | `search.py` | `retrieve` reloads chunks + BM25 per call | `Retriever` class (needed for chat/API bonus) |
| L9 | `answer.py:26` | model reloaded per `answer` | one `Generator` (chat/API) |
| L10 | `augmentation.py:19,33` | label `[1]: path`, no "cite [n]", hardcoded "vLLM" | `[1] path`, cite rule, corpus name param |
| L11 | `evaluate.py` | `k` arg unused (always 1/3/5/10) | use or remove |
| L12 | Fire | 5000-word query → "Parser stack overflowed" | document |
| L13 | typos | `igonore waht breakk Clearify SOmthing "Erro form serach" retreved pipeLine` | one pass |
| L14 | root | `main.py test.py mini_docs.json .mini_docs.json` | `git rm` |
| L15 | `index.py:31-41,89-90` | dead / commented code | delete |
| L16 | `search.py:42` | `show_progress=True` bar mixes with first output line | `False` |

---

## 3. Speed (answer generation)

Machine here: i7-7600U 2C/4T, AVX2 only (no bf16 / AMX), no GPU, throttled ~1 GHz
(power-saver), busy. fp32 matmul 33 GFLOPS vs bf16 0.3 GFLOPS.

| config | prompt tok | prefill s | gen tok | total s |
|---|---|---|---|---|
| bf16 (old default), K=5 | – | – | – | > 10 min, never finished |
| fp32, K=5 | 2171 / 2447 | 54 / 76 | 25 / 73 | 66 / 127 |
| fp32, K=3 | 1257 / 1456 | 37 / 46 | 25 / 51 | 48 / 78 |
| fp32, K=2 | 1035 / 1094 | 30 / 31 | 25 / 53 | 41 / 68 |
| fp32, K=3 + 128 tok + "1-3 sentences" (= current code) | 1265 / 1464 | 41 / 44 | 21 / 30 | 52 / 72 |
| full CLI `answer` (current code) | | | | 172 (busy machine) |
| 4 threads / 1 thread | slower than 2 | | | |
| int8 dynamic quant | prefill 1.6–2x faster | | garbage | rejected |

Before a long run: charger in, `powerprofilesctl set performance`, close Chrome/docker.
Estimate at full clock: ~15–25 s / question → 50–80 min per 100 q. Subject: no time limit on
answers. Profiling script: `/tmp/claude-1000/-home-zak-Desktop-RaG/b00b9fab-6a3c-439e-961f-3f54ccb58ea8/scratchpad/perf/prof.py`
(env `DTYPE THREADS K MAXN NQ SHOW`).

---

## 4. Test runbook — part by part

### T1 lint
```sh
make lint
uv run flake8 . --exclude .venv,data,.git,__pycache__,.mypy_cache
```
Expect: `Success: no issues found`, flake8 silent.
Last: [ ] `search.py:16 F401` · [ ] `test.py:4 E703` (junk file).

### T2 Makefile rules
```sh
make -n install run debug clean lint
```
Expect: all parse; `lint` should read `flake8 .` / `mypy .` (subject). Last: [~] uses `src`.

### T3 index (writes `data/processed` — only when you mean it)
```sh
time uv run python -m src index --max_chunk_size 2000
uv run python -c "
import json, random
from src.utils import ft_open
c = json.load(open('data/processed/chunks.json'))
print('chunks', len(c), 'max', max(x['last_character_index']-x['first_character_index'] for x in c))
bad = [x for x in c if not x['file_path'].startswith('data/raw/')]
print('bad prefix', len(bad))
"
```
Expect: < 5 min (~7 s), 18738 chunks, max ≤ 2000, bad prefix 0. Last: [x].
Edge: `index --max_chunk_size 0` and `-5` → one line `max_size should be positive`, rc 1.

### T4 search, single query
```sh
uv run python -m src search "lora adapter" --k 3; echo rc=$?
uv run python -m src search PagedAttention --k 2; echo rc=$?
time uv run python -m src search "lora adapter" --k 1
uv run python -c "from src.search import retrieve; print(retrieve('lora adapter', k=2))"
```
Expect: exactly 3 / 2 lines `path [a:b]`, rc 0; ~1–2 s; list of `MinimalSource(...)`. Last: [x].

### T5 search edge cases
```sh
for q in '"a ?"' '""' '"!!!"'; do eval uv run python -m src search $q; echo rc=$?; done
uv run python -m src search lora --k 0; echo rc=$?
uv run python -m src search lora --k -1; echo rc=$?
uv run python -m src search lora --k 999999999 | wc -l
uv run python -m src search lora --save_directory nope; echo rc=$?
uv run python -m src search "comment configurer un adaptateur LoRA"; echo rc=$?
```
Expect: one `ERROR414: ...` line + rc 1 for empty/k≤0/missing index; huge k capped (no crash);
foreign-language query returns results, rc 0. Last: [x].

### T6 search_dataset
```sh
time uv run python -m src search_dataset --k 10 --save_directory /tmp/ragt/docs
time uv run python -m src search_dataset \
  --dataset_path data/datasets_public/public/UnansweredQuestions/dataset_code_public.json \
  --k 10 --save_directory /tmp/ragt/code
```
Expect: `Saved student_search_results to ...`, both together < 90 s. Last: [x] (~40 s).

### T7 evaluate (recall)
```sh
uv run python -m src evaluate --student_search_results_path /tmp/ragt/docs/dataset_docs_public.json
uv run python -m src evaluate --student_search_results_path /tmp/ragt/code/dataset_code_public.json \
  --dataset_path data/datasets_public/public/AnsweredQuestions/dataset_code_public.json
```
Expect: valid True; docs 0.540 / 0.760 / **0.830** / 0.880; code 0.354 / 0.566 / **0.657** / 0.697.
Last: [x]. **Any indexing/search change must keep these.**

### T8 answer, single query (slow: model)
```sh
time uv run python -m src answer "How to load a LoRA adapter dynamically?"
uv run python -m src answer "a ?"; echo rc=$?
uv run python -m src answer "lora" --k 0; echo rc=$?
uv run python -m src answer "Who won the 2022 World Cup?"
```
Expect: names `/v1/load_lora_adapter`; edge cases one line rc 1; off-topic → says sources don't
contain it. Last: [x] first three (172 s here); [ ] off-topic not tried.

### T9 dataset edge cases (search_dataset / answer_dataset / evaluate)
```sh
echo '{bad'                > /tmp/ragt/bad.json
echo '{"rag_questions":[]}' > /tmp/ragt/empty.json
echo '{"rag_questions":[{"question_id":"x1","question":"a ?"},{"question_id":"x2","question":"How to load a LoRA adapter?"}]}' > /tmp/ragt/degen.json
uv run python -m src search_dataset --dataset_path nope.json; echo rc=$?
uv run python -m src search_dataset --dataset_path /tmp/ragt/bad.json   --save_directory /tmp/ragt/o; echo rc=$?
uv run python -m src search_dataset --dataset_path /tmp/ragt/empty.json --save_directory /tmp/ragt/o; echo rc=$?
uv run python -m src search_dataset --dataset_path /tmp/ragt/degen.json --save_directory /tmp/ragt/o; echo rc=$?
python3 -c "import json;d=json.load(open('/tmp/ragt/o/degen.json'));print([(r['question_id'],len(r['retrieved_sources'])) for r in d['search_results']])"
uv run python -m src search_dataset --k 0; echo rc=$?
uv run python -m src evaluate --student_search_results_path nope.json; echo rc=$?
uv run python -m src evaluate --student_search_results_path /tmp/ragt/bad.json; echo rc=$?
uv run python -m src answer_dataset --student_search_results_path nope.json; echo rc=$?
uv run python -m src answer_dataset --k -1; echo rc=$?
```
Expect: missing/bad/k0 → one line rc 1; empty → valid file rc 0; degen → `[('x1', 0), ('x2', 10)]`.
Last: [x] all · [~] bad.json prints 3 lines (M2).

### T10 models / output validity
```sh
uv run python -c "
from src.models import StudentSearchResults as S
for p in ['/tmp/ragt/docs/dataset_docs_public.json','/tmp/ragt/code/dataset_code_public.json']:
    r = S.model_validate_json(open(p).read())
    print(p.split('/')[-1], len(r.search_results), 'k', r.k,
          'max', max(s.last_character_index-s.first_character_index for x in r.search_results for s in x.retrieved_sources))
"
```
Expect: 100 / 99 rows, k 10, max ≤ 2000. Last: [x].

### T10b answer_dataset mini run (3 questions, real model)
```sh
uv run python -c "
import json
d = json.load(open('/tmp/ragt/docs/dataset_docs_public.json')); d['search_results'] = d['search_results'][:3]
json.dump(d, open('/tmp/ragt/mini_docs.json', 'w'))"
time uv run python -m src answer_dataset --student_search_results_path /tmp/ragt/mini_docs.json --save_directory /tmp/ragt/ans
uv run python -c "
from src.models import StudentSearchResultsAndAnswer as A
r = A.model_validate_json(open('/tmp/ragt/ans/mini_docs.json').read())
print(len(r.search_results), all(x.answer for x in r.search_results), r.k)
for x in r.search_results: print('-', x.question, '\n ', x.answer[:200])"
```
Expect: `3 True 10`, answers on point. Last: [ ] not run. After H2/H3: Ctrl-C mid-run → valid partial file; rerun resumes.

### T11 moulinette (official — get binary from subject attachments, `chmod +x`)
```sh
./moulinette evaluate_student_search_results /tmp/ragt/docs/dataset_docs_public.json \
  data/datasets_public/public/AnsweredQuestions/dataset_docs_public.json --k 10 --max_context_length 2000
./moulinette evaluate_student_search_results /tmp/ragt/code/dataset_code_public.json \
  data/datasets_public/public/AnsweredQuestions/dataset_code_public.json --k 10 --max_context_length 2000
```
Expect: `Student data is valid: True`, docs R@5 ≥ 0.80, code ≥ 0.50. Last: [ ] never run.

### T12 subject walkthrough verbatim (after layout move to `data/datasets/`)
```sh
uv run python -m src index --max_chunk_size 2000
uv run python -m src search_dataset --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json --k 10 --save_directory data/output/search_results/UnansweredQuestions
./moulinette evaluate_student_search_results data/output/search_results/UnansweredQuestions/dataset_docs_public.json data/datasets/AnsweredQuestions/dataset_docs_public.json --k 10 --max_context_length 2000
uv run python -m src answer_dataset --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json --save_directory data/output/search_results_and_answer/UnansweredQuestions
```
Expect: each runs unchanged; last prints `Loaded 100 questions ... Processed 100 of 100 questions
Saved student_search_results_and_answer to ...`. Last: [ ].

### T13 chunker invariants (no write to data/)
```sh
uv run python -c "
import json, random
from src.utils import ft_open
c = json.load(open('data/processed/chunks.json'))
by = {}
for x in c: by.setdefault(x['file_path'], []).append((x['first_character_index'], x['last_character_index']))
gaps = 0
for p, r in random.sample(list(by.items()), 200):
    r.sort(); t = ft_open(p)
    if r[0][0] != 0 or r[-1][1] != len(t) or any(a[1] != b[0] for a, b in zip(r, r[1:])): gaps += 1
print('files with gap/overlap/uncovered:', gaps)"
```
Expect: 0. Last: [x].

---

## 5. Regression check — older fixes still holding (re-run after big changes)
- [x] silent corruption (slice path vs text) — T13 passes
- [x] `hard_split` infinite loop guard (`max_size ≤ 0` → ValueError)
- [x] tokenizer no doubled words: `tokenizer('hello world') == ['hello','world']`
- [x] one tqdm bar for chunking
- [x] chunk size 2000 (tiny-chunk IoU collapse)
- [x] search output not a literal f-string
- [x] output file named like input basename
- [x] evaluate: parse via `MoulinetteDataset`, compare `.file_path`, valid not inverted, labels aligned

---

## 6. Creative stress tests for the defense
- exact identifier `SamplingParams` → top-1 should be its definition file
- delete/rename `data/processed` → `search` gives one line "Index Not found", rc 1
- `index` twice → identical `chunks.json` (`cmp`) — determinism (L2)
- 50 MB one-line file in a copy of the corpus → hard split terminates
- Ctrl-C during `answer_dataset` → partial file kept (after H2)
- off-topic question → model says the sources don't contain it
- question in French / emoji only → no crash

---

## 7. README outline (chapter VIII)
1. `*This project has been created as part of the 42 curriculum by zhaouzan.*`
2. Description — RAG over vLLM 0.10.1, 4 stages
3. Instructions — uv, `make install`, data placement, `make run`, lint/clean/debug, moulinette
4. Resources + AI usage (which tasks, which parts, how verified)
5. System architecture — data flow + module map
6. Chunking strategy — AST nodes, decorators, recursion, gap keep, hard split, Markdown headings, 2000 cap, IoU 0.05
7. Retrieval method — own tokenizer (camel/snake split), BM25 k1=1.5 b=0.75, batched retrieve, keep/hits
8. Performance analysis — recall tables, chunk-size experiment, index / retrieval / answer times (§3)
9. Design decisions — offsets not text, own tokenizer, fp32 on CPU, k=3 for answers, greedy, `enable_thinking=False`
10. Challenges — silent corruption, hard_split loop, tiny-chunk IoU, bf16 on CPU, answer with zero context
11. Example usage — each command with sample output
