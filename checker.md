# checker.md — verification scripts per part

Copy-paste each block from the repo root. Every check prints `PASS` or `FAIL: <reason>`, so a
block is a go/no-go on one requirement. Cross-references are to `task.md` (C.x bugs, D.x tasks).

Run order mirrors the pipeline: `CHECK 1` upward. A failing early check makes later ones
meaningless — fix in order.

---

## CHECK 0 — one-shot smoke test

Fastest way to see where you stand. Runs the cheap checks only.

```bash
bash -c '
ok(){ echo "PASS  $1"; }; ko(){ echo "FAIL  $1"; }
python3 - <<PY || true
import tomllib, sys
d = tomllib.load(open("pyproject.toml","rb"))["project"]["dependencies"]
need = {"bm25s","pydantic","fire","tqdm"}
have = {x.split(">")[0].split("=")[0].split("[")[0].strip() for x in d}
miss = need - have
print(("FAIL  deps missing: " + ", ".join(sorted(miss))) if miss else "PASS  deps declared")
if "bm25" in have: print("FAIL  pyproject declares the bm25 shim (C.5)")
PY
for m in bm25s pydantic fire tqdm; do
  uv run python -c "import $m" 2>/dev/null && ok "import $m" || ko "import $m"
done
test -f src/models.py && ok "models.py exists" || ko "models.py missing"
test -f Makefile && ok "Makefile exists" || ko "Makefile missing (D.8)"
test -s README.md && ok "README non-empty" || ko "README empty (D.9)"
test -x ./moulinette && ok "moulinette present" || ko "moulinette missing (D.4)"
grep -qE "^/?data/?\*?$|^data/" .gitignore && ok "data/ ignored" || ko "data/ NOT ignored (C.7)"
'
```

---

## CHECK 1 — dependencies exact

`uv sync` is all the moulinette runs, so every import must be a declared dependency.

```bash
uv sync
uv run python - <<'PY'
import tomllib
decl = tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']
names = {d.split('>')[0].split('=')[0].split('[')[0].strip() for d in decl}
print('declared:', sorted(names))
bad = []
if 'bm25s' not in names: bad.append('bm25s not declared')
if 'bm25'  in names:     bad.append('bm25 shim declared but never imported (C.5)')
if 'pydantic' not in names: bad.append('pydantic not declared')
print('FAIL: ' + '; '.join(bad) if bad else 'PASS deps')
PY
```

---

## CHECK 2 — chunkers: coverage, size limit, degenerate input

The core correctness property: chunk slices must rebuild each file **exactly**, and no chunk may
exceed the limit. Runs over the real corpus.

```bash
uv run python - <<'PY'
import sys, random, glob; sys.argv=['x']
from src.python_file_chunker import chunk_pfile
from src.txt_file_chunker import chunk_txt_file
MAX = 2000
files = glob.glob('data/raw/**/*.py', recursive=True)
files = random.Random(0).sample(files, min(300, len(files)))
files += glob.glob('data/raw/**/*.md', recursive=True)[:100]
bad_cov = bad_size = errs = 0; n = 0
for f in files:
    try:
        src = open(f, encoding='utf-8').read()
        ch = chunk_pfile(f, MAX) if f.endswith('.py') else chunk_txt_file(f, MAX)
    except Exception as e:
        errs += 1; print('  ERR', f, type(e).__name__); continue
    n += len(ch)
    if ''.join(src[a:b] for a, b in ch) != src: bad_cov += 1; print('  COVERAGE', f)
    if any(b - a > MAX for a, b in ch):         bad_size += 1; print('  OVERSIZE', f)
print(f'files={len(files)} chunks={n} coverage_fail={bad_cov} oversize={bad_size} errors={errs}')
print('PASS chunkers' if not (bad_cov or bad_size) else 'FAIL chunkers')
PY
```

### 2b — `max_size <= 0` must not hang (C.1)

