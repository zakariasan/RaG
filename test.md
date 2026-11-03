# test.md — manual test report

Run on 2026-11-03, working tree on top of `a8ae401` (your uncommitted fixes).
Every test: **command → expected → actual → status**. Copy the commands, run them,
compare with "Expected".

Status: ✅ pass · ❌ fail (fix needed) · ⚠️ works but not ideal

## Setup (run once in the repo root)

```bash
T=/tmp/ragtest; mkdir -p $T          # all test outputs go here, repo data untouched
M=./moulinette                        # path to the moulinette binary
D=data/datasets
P="uv run python -m src"
echo '{bad' > $T/bad.json             # malformed JSON
```

Rule for every error case: **one line message, rc = 1, no traceback**.
Check rc with `echo $?` right after the command.

---

## 0. Summary

Re-run (2nd pass) after your `retriever.scores` fix: sections 1–5 re-checked, sections 7–9
added (hard tests). Fix list with code: `task.md`.

| Area | Status |
|---|---|
| `make lint` | ✅ `Success: no issues found in 12 source files` |
| index (full corpus, single file, bad args) | ✅ |
| corpus integrity (coverage, ≤ 2000, paths) | ✅ |
| search | ✅ / ⚠️ `--k 100` refused, `--k 2.5` message |
| search_dataset | ✅ / ⚠️ `--k True` accepted, `--k abc` message |
| subject walkthrough verbatim + moulinette | ✅ docs 0.830 / code 0.657 |
| evaluate = moulinette | ✅ / ⚠️ `--k` ignored, mismatched truth → silent 0.000 |
| answer | ✅ / ⚠️ quality (section 9) |
| answer_dataset | ✅ / ⚠️ prints the whole list (bug 2) |
| token budget | ❌ k=99 → 41040 tokens > 40960 context (section 9) |

### Bugs found

1. ✅ ~~`src/search.py:86` `retrieve.scores`~~ — fixed (`retriever.scores`).
2. ⚠️ **`src/answer.py:112-115`** `f'Processed {question_ans} '` prints every MinimalAnswer.
   Fix: `{len(question_ans)}`.
3. ⚠️ **`src/search.py:67`** default `dataset_path` still `data/datasets_public/public/...`
   (folder moved). Fix: `'data/datasets/UnansweredQuestions/dataset_docs_public.json'`.
4. ⚠️ **`src/search.py:75`** `search_dataset --k 2.5` → `Partition index must be integer`.
   Use the same full check as `retrieve` (or `check_k`).
5. ⚠️ **`src/search.py:28-29`** `--k 100`, `--k 2.5`, `--k abc` all say `K must be positive.`
   → wrong message; `k >= 100` blocks a valid request.
6. ⚠️ `search 123` now runs (✅), `search "zzqxv"` returns random zero-score hits (no "no match").
7. ⚠️ `search lora --bogus 1` prints results **and** Fire help, rc 2.
8. ⚠️ typo `src/search.py:113` `ErroR form serach dataset`; labels `ERROR414` / `Error404`
   in `src/__main__.py:23,27`.

---

## 1. Lint

| # | Command | Expected | Actual | |
|---|---|---|---|---|
| 1.1 | `make lint; echo $?` | flake8 silent, mypy `Success`, rc 0 | `Success: no issues found in 12 source files`, rc 0 | ✅ |
| 1.2 | `make lint-strict; echo $?` | optional | 7 errors (missing stubs `fire`, `bm25s`, ...) rc 2 | ⚠️ optional |
| 1.3 | `uv lock --check` | lock matches pyproject | `Resolved 78 packages` rc 0 | ✅ |

---

## 2. Index

