# task.md — what is left to do

Updated 2026-10-31 after: swarm review (5 agents) + **official moulinette run** on HEAD
`ae60ea3 Removing: markdown`. Done items were removed (history: `git log -p task.md`,
`completed.md`). Line numbers = HEAD.

## Where we are now (measured on HEAD)

| Part | State |
|---|---|
| index | OK: 18738 chunks, ≤ 2000 chars, exact offsets, full coverage, 7.3 s (limit 300 s) |
| search_dataset | OK: 200 questions in 1.1 s (limit 90 s), deterministic |
| **moulinette docs** | `Student data is valid: True`, R@1 0.540, R@3 0.760, **R@5 0.830** (need 0.80), R@10 0.880 |
| **moulinette code** | `Student data is valid: True`, R@1 0.354, R@3 0.566, **R@5 0.657** (need 0.50), R@10 0.697 |
| own `evaluate` | matches moulinette on public sets; wrong when questions are missing (see T10) |
| answer / answer_dataset | answers correct and grounded on 3/3 tested; ~31–60 s per question on CPU |
| markdown_chunker lib | removed in HEAD: good (it gave invalid offsets, 465 warnings, docs R@5 0.28) |
| `make lint` | **FAIL**: mypy `src/generation.py:46` |
| moulinette `evaluate_student_answers` | prints nothing, rc 0, even for a garbage file: cannot grade answers locally |

Moulinette rules confirmed by crafted files:
- one source of 2001 chars → `Student data is valid: False` (whole output rejected)
- paths with `./` prefix → R@5 0.000
- 50 of 100 questions answered → R@5 0.460 (missing questions count 0)
- zero-width source → still valid

Run it again after each retrieval change:

```bash
./moulinette evaluate_student_search_results \
    data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
    data/datasets/AnsweredQuestions/dataset_docs_public.json \
    --k 10 --max_context_length 2000
```

---

## Mandatory — in order

### T1 `[ ]` `make lint` green, with the subject's exact rule
- `src/generation.py:46` mypy union-attr. Fix = your commented lines 51-53:
  `answer = self.tokenizer.decode(...)`, `if not isinstance(answer, str): raise TypeError(...)`,
  `return answer.strip()`, signature `-> str`.
- Subject V.2: lint = `flake8 .` and `mypy .`. Today `mypy .` aborts
  (`Duplicate module named "utils"` from `data/raw`) and `flake8 .` crawls `.venv`.
  Add `.flake8` → `[flake8]` `exclude = .venv,.git,__pycache__,.mypy_cache,data`, and in
  `pyproject.toml` → `[tool.mypy]` `exclude = ['^data/', '^\.venv/']`.
- Makefile: `uv run flake8 .`, `uv run mypy . ...`; `debug: uv run python -m pdb -m src`
  (`pudb` is not on PATH outside the venv); add `.PHONY`.
- Commit the deletions of `test.py`, `test01.py` (already deleted in working tree);
  also `git rm main.py mini_docs.json .mini_docs.json` (`main.py` fails mypy, untyped).
- Check: `env -i PATH=/usr/bin:/bin:$HOME/.local/bin HOME=$HOME make lint` → rc 0.

### T2 `[ ]` `--max_chunk_size` must be 1..2000 integer — `src/index.py:117`
- `--max_chunk_size 999999` → rc 0, chunk of 22680 chars → moulinette **rejects everything**.
- `1` crashes (`max() iterable argument is empty`: 1-char tokens dropped); `abc`, `2.5`,
  `1e3`, `True` give cryptic errors.
  ```python
  if isinstance(max_chunk_size, bool) or not isinstance(max_chunk_size, int) \
          or not 0 < max_chunk_size <= 2000:
      raise ValueError("--max_chunk_size must be an integer in 1..2000")
  ```

### T3 `[ ]` Failed `index` must not break the existing index — `src/index.py:120-139`
- `chunks.json` is written (`:124`) before BM25 is built and saved (`:139`).
- `index --files /nonexistent` → `chunks.json` = `[]`, old BM25 files stay → `search` then
  prints **nothing, rc 0**. A partial run can leave chunks.json and BM25 with different
  sizes → silently wrong sources or `list index out of range`.
- `--files <single file>` fails the same way (`os.walk` on a file yields nothing).
- Fix: `if not chunk_meta: raise ValueError(...)`; `if not any(corpus_tokens): raise ...`;
  `retriever.save` first, write `chunks.json` last. In `search.py` after `BM25.load`:
  `if retriever.scores['num_docs'] != len(chunks): raise ValueError('Index mismatch, re-run index')`.

### T4 `[ ]` Normalize paths — `src/index.py:70`
- `index --files ./data/raw` → paths `./data/raw/...` → moulinette R@5 **0.000** (verified).
- `full_path = os.path.normpath(os.path.join(path, file))`.

### T5 `[ ]` `answer` — `src/answer.py:17-27`
- Index path hard-coded: `retrieve(query, k=k)` always reads `data/processed/`. Subject:
  "All input and output paths must be configurable". Add `save_directory` param, pass it on.