```bash
timeout 10 uv run python - <<'PY'; rc=$?
import sys; sys.argv=['x']
from src.utils import hard_split, get_offsets
t = "a\nb\nc\n"; offs = get_offsets(t.splitlines(keepends=True))
for bad in (0, -1):
    try:
        hard_split(0, len(t), offs, bad)
        print(f'FAIL hard_split({bad}) returned instead of raising')
    except ValueError:
        print(f'PASS hard_split({bad}) raises ValueError')
PY
[ $rc -eq 124 ] && echo "FAIL hard_split HANGS (C.1 unfixed)"
```

### 2c — chunker edge-case files

```bash
mkdir -p /tmp/chunk_edge && cd /tmp/chunk_edge
printf ''                > empty.py
printf 'x = 1'           > noeol.py
printf '\n\n\n'          > blank.py
printf 'def f():\n    return %s\n' "$(python3 -c 'print("1+"*800+"1")')" > longline.py
cd - >/dev/null
uv run python - <<'PY'
import sys; sys.argv=['x']
from src.python_file_chunker import chunk_pfile
for f in ['empty.py','noeol.py','blank.py','longline.py']:
    p = '/tmp/chunk_edge/' + f
    try:
        ch = chunk_pfile(p, 2000)
        src = open(p, encoding='utf-8').read()
        okc = ''.join(src[a:b] for a,b in ch) == src
        oks = all(b-a <= 2000 for a,b in ch)
        print(f'{"PASS" if okc and oks else "FAIL"} {f}: {len(ch)} chunks cover={okc} size={oks}')
    except Exception as e:
        print(f'FAIL {f}: {type(e).__name__}: {e}')
PY
```

---

## CHECK 3 — tokenizer

```bash
uv run python - <<'PY'
import sys; sys.argv=['x']
from src.index import tokenizer
cases = [
    ('def fused_batched_moe(self, LoRAConfig):',
     ['def','fused','batched','moe','self','loraconfig','lo','ra','config']),
    ('getHTTPResponseCode', ['gethttpresponsecode','get','http','response','code']),
    ('', []),
    ('a b cc 12 x9', ['cc','12','x9']),
]
fails = 0
for src, want in cases:
    got = tokenizer(src)
    if got != want:
        fails += 1; print('FAIL', repr(src), '\n  got ', got, '\n  want', want)
# no duplicates from single-part words
dup = tokenizer('def def')
if dup != ['def','def']: fails += 1; print('FAIL duplicate handling:', dup)
print('PASS tokenizer' if not fails else f'FAIL tokenizer ({fails})')
PY
```

---

## CHECK 4 — index artifacts and the parallel-list invariant

```bash
time uv run python -m src index --max_chunk_size 2000
ls -la data/processed/
uv run python - <<'PY'
import json, os, statistics
D = 'data/processed'
need = ['chunks.json','data.csc.index.npy','indices.csc.index.npy',
        'indptr.csc.index.npy','vocab.index.json','params.index.json']
miss = [f for f in need if not os.path.exists(os.path.join(D,f))]
print('FAIL missing: '+', '.join(miss) if miss else 'PASS all 6 index files present')

c = json.load(open(f'{D}/chunks.json'))
w = [x['last_character_index'] - x['first_character_index'] for x in c]
print(f'chunks={len(c)} files={len({x["file_path"] for x in c})} '
      f'width mean={statistics.mean(w):.0f} median={statistics.median(w)} max={max(w)}')
print('PASS width <= 2000' if max(w) <= 2000 else f'FAIL oversize chunk: {max(w)}')
print('PASS median width sane' if statistics.median(w) > 300
      else 'FAIL chunks far too small -> IoU floor will sink recall (C.9)')

keys = {'file_path','first_character_index','last_character_index'}
print('PASS field names' if all(keys <= set(x) for x in c[:50]) else 'FAIL field names')
pref = [x for x in c if not x['file_path'].startswith('data/raw/')]
print('PASS path prefix' if not pref else f'FAIL {len(pref)} paths not under data/raw/: {pref[0]}')

import bm25s
r = bm25s.BM25.load(D, mmap=False)
n = r.scores['num_docs'] if isinstance(getattr(r,'scores',None), dict) else None
print(f'bm25 num_docs={n} chunks.json={len(c)}',
      'PASS invariant' if n in (None, len(c)) else 'FAIL meta/index length mismatch')
PY
```