| # | Command | Expected | Actual | |
|---|---|---|---|---|
| 2.1 | `time $P index --save_dir $T/proc` | `Ingestion complete! Indexed N chunks`, < 300 s | 18737 chunks, 7.9 s | ✅ |
| 2.2 | `$P index --max_chunk_size 0 --save_dir $T/x` | error, rc 1 | `--max_chunk_size must be an integer in 1..2000` rc 1 | ✅ |
| 2.3 | `... --max_chunk_size 2001` | error, rc 1 | same message, rc 1 | ✅ |
| 2.4 | `... --max_chunk_size abc` | error, rc 1 | same message, rc 1 | ✅ |
| 2.5 | `$P index --files data/nope --save_dir $T/x` | error, rc 1 | `No indexable files found under data/nope` rc 1 | ✅ |
| 2.6 | `$P index --files data/raw/vllm-0.10.1/docs/features/lora.md --save_dir $T/one` | 1 file indexed | 8 chunks, path `data/raw/...` | ✅ |
| 2.7 | same with absolute path `$PWD/data/raw/.../lora.md --save_dir $T/one2` | stored relative | `"file_path": "data/raw/vllm-0.10.1/docs/features/lora.md"` | ✅ |

### 2.8 Corpus integrity (whole corpus)

```bash
uv run python - <<EOF
import json, collections, os
c = json.load(open('$T/proc/chunks.json'))
by = collections.defaultdict(list)
for x in c:
    by[x['file_path']].append((x['first_character_index'], x['last_character_index']))
bad = [f for f, l in by.items()
       if l[0][0] != 0
       or l[-1][1] != len(open(f, encoding='utf-8').read())
       or any(a[1] != b[0] for a, b in zip(l, l[1:]))
       or any(e <= s for s, e in l)]
print('files', len(by), 'chunks', len(c),
      'max', max(e - s for l in by.values() for s, e in l),
      'coverage errors', len(bad),
      'abs/./ paths', sum(os.path.isabs(f) or f.startswith('./') for f in by))
EOF
```

| Check | Expected | Actual | |
|---|---|---|---|
| max chunk size | ≤ 2000 | 2000 | ✅ |
| coverage: every file 0 → end, no gap, no overlap, no empty chunk | 0 errors | 0 (the `.gitkeep` `[0:0]` chunk is gone) | ✅ |
| paths exactly `data/raw/...` | 0 abs / `./` | 0 | ✅ |
| files | walked 2871 = 2692 indexed + 56 non-UTF-8 + 123 empty | 2692 | ✅ |
| `.py` syntax errors (skipped files) | — | 0 | ✅ |
| chunks per strategy | — | 15145 Python (AST), 3592 text (lines) | ✅ |

---

## 3. Search

| # | Command (`--save_directory $T/proc` on each) | Expected | Actual | |
|---|---|---|---|---|
| 3.1 | `$P search "How to configure LoRA?" --k 3` | 3 lines `path [s:e]` | `docs/features/lora.md [1884:3843]` + 2 | ✅ |
| 3.2 | `$P search ""` | error, rc 1 | `Empty query` rc 1 | ✅ |
| 3.3 | `$P search "?!?"` | error, rc 1 | `Empty query` rc 1 | ✅ |
| 3.4 | `$P search "zzqxv" --k 2` | no crash; ideally "no match" | 2 random hits, rc 0 | ⚠️ |
| 3.5 | `$P search 123 --k 2` | no crash | 2 hits, rc 0 | ✅ |
| 3.6 | `$P search lora --k 0` | error, rc 1 | `K must be positive.` rc 1 | ✅ |
| 3.7 | `$P search lora --k -1` | error, rc 1 | `K must be positive.` rc 1 | ✅ |
| 3.8 | `$P search lora --k 2.5` | `--k must be a positive integer` | `K must be positive.` | ⚠️ |
| 3.9 | `$P search lora --k abc` | `--k must be a positive integer` | `K must be positive.` | ⚠️ |
| 3.10 | `$P search lora --k 100` | 100 results | `K must be positive.` rc 1 | ⚠️ |
| 3.11 | `$P search lora --save_directory $T/nope` | error, rc 1 | `Index Not found.` rc 1 | ✅ |
| 3.12 | index cut to 50 chunks (see below) `--save_directory $T/cut` | error, rc 1 | `Index mismatch, re-run index` rc 1 | ✅ |
| 3.13 | `$P search lora --k 1 --bogus 1` | error before search | result **and** Fire help, rc 2 | ⚠️ |