- Output is plain text. Subject VI.3: "produce structured JSON following the provided
  pydantic models" → print a `MinimalAnswer` (`question_id`, `question`,
  `retrieved_sources`, `answer`) with `model_dump_json(indent=4)`.

### T6 `[ ]` `answer_dataset` safe long runs — `src/answer.py:30-77`
- `os.makedirs(save_directory)` + path check only **after** the whole loop (`:69`): a bad
  save dir fails after ~1 h. Move before `Generator()`.
- No per-question `try/except`: one missing source file (`augmentation.py:18` `ft_open`)
  aborts everything. Catch `OSError` per question, store an error answer, continue.
- No partial save / resume, Ctrl-C loses all: save every 10 rows + in `finally`;
  resume from the existing output file (skip done `question_id`s).
- Subject VI.7.2 output shows `Processed 100 of 100 questions` → print it.
- Output `k` (`:67`) copies the search k (10) while only `--k 3` sources are used:
  decide and document.

### T7 `[ ]` Token budget — `src/augmentation.py`
- Subject VI.3: "within its token budget". Measured prompt tokens: k=3 ≈ 750–1600,
  k=50 ≈ 18–23k, k=200 ≈ 72–94k; Qwen3 limit 40960 → k ≥ ~100 overflows.
- Count tokens with the Qwen tokenizer per source; stop adding sources at a budget
  (e.g. 3000 tokens, keeps CPU time sane).

### T8 `[ ]` Fire argument types — `src/search.py:28-31` (+ `search_dataset`, `answer*`)
- `search 123`, `search True`, `search "[1,2]"` → `expected string or bytes-like object`.
- `--k 2.5` → `Partition index must be integer`; `--k abc` → `'<=' not supported...`.
  ```python
  if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
      raise ValueError('--k must be a positive integer')
  query = str(query)
  ```
- Unknown flag (`search lora --bogus 1`) runs the command fully, then rc 2. For
  `answer_dataset` = 1 h wasted. Optional: check `--flags` against
  `inspect.signature(cmd).parameters` before `fire.Fire`.

### T9 `[ ]` Real Markdown chunker — subject VI.1 "two distinct chunking strategies"
- Now `.md` uses the same line packing as any text file. Use structure instead:
  sections at ATX headings **outside code fences**, oversize sections cut at paragraph
  starts, `hard_split` fallback, greedy packing. Exact offsets, no library.