### 4b — no file silently dropped

```bash
uv run python - <<'PY'
import json, os
idx = {x['file_path'] for x in json.load(open('data/processed/chunks.json'))}
missing = []
for p, d, fs in os.walk('data/raw'):
    for f in fs:
        fp = os.path.join(p, f)
        if f.endswith(('.py','.md','.rst','.txt')) and fp not in idx and os.path.getsize(fp) > 0:
            missing.append(fp)
print(f'non-empty eligible files absent from index: {len(missing)}')
for m in missing[:10]: print('  ', m)
print('PASS no silent drops' if not missing else 'FAIL files vanished (check the except clause)')
PY
```

### 4c — indexing budget

```bash
/usr/bin/time -f '%e s  %M KB peak' uv run python -m src index --max_chunk_size 2000 2>&1 | tail -3
# PASS if under 300 s
```

---

## CHECK 5 — `search` CLI and edge cases

```bash
echo '--- normal (expect k lines "path [start:end]" with REAL numbers)'
uv run python -m src search "How to configure OpenAI server" --k 3
echo '--- empty query';   uv run python -m src search "" --k 3
echo '--- k=0';           uv run python -m src search "test" --k 0
echo '--- k negative';    uv run python -m src search "test" --k -5
echo '--- k huge';        uv run python -m src search "lora" --k 999999 | wc -l
echo '--- junk query';    uv run python -m src search "zzzqqq999" --k 2
echo '--- missing index'; uv run python -m src search "test" --save_dir /nonexistent
```

Automated version — catches the literal-f-string bug (C.2) and any traceback:

```bash
bash -c '
fail=0
out=$(uv run python -m src search "lora adapter" --k 3 2>&1)
echo "$out" | grep -q "first_character_index" && { echo "FAIL output prints a literal f-string (C.2)"; fail=1; }
echo "$out" | grep -qE "\[[0-9]+:[0-9]+\]$" && echo "PASS output format" || { echo "FAIL output format"; fail=1; }
for args in "\"\" --k 3" "test --k 0" "test --k -5" "test --save_dir /nonexistent"; do
  o=$(eval uv run python -m src search $args 2>&1)
  echo "$o" | grep -q "Traceback" && { echo "FAIL traceback on: $args"; fail=1; } || echo "PASS graceful: $args"
done
[ $fail -eq 0 ] && echo "PASS search" || echo "FAIL search"
'
```

---

## CHECK 6 — pydantic models (D.1)

```bash
uv run python - <<'PY'
import sys; sys.argv=['x']
need = ['MinimalSource','UnansweredQuestion','AnsweredQuestion','RagDataset',
        'MinimalSearchResults','MinimalAnswer','StudentSearchResults',
        'StudentSearchResultsAndAnswer']
try:
    import src.models as m
    from pydantic import BaseModel
except Exception as e:
    print(f'FAIL cannot import models: {type(e).__name__}: {e}'); sys.exit(0)
missing = [n for n in need if not hasattr(m, n)]
print('FAIL missing models: '+', '.join(missing) if missing else 'PASS all 8 models present')
notmodel = [n for n in need if hasattr(m,n) and not issubclass(getattr(m,n), BaseModel)]
print('FAIL not BaseModel: '+', '.join(notmodel) if notmodel else 'PASS all are pydantic')

if not missing:
    # auto question_id
    q = m.UnansweredQuestion(question='x')
    print('PASS question_id default' if len(q.question_id) > 10 else 'FAIL question_id default')
    # ground truth parses, extra fields tolerated
    raw = open('data/datasets/AnsweredQuestions/dataset_docs_public.json').read()
    ds = m.RagDataset.model_validate_json(raw)
    print(f'PASS ground truth parses ({len(ds.rag_questions)} questions)')
    # serialization shape
    j = m.StudentSearchResults(search_results=[], k=5).model_dump_json()
    print('PASS serialization' if j == '{"search_results":[],"k":5}' else f'FAIL serialization: {j}')
PY
```