Cut index for 3.12 / 4.7:
```bash
cp -r $T/proc $T/cut
uv run python -c "import json;c=json.load(open('$T/cut/chunks.json'));json.dump(c[:50],open('$T/cut/chunks.json','w'))"
```

---

## 4. search_dataset + moulinette + evaluate

```bash
for ds in docs code; do
  $P search_dataset --dataset_path $D/UnansweredQuestions/dataset_${ds}_public.json \
      --k 10 --save_directory $T/out --save_processed $T/proc
  $M evaluate_student_search_results $T/out/dataset_${ds}_public.json \
      $D/AnsweredQuestions/dataset_${ds}_public.json --k 10 --max_context_length 2000
  $P evaluate --student_search_results_path $T/out/dataset_${ds}_public.json \
      --dataset_path $D/AnsweredQuestions/dataset_${ds}_public.json
done
```

| # | Test | Expected | Actual | |
|---|---|---|---|---|
| 4.1 | search_dataset | `Saved student_search_results to ...` | saved, rc 0 | ✅ |
| 4.2 | moulinette docs | valid True, R@5 ≥ 0.80 | valid True, 100 q, R@1/3/5/10 0.540/0.760/**0.830**/0.880 | ✅ |
| 4.3 | moulinette code | valid True, R@5 ≥ 0.50 | valid True, 99 q, 0.354/0.566/**0.657**/0.697 | ✅ |
| 4.4 | own `evaluate` docs / code | same numbers as moulinette | identical | ✅ |
| 4.5 | `search_dataset --k 0 ...` | error, rc 1 | `--k must be positive.` rc 1 | ✅ |
| 4.6 | `search_dataset --k 2.5 ...` | `--k must be a positive integer` | `Partition index must be integer` rc 1 | ⚠️ |
| 4.7 | `--save_processed $T/cut` | `Index mismatch` | `Index Mismatch  re-run the index.` rc 1 | ✅ |
| 4.8 | `--dataset_path $T/nope.json` | error, rc 1 | `ErroR form serach dataset: [Errno 2] ...` rc 1 | ⚠️ typo |
| 4.9 | `--dataset_path $T/bad.json` | one line, rc 1 | 3-line pydantic message, rc 1 | ⚠️ |
| 4.10 | `$P evaluate --student_search_results_path $T/nope.json` | error, rc 1 | `[Errno 2] No such file ...` rc 1 | ✅ |
| 4.11 | `$P evaluate --student_search_results_path $T/bad.json` | error, rc 1 | pydantic message, rc 1 | ✅ |
| 4.12 | 200 questions time | ≤ 90 s | ~1 s | ✅ |

---

## 5. answer / answer_dataset (loads Qwen3-0.6B)

| # | Command | Expected | Actual | |
|---|---|---|---|---|
| 5.1 | `$P answer "What HTTP endpoint is used to dynamically load a LoRA adapter in vLLM?" --k 3 --index_dir $T/proc --save_directory $T/a1` | correct grounded answer + JSON saved | `/v1/load_lora_adapter`, file `student_search_result_and_answer.json`, 23 s | ✅ |
| 5.2 | `$P answer "" --index_dir $T/proc` | error, rc 1, before model load | `Empty query` rc 1 | ✅ |
| 5.3 | `$P answer lora --k 0 --index_dir $T/proc` | error, rc 1 | `K must be positive.` rc 1 | ✅ |
| 5.4 | `$P answer_dataset --k 0 ...` | error, rc 1 | `--k must be positive.` rc 1 | ✅ |
| 5.5 | `$P answer_dataset --student_search_results_path $T/nope.json` | error, rc 1 | `[Errno 2] ...` rc 1 | ✅ |
| 5.6 | 2 questions, 2nd has a missing source (below) | both answered, file saved, `k` = 2 | answer 1 correct, answer 2 `Could not read sources: ... nope.md`, `k=2`, saved | ✅ |
| 5.7 | final print of 5.6 | `Processed 2 of 2 questions` | prints the whole `MinimalAnswer` list | ⚠️ bug 2 |