- Measured in scratch with **exactly this code** (2026-10-31): docs R@1/3/5/10 =
  0.63/0.81/**0.85**/0.87 (now 0.54/0.76/0.83/0.88), code R@5 0.667 (now 0.657),
  178 md files, 0 coverage errors, max chunk 2000. Goes in `src/txt_file_chunker.py`
  (`import re`), then `elif fil.endswith('.md'): pairs = chunk_md_file(src, max_size)`
  in `index_machine`.
  ```python
  HEADING = re.compile(r' {0,3}#{1,6}\s')
  FENCE = re.compile(r' {0,3}(```|~~~)')


  def pack(pieces: list[tuple[int, int]],
           max_size: int) -> list[tuple[int, int]]:
      """Merge neighbouring ranges while the merged range fits max_size."""
      out = [pieces[0]]
      for s, e in pieces[1:]:
          if e - out[-1][0] <= max_size:
              out[-1] = (out[-1][0], e)
          else:
              out.append((s, e))
      return out


  def chunk_md_file(src_file: str, max_size: int) -> list[tuple[int, int]]:
      """Chunk Markdown by sections (headings outside code fences).

      A section too big is cut at paragraph starts, then hard_split,
      then packed; finally neighbouring pieces are packed to max_size.
      """
      if not src_file:
          return []
      lines = src_file.splitlines(keepends=True)
      offsets = get_offsets(lines)
      heads = [0]
      paras: list[int] = []
      in_fence = False
      for i, line in enumerate(lines):
          if FENCE.match(line):
              in_fence = not in_fence
          elif not in_fence and i > 0:
              if HEADING.match(line):
                  heads.append(offsets[i])
              elif not lines[i - 1].strip():
                  paras.append(offsets[i])
      heads.append(len(src_file))
      pieces: list[tuple[int, int]] = []
      for s, e in zip(heads, heads[1:]):
          if e - s <= max_size:
              pieces.append((s, e))
              continue
          cuts = [s] + [p for p in paras if s < p < e] + [e]
          parts: list[tuple[int, int]] = []
          for a, b in zip(cuts, cuts[1:]):
              parts.extend(hard_split(a, b, offsets, max_size))
          pieces.extend(pack(parts, max_size))
      return pack(pieces, max_size)
  ```
- Check after: every chunk `0 <= s < e <= len`, contiguous, ≤ max; moulinette valid.

### T10 `[ ]` `evaluate` = moulinette — `src/evaluate.py:26-40`
- Divides by the student count, not the truth count: 50/100 questions → ours **0.920**,
  moulinette **0.460** (verified).
- Only `sources[0]` is scored; unknown id → raw `KeyError` (`ERROR414: 'zzz'`); `--k` unused.
  ```python
  got = {r.question_id: r.retrieved_sources for r in questions.search_results}
  total = 0.0
  for q in truth.values():
      srcs = got.get(q.question_id, [])[:k]
      found = sum(any(s.file_path == t.file_path and
                      iou(s.first_character_index, s.last_character_index,
                          t.first_character_index, t.last_character_index) >= 0.05
                      for s in srcs) for t in q.sources)
      total += found / len(q.sources) if q.sources else 0.0
  return total / len(truth)
  ```

### T11 `[ ]` Layout VI.7.1 + regenerate outputs
- Datasets are in `data/datasets_public/public/...`; subject layout is
  `data/datasets/{UnansweredQuestions,AnsweredQuestions}/`. Move them, update defaults in
  `search.py` and `evaluate.py`.
- `data/output/search_results/UnansweredQuestions/dataset_code_public.json` is still
  **k=5** → regenerate with `--k 10`.
- `data/output/search_results_and_answer/` does not exist yet → full `answer_dataset`
  on docs + code (long run, after T6).
- Run the VI.7.2 walkthrough commands verbatim.

### T12 `[ ]` Docstrings PEP 257 (subject V.1)
- Missing: `chunk_nodes` (`python_file_chunker.py:5`), `answer_dataset` (`answer.py:30`),
  classes `Augmentation`, `Generator`, all 11 models in `models.py`.
- Existing ones: one-liners, typos (`igonore`, `.gotignore`, `breakk`, `waht`, `Clearify`,
  `retreved`, `deppend`, `march of hard chunk`); add Args/Returns.

### T13 `[ ]` Error messages
- All errors to `sys.stderr`; one line for `ValidationError` (`e.errors()[0]['msg']`);
  drop `Error404`/`ERROR414` labels; fix `Erro form serach dataset`, `SOmthing`,
  `Extract Chunks probleme.`.
- `search "zzqxv"` prints random zero-score hits: optional "no match" message.
- Fire limit: ~1500-word query → `Parser stack overflowed` (document it).

### T14 `[ ]` Dead code
- `skip_file` / `skip_folder` (`index.py`), `g_checker` param (`evaluate.py`), `src_file`
  param of `chunk_nodes`, commented-out lines. `chunk_txt_file(filename)` now receives the
  content → rename the parameter.
- Empty non-`.py` file → `[0:0]` chunk (`.gitkeep`): return `[]` on empty text.

### T15 `[ ]` README sync (after the code changes)
- Options table misses `search --load_dir`, `search_dataset --saved_file`, `evaluate --k`;
  add `answer --save_directory` (T5). Pick one name for the index dir
  (`--save_dir` / `--save_directory` / `--save_processed` today).
- Update chunking section (T9) and recall tables after T9/T16.

---

## Recall — raise the margin (docs R@5 is only 0.03 above the bar)

### T16 `[ ]` Tokenizer — measured in scratch on public sets
| Variant | docs@5 | code@5 |
|---|---|---|
| current | 0.830 | 0.657 |
| + whole `snake_case` identifiers | 0.840 | 0.697 |
| + file name tokens in every chunk | 0.830 | 0.747 |
| **+ both + bm25s English stopwords** (re-verified) | **0.860** | **0.798** |
| full path tokens / other k1,b / chunk 1000–1500 / down-weight .json | worse or same | |

```python
from bm25s.stopwords import STOPWORDS_EN
STOP = set(STOPWORDS_EN)
# in tokenizer, before the final filter:
res += [w.lower() for w in re.findall(r'[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+', string)]
return [t for t in res if len(t) > 1 and t not in STOP]

def path_tokens(path: str) -> list[str]:
    """Tokens of the file name, added to every chunk of that file."""
    stem = os.path.splitext(os.path.basename(path))[0]
    return tokenizer(stem) + [stem.lower()]

# in index():
corpus_tokens = [tokenizer(t) + path_tokens(m.file_path)
                 for t, m in zip(txt, chunk_meta)]
```
Tuned on public sets only → expect a bit less on hidden ones. Re-run moulinette.

---

## Hypotheses (low risk, not proven)
- 4 corpus files use `\r\n`; `open()` translates newlines → offsets count translated
  text. None in public datasets.
- Indexer filters with the cwd `./.gitignore` matched on folder names (`data`, `build`,
  `dist`); no effect on vLLM 0.10.1, but depends on where you run it.
- `max_new_tokens=128` may cut long answers (none cut in 4 runs).

## Not tested yet
- Fresh `git clone` + `uv sync` on a disk with several GB free (`/tmp` too small here).
- Full `answer_dataset` on 100 questions (~1 h).

## Optional — tests (not graded)
`hard_split` bounds, `chunk_pfile` / md / txt coverage, tokenizer, index round-trip
(empty corpus writes nothing, `./` normalized), `retrieve` edge cases, `search_dataset`
output model, `evaluate` multi-source + missing questions, CLI no-traceback (subprocess),
`answer_dataset` with mocked `Generator`.

---

# Bonus — only after everything above (subject IX)

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