---

## CHECK 7 — `search_dataset` output validity (D.2)

```bash
for SCOPE in UnansweredQuestions; do
for DS in dataset_docs_public dataset_code_public; do
  uv run python -m src search_dataset \
    --dataset_path data/datasets/$SCOPE/$DS.json \
    --k 10 --save_directory data/output/search_results/$SCOPE
done; done
ls -la data/output/search_results/UnansweredQuestions/
```

```bash
uv run python - <<'PY'
import json, glob, os
fails = 0
for p in sorted(glob.glob('data/output/search_results/*/*.json')):
    d = json.load(open(p))
    base = os.path.basename(p)
    src = f'data/datasets/UnansweredQuestions/{base}'
    nq = len(json.load(open(src))['rag_questions']) if os.path.exists(src) else None
    rows = d['search_results']
    issues = []
    if nq is not None and len(rows) != nq: issues.append(f'rows {len(rows)} != questions {nq}')
    if 'k' not in d: issues.append('missing k')
    for r in rows:
        if set(r) < {'question_id','question','retrieved_sources'}: issues.append('row fields'); break
        for s in r['retrieved_sources']:
            if set(s) != {'file_path','first_character_index','last_character_index'}:
                issues.append('source fields'); break
            if not s['file_path'].startswith('data/raw/'): issues.append('bad path prefix'); break
            if s['last_character_index'] - s['first_character_index'] > 2000:
                issues.append('source wider than 2000 -> whole run invalid'); break
    print(('FAIL ' if issues else 'PASS ') + base + (': ' + '; '.join(issues[:3]) if issues else
          f' rows={len(rows)} k={d["k"]} sources/row={len(rows[0]["retrieved_sources"]) if rows else 0}'))
    fails += bool(issues)
print('PASS search_dataset' if not fails else f'FAIL search_dataset ({fails} files)')
PY
```

### 7b — retrieval throughput budget (200 questions <= 90 s)

```bash
/usr/bin/time -f 'docs+code elapsed: %e s' bash -c '
for DS in dataset_docs_public dataset_code_public; do
  uv run python -m src search_dataset \
    --dataset_path data/datasets/UnansweredQuestions/$DS.json \
    --k 10 --save_directory data/output/search_results/UnansweredQuestions >/dev/null
done'
# 199 questions total. PASS if well under 90 s (process start-up included).
```

---

## CHECK 8 — recall@k, your own metric (D.3)

Independent of your `evaluate`, so it also validates `evaluate` itself.

```bash
uv run python - <<'PY'
import json, glob, os
def iou(a,b,c,d):
    i = max(0, min(b,d)-max(a,c)); u = max(b,d)-min(a,c)
    return i/u if u else 0.0
THRESH = {'docs': 0.80, 'code': 0.50}
for p in sorted(glob.glob('data/output/search_results/*/*.json')):
    base = os.path.basename(p)
    gt = f'data/datasets/AnsweredQuestions/{base}'
    if not os.path.exists(gt): print('skip (no ground truth)', base); continue
    truth = {q['question_id']: q['sources'] for q in json.load(open(gt))['rag_questions']}
    rows = json.load(open(p))['search_results']
    kind = 'docs' if 'docs' in base else 'code'
    line = [base]
    for k in (1,3,5,10):
        hit = 0
        for r in rows:
            for s in truth.get(r['question_id'], []):
                for g in r['retrieved_sources'][:k]:
                    if g['file_path'] == s['file_path'] and iou(
                        g['first_character_index'], g['last_character_index'],
                        s['first_character_index'], s['last_character_index']) >= 0.05:
                        hit += 1; break
                else: continue
                break
        r5 = hit/len(rows)
        line.append(f'R@{k}={r5:.3f}')
        if k == 5:
            verdict = 'PASS' if r5 >= THRESH[kind] else 'FAIL'
            line.append(f'[{verdict} vs {THRESH[kind]}]')
    print('  '.join(line))
PY
```