File for 5.6:
```bash
uv run python - <<EOF
import json
d = json.load(open('$T/out/dataset_docs_public.json'))
d['search_results'] = d['search_results'][:2]
d['search_results'][1]['retrieved_sources'][0]['file_path'] = 'data/raw/nope.md'
json.dump(d, open('$T/two.json', 'w'))
EOF
$P answer_dataset --student_search_results_path $T/two.json --save_directory $T/a2 --k 2
```

---

## 7. Subject walkthrough VI.7.2 — verbatim, default paths

Run in an isolated copy (own `data/processed`, `data/output`; `data/raw` + `data/datasets`
linked), moulinette renamed to `./moulinette` as the subject says.

```bash
make run
for ds in docs code; do
  uv run python -m src search_dataset --dataset_path data/datasets/UnansweredQuestions/dataset_${ds}_public.json \
      --k 10 --save_directory data/output/search_results/UnansweredQuestions
  ./moulinette evaluate_student_search_results data/output/search_results/UnansweredQuestions/dataset_${ds}_public.json \
      data/datasets/AnsweredQuestions/dataset_${ds}_public.json --k 10 --max_context_length 2000
done
```

| # | Test | Expected | Actual | |
|---|---|---|---|---|
| 7.1 | `make run` | `Ingestion complete! ... under data/processed/` | 18737 chunks, 8.9 s | ✅ |
| 7.2 | step 2 docs / code | `Saved student_search_results to data/output/search_results/UnansweredQuestions/dataset_*.json` | same, 0.53 s each | ✅ |
| 7.3 | step 3 docs | valid True, R@5 ≥ 0.80 | valid True, **0.830** | ✅ |
| 7.4 | step 3 code | valid True, R@5 ≥ 0.50 | valid True, **0.657** | ✅ |
| 7.5 | `AnsweredQuestions/dataset_code_public.json` as input, `--save_directory .../AnsweredQuestions` | valid True | valid True, 0.657 | ✅ |
| 7.6 | `search_dataset` with **no args** | uses defaults, saves | `No such file ... data/datasets_public/...` rc 1 | ❌ default path `src/search.py:67` |
| 7.7 | `evaluate` with no args | uses defaults | 0.830 | ✅ |
| 7.8 | `--k 5` output, moulinette `--k 10` | valid, R@10 = R@5 | valid, R@10 0.830 | ✅ |
| 7.9 | `search_dataset --k 100000` | capped, no crash; `k` = requested | 18737 sources/q, file written, **`"k": 18737`** | ⚠️ `k` should be the requested value |

---

## 8. Hard tests — odd inputs a reviewer may try

Files used:
```bash
echo '{"rag_questions": []}' > $T/empty.json
echo '[]' > $T/list.json
echo '' > $T/blank.json
echo '{"search_results": [], "k": 10}' > $T/sr_empty.json
echo '{"rag_questions": [{"question": ""}, {"question": "???"}, {"question": "lora adapter"}]}' > $T/odd_q.json
python3 -c "print('{\"rag_questions\": [{\"question\": \"' + 'lora '*3000 + '\"}]}')" > $T/long_q.json
```

| # | Command | Expected | Actual | |
|---|---|---|---|---|
| 8.1 | `search_dataset --dataset_path $T/empty.json` | empty results file | saved, rc 0 | ✅ |
| 8.2 | `... $T/list.json` | error, rc 1 | pydantic `Input should be an object` rc 1 (3 lines) | ✅ / ⚠️ one line |
| 8.3 | `... $T/blank.json` | error, rc 1 | `Invalid JSON: EOF while parsing` rc 1 | ✅ |
| 8.4 | `... $T/odd_q.json` | `""` and `???` → 0 sources, `lora adapter` → 10 | `[0, 0, 10]` | ✅ |
| 8.5 | `... $T/long_q.json` (15000 chars in JSON) | works | saved, rc 0 | ✅ |
| 8.6 | `--dataset_path data/datasets` (a folder) | error, rc 1 | `[Errno 21] Is a directory` rc 1 | ✅ |
| 8.7 | `--save_directory $T/empty.json` (a file) | error, rc 1 | `[Errno 17] File exists` rc 1 | ✅ |
| 8.8 | `--save_directory /proc/x` | error, rc 1 | `[Errno 2]` rc 1 | ✅ |
| 8.9 | `search_dataset --k True` | refused | **accepted**, `"k": 1` | ⚠️ |
| 8.10 | `search_dataset --k abc` | `--k must be a positive integer` | `'<=' not supported between instances of 'str' and 'int'` | ⚠️ |
| 8.11 | `index --save_dir /proc/x` | error, rc 1 | `Cannot save and write Index: [Errno 2]` rc 1 | ✅ |
| 8.12 | `index --save_dir $T/empty.json` | error, rc 1 | `[Errno 17] File exists` rc 1 | ✅ |
| 8.13 | `index --files <empty dir>` | error, rc 1 | `No indexable files found` rc 1 | ✅ |
| 8.14 | `index --files <dir with 1 random binary>` | error, rc 1 | `No indexable files found` rc 1 | ✅ |
| 8.15 | `index --files <dir with broken .py>` | skipped | `No indexable files found` rc 1 | ✅ |
| 8.16 | `index --files .../vllm/__init__.py --max_chunk_size 1` | error or index | `No tokens produced (max_chunk_size too small?)` rc 1 | ✅ |
| 8.17 | `index --files .../vllm/envs.py --max_chunk_size 50` | all chunks ≤ 50 | 1436 chunks, max 50 | ✅ |
| 8.18 | `index --files ./data/raw/.../features` / `.../features/` | paths `data/raw/...` | `data/raw/vllm-0.10.1/docs/features/...` both | ✅ |
| 8.19 | `search "Comment configurer LoRA? 日本語 émoji 🚀" --k 2` | works | 2 LoRA hits | ✅ |
| 8.20 | `search "<'lora ' × 1500>"` | works or clear error | `Parser stack overflowed` rc 1 (Fire limit) | ⚠️ document |
| 8.21 | `search lora --k True` | `--k must be a positive integer` | `K must be positive.` rc 1 | ⚠️ message |
| 8.22 | `search` (no query) | error, rc 1 | `Empty query` rc 1 | ✅ |
| 8.23 | `search lora 3` (positional k) | 3 results | 3 results | ✅ |
| 8.24 | `search --help` | help, rc 0 | help, rc 0 | ✅ |
| 8.25 | `evaluate --student_search_results_path $T/sr_empty.json` | error, rc 1 | `empty truth, empty results or k <= 0` rc 1 | ✅ |
| 8.26 | `evaluate` docs results vs **code** truth | warn: no common question | silent `0.000` everywhere, rc 0 | ⚠️ |
| 8.27 | `evaluate --dataset_path` = an **Unanswered** file | error, rc 1 | pydantic `Field required` rc 1 | ✅ |
| 8.28 | `evaluate --k 0` / `--k abc` | refused | accepted, ignored | ⚠️ |
| 8.29 | `evaluate --max_context_length 10` | valid False | `Student data is valid: False`, then recall still printed | ✅ / ⚠️ note |
| 8.30 | `answer_dataset` on `$T/sr_empty.json` | `Processed 0 of 0` | `Processed [] of 0 questions` | ⚠️ bug 2 |
| 8.31 | `answer_dataset --k True` | refused | `--k must be positive.` rc 1 | ✅ |
| 8.32 | `foo` (unknown command) | error | Fire usage, rc 2 | ✅ |
| 8.33 | no command | list commands | help, rc 0 | ✅ |