### 8b — your `evaluate` must agree

```bash
uv run python -m src evaluate \
  --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  --dataset_path data/datasets/AnsweredQuestions/dataset_docs_public.json
# PASS if the Recall@5 printed matches CHECK 8 for the same file.
```

### 8c — official scorer (D.4)

```bash
./moulinette evaluate_student_search_results \
  data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  data/datasets/AnsweredQuestions/dataset_docs_public.json \
  --k 10 --max_context_length 2000
# Require "Student data is valid: True" FIRST. Then Recall@5 >= 0.80 (docs) / 0.50 (code).
```

---

## CHECK 9 — answer generation (D.6)

```bash
uv run python -m src answer "What HTTP endpoint loads a LoRA adapter?" --k 5
uv run python -m src answer_dataset \
  --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  --save_directory data/output/search_results_and_answer/UnansweredQuestions
```

```bash
uv run python - <<'PY'
import json, glob, os
for p in sorted(glob.glob('data/output/search_results_and_answer/*/*.json')):
    d = json.load(open(p)); rows = d['search_results']
    empty = [r for r in rows if not r.get('answer','').strip()]
    nosrc = [r for r in rows if not r.get('retrieved_sources')]
    print(f'{os.path.basename(p)}: rows={len(rows)} empty_answers={len(empty)} no_sources={len(nosrc)}')
    print('  ' + ('PASS' if not empty and 'k' in d else 'FAIL answers missing or k absent'))
    if rows: print('  sample:', rows[0]['answer'][:160].replace('\n',' '))
PY
```

Grounding spot-check — read 3 answers next to their sources by hand. The subject grades
grounding, not fluency.

---

## CHECK 10 — lint, typing, docstrings (D.7)

```bash
uv run flake8 . --exclude=.venv,data,__pycache__ && echo "PASS flake8" || echo "FAIL flake8"
uv run mypy src --warn-return-any --warn-unused-ignores --ignore-missing-imports \
  --disallow-untyped-defs --check-untyped-defs && echo "PASS mypy" || echo "FAIL mypy"
uv run mypy src --strict 2>&1 | tail -3   # optional, lint-strict
```

```bash
uv run python - <<'PY'
import ast, glob
bad_hint = bad_doc = 0
for f in glob.glob('src/*.py'):
    t = ast.parse(open(f).read())
    for n in ast.walk(t):
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if n.returns is None or any(a.annotation is None for a in n.args.args):
                print(f'  no hints: {f}:{n.lineno} {n.name}'); bad_hint += 1
            if not ast.get_docstring(n):
                print(f'  no docstring: {f}:{n.lineno} {n.name}'); bad_doc += 1
print(f'{"PASS" if not bad_hint else "FAIL"} type hints ({bad_hint} missing)')
print(f'{"PASS" if not bad_doc else "FAIL"} docstrings ({bad_doc} missing)')
PY
```

### 10b — dead code (C.8)

```bash
for sym in skip_file skip_folder space; do
  n=$(grep -rn "\b$sym\b" src/*.py | wc -l)
  [ "$n" -eq 0 ] && echo "PASS $sym removed" || { echo "FAIL $sym still present:"; grep -rn "\b$sym\b" src/*.py; }
done
```

---

## CHECK 11 — Makefile (D.8)

```bash
for r in install run debug clean lint; do
  grep -qE "^$r:" Makefile && echo "PASS rule $r" || echo "FAIL rule $r missing"
done
make -n install run debug clean lint >/dev/null 2>&1 && echo "PASS all rules parse" || echo "FAIL a rule does not parse"
grep -E "^clean:" -A3 Makefile | grep -q "data" && echo "FAIL clean touches data/" || echo "PASS clean spares data/"
```