Note 8.29: the `valid` line in `evaluate` only checks lengths, and recall is still computed
when it is False (the moulinette rejects the whole file). Rename it so it does not look like
the moulinette, or stop with an error (task T13).

---

## 9. Answer quality + token budget (real Qwen3-0.6B)

Script (run in repo root):
```bash
uv run python - <<'EOF'
import json
from src.search import retrieve
from src.augmentation import Augmentation
from src.generation import Generator
g = Generator(); a = Augmentation()
qs = ["What's the default value of trust_remote_code in vLLM's LLM class constructor?",
      "What is the capital of France?", "zzqxv blorp",
      "How do I enable prefix caching in vLLM?"]
for q in qs:
    a.read_sources(retrieve(q, 3, 'data/processed/'))
    print('Q:', q, '\nA:', g.generate(a.build_prompt(q)), '\n')
for k in (3, 10, 50, 99):
    a.read_sources(retrieve(qs[3], k, 'data/processed/'))
    text = g.tokenizer.apply_chat_template(a.build_prompt(qs[3]), tokenize=False,
                                           add_generation_prompt=True, enable_thinking=False)
    print(k, len(g.tokenizer(text)['input_ids']))
EOF
```

| # | Question | Expected | Actual | |
|---|---|---|---|---|
| 9.1 | default of `trust_remote_code` (code set, truth: `False`) | `False` | `True` | ❌ wrong |
| 9.2 | What is the capital of France? | "sources do not contain the answer" | `Paris` | ⚠️ not grounded |
| 9.3 | `zzqxv blorp` | "sources do not contain..." | "The provided code snippets do not contain any relevant information..." | ✅ |
| 9.4 | How do I enable prefix caching? (k=10) | `enable_prefix_caching=True` | `enable_prefix_caching=True` | ✅ |

| `--k` | prompt tokens (2 questions) | Qwen3-0.6B context 40960 | |
|---|---|---|---|
| 3 | 1039 – 1151 | fits | ✅ |
| 10 | 3625 – 4038 | fits | ✅ |
| 50 | 19293 – 20254 | fits | ✅ |
| 99 | 38258 – **41040** | **over** | ❌ no token budget (task T7) |

---

## 10. Static checks

| # | Check | Expected | Actual | |
|---|---|---|---|---|
| 10.1 | every function/class has a docstring (AST scan) | 0 missing | **14 missing** (`answer_dataset`, `Augmentation`, `Generator`, `chunk_nodes`, 10 models) | ❌ |
| 10.2 | docstrings document params/returns (subject V.1) | Args/Returns | 20 functions without | ⚠️ |
| 10.3 | files opened with `with` (context managers) | all | all (`ft_open` + `with open`) | ✅ |
| 10.4 | tqdm on long operations | index, search_dataset, answer_dataset | all three | ✅ |
| 10.5 | pydantic models = subject VI.4 | same fields | same + `Moulinette*` extras | ✅ |
| 10.6 | `.gitignore` excludes data, venv, caches | yes | `/data/*`, `.venv`, `__pycache__/` | ✅ |
| 10.7 | no large data / outputs committed | none | `en.subject.pdf` (1.6 MB) tracked; `.mini_docs.json` (empty) tracked | ⚠️ |

---

## 6. Not tested yet
- Full `answer_dataset` on 100 questions (~40 min) → `data/output/search_results_and_answer/`.
- Fresh `git clone` + `uv sync` on a clean machine.
- Hidden datasets (only public ones here).