---

## CHECK 12 — layout, README, git hygiene

```bash
bash -c '
for p in src/__main__.py pyproject.toml uv.lock README.md Makefile \
         data/raw data/processed data/datasets/UnansweredQuestions data/datasets/AnsweredQuestions; do
  [ -e "$p" ] && echo "PASS  $p" || echo "FAIL  $p missing"
done
head -1 README.md | grep -qE "^\*.*42 curriculum.*\*$" && echo "PASS README first line" || echo "FAIL README first line (D.9)"
for s in "Description" "Instructions" "Resources" "architecture" "Chunking" "Retrieval" \
         "Performance" "Design" "Challenges" "Example"; do
  grep -qi "$s" README.md && echo "PASS  README mentions $s" || echo "FAIL  README missing $s"
done
grep -rn "data/raw\|data/processed" src/*.py | grep -v "=" | grep -q . \
  && echo "CHECK hardcoded paths above" || echo "PASS no bare hardcoded paths"
git status --porcelain | grep -q "^?? data/" && echo "FAIL data/ untracked and NOT ignored (C.7)" || echo "PASS data/ not staged"
git ls-files | grep -qE "^data/" && echo "FAIL data files are tracked in git" || echo "PASS no data in git"
'
```

---

## CHECK 13 — full pipeline, as the defense runs it

```bash
set -e
uv sync
uv run python -m src index --max_chunk_size 2000
uv run python -m src search_dataset \
  --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json \
  --k 10 --save_directory data/output/search_results/UnansweredQuestions
./moulinette evaluate_student_search_results \
  data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  data/datasets/AnsweredQuestions/dataset_docs_public.json \
  --k 10 --max_context_length 2000
uv run python -m src answer_dataset \
  --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
  --save_directory data/output/search_results_and_answer/UnansweredQuestions
echo "PIPELINE OK"
```

Repeat for `dataset_code_public.json`. Both must clear their threshold.

---

## CHECK 14 — chunk-size sweep for the README

Produces the Performance analysis table. Run once, near the end.

```bash
for S in 2000 1500 1000 500 250; do
  echo "=== max_chunk_size=$S"
  uv run python -m src index --max_chunk_size $S >/dev/null
  for DS in dataset_docs_public dataset_code_public; do
    uv run python -m src search_dataset \
      --dataset_path data/datasets/UnansweredQuestions/$DS.json \
      --k 10 --save_directory data/output/search_results/sweep_$S >/dev/null
  done
  # then run CHECK 8 against data/output/search_results/sweep_$S
done
uv run python -m src index --max_chunk_size 2000   # restore the good index
```

Expect recall to fall as the size shrinks, sharply below ~500, because of the IoU 0.05 floor.
Record the numbers — the subject asks for exactly this.

---

## Status board

Tick as each check passes.

| Check | What | Status |
|---|---|---|
| 0 | smoke | [ ] |
| 1 | dependencies exact | [ ] |
| 2 | chunkers: coverage / size / degenerate | [x] coverage+size · [ ] 2b guard |
| 3 | tokenizer | [x] |
| 4 | index artifacts + invariant + no drops | [x] (re-run after C.9) |
| 5 | search CLI + edges | [~] C.2 open |
| 6 | 8 pydantic models | [ ] |
| 7 | search_dataset output valid + throughput | [ ] |
| 8 | recall@k + evaluate agrees + moulinette | [ ] |
| 9 | answers generated and grounded | [ ] |
| 10 | flake8 / mypy / hints / docstrings / dead code | [ ] |
| 11 | Makefile rules | [ ] |
| 12 | layout / README / git hygiene | [ ] |
| 13 | full pipeline end to end | [ ] |
| 14 | chunk-size sweep recorded | [ ] |
