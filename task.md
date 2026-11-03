# task.md — what is left to do

Updated 2026-11-03 (4th pass) on the working tree over `a8ae401` (your uncommitted fixes).
Re-tested in an isolated copy: `make lint`, `make lint-strict`, `make run`, subject VI.7.2
walkthrough **verbatim**, moulinette, ~60 odd-input cases, answer quality with the real model,
prompt token sizes. Full commands + results: `test.md`. Every fix = **file:line on the working tree**.

## Where we are now

| Part | State |
|---|---|
| `make lint` (subject flags, `flake8 .` / `mypy .`) | ✅ `Success: no issues found in 12 source files` |
| `make lint-strict` (optional) | ⚠️ 7 errors (missing stubs `fire`, `bm25s`...) — optional, not graded |
| `uv lock --check` | ✅ lock matches `pyproject.toml` |
| `make run` (index) | ✅ 18737 chunks, ~9 s (limit 300 s) |
| corpus integrity | ✅ 2871 walked / 2692 indexed, max 2000, 0 gaps/overlaps, paths `data/raw/...` |
| walkthrough step 2 `search_dataset` | ✅ docs + code, ~0.5 s each (limit 90 s / 200 q) |
| walkthrough step 3 moulinette | ✅ valid True, docs R@5 **0.830** (≥ 0.80), code R@5 **0.657** (≥ 0.50) |
| `AnsweredQuestions` scope as input | ✅ valid True, same recall |
| own `evaluate` | ✅ = moulinette |
| `answer` | ✅ 23 s, JSON saved |
| `answer_dataset` | ✅ missing source handled / ⚠️ print (T6) |
| answer quality | ⚠️ 1 wrong answer on a code question, answers out-of-scope questions (T17) |
| token budget | ❌ `answer --k 99` → **41040 prompt tokens > 40960** Qwen3 context (T7) |
| docstrings | ❌ 14 missing, 20 without Args/Returns (T12) |

Moulinette facts (crafted files, earlier passes — still true):
- one source of 2001 chars → `Student data is valid: False` (whole output rejected)
- paths with `./` → R@5 0.000; missing questions count as 0
- a question id **not in the truth file → moulinette crashes** (`KeyError`): never rename ids
- `evaluate_student_answers` prints nothing, rc 0, even for garbage: answers can't be graded locally

Done since last pass (verified): `evaluate.py:63` syntax error, `search_dataset` index mismatch
check (`retriever.scores`), `query = str(query)`, Makefile `flake8 .` / `mypy .` + `.flake8` +
`[tool.mypy] exclude`, `main.py` / `mini_docs.json` removed, `generation.py` returns `str`,
single-file index stored relative, empty file → no chunk, `Cannot` typo, datasets moved to
`data/datasets/`, evaluate default path.

---

## Mandatory — in order

### T6 `[~]` `answer_dataset` — print + safe long runs — `src/answer.py`
- **`:112-115`** prints the whole list (`Processed [MinimalAnswer(...)...] of 2 questions`):
  ```python
      print(
          f'Processed {len(question_ans)} '
          f'of {len(questions.search_results)} questions'
      )
  ```
- No partial save; Ctrl-C after 40 min loses all. Compute `path` before the loop and save every
  10 answers + in `finally:`:
  ```python
      def save(rows: list[MinimalAnswer]) -> None:
          """Write the answers done so far to path."""
          out = StudentSearchResultsAndAnswer(search_results=rows, k=k)
          with open(path, 'w', encoding='utf-8') as f:
              f.write(out.model_dump_json(indent=4))

      try:
          for question in tqdm(...):
              ...
              if len(question_ans) % 10 == 0:
                  save(question_ans)
      finally:
          save(question_ans)
  ```
- `retrieved_sources` keeps all 10 sources while only `--k 3` are used. Either store
  `question.retrieved_sources[:k]` or say it in the README (currently: README says `k` = sources
  per prompt).

### T7 `[ ]` Token budget — subject VI.3 "within its token budget" — **measured now**
| `--k` | prompt tokens (2 questions) |
|---|---|
| 3 | 1039 – 1151 |
| 10 | 3625 – 4038 |
| 50 | 19293 – 20254 |
| 99 | 38258 – **41040** ← over Qwen3-0.6B `max_position_embeddings` 40960 |

`src/search.py:28` refuses `k >= 100`, which is not a budget and also blocks `search --k 100`.
Fix: budget in `src/augmentation.py:12` `read_sources`, stop adding sources when full:
```python
    def read_sources(
        self,
        sources: list[MinimalSource],
        tokenizer: Callable[[str], Any] | None = None,
        budget: int = 6000
    ) -> None:
        """Read the text of each source into the prompt context.

        Args:
            sources: retrieved source locations, best first.
            tokenizer: Qwen tokenizer; when given, stop before `budget` tokens.
            budget: max tokens of context.
        """
        context = ''
        used = 0
        for i, elem in enumerate(sources):
            if elem.file_path not in self.cache:
                self.cache[elem.file_path] = ft_open(elem.file_path)
            part = (f'[{i + 1}]: {elem.file_path}\n'
                    + self.cache[elem.file_path][
                        elem.first_character_index:elem.last_character_index]
                    + '\n')
            if tokenizer is not None:
                n = len(tokenizer(part)['input_ids'])
                if used + n > budget:
                    break
                used += n
            context += part
        self._context = context
```
`answer.py` (both functions): `a.read_sources(sources, g.tokenizer)` — create `g = Generator()`
**before** `read_sources`. Then remove `or k >= 100` at `src/search.py:28`.
Check: `answer "How do I enable prefix caching in vLLM?" --k 200` works, prompt ≤ budget.

### T8 `[~]` k checks — one helper — `src/utils.py` + 4 call sites
Still wrong (tested):
| Command | Now | Expected |
|---|---|---|
| `search lora --k 2.5` / `--k abc` / `--k True` | `K must be positive.` | `--k must be a positive integer` |
| `search_dataset --k 2.5` | `Partition index must be integer` | same message |
| `search_dataset --k abc` | `'<=' not supported between instances of 'str' and 'int'` | same message |
| `search_dataset --k True` | **accepted**, writes `"k": 1` | refused |
| `evaluate --k abc` / `--k 0` | accepted, ignored | refused (or remove `--k`) |

```python
def check_k(k: object) -> int:
    """Validate a --k argument.

    Args:
        k: value given on the command line.

    Returns:
        k, when it is a positive int.

    Raises:
        ValueError: if k is a bool, not an int, or <= 0.
    """
    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError('--k must be a positive integer')
    return k
```
Use at `src/search.py:28-29`, `src/search.py:75-76`, `src/answer.py:68-69`, and at the top of
`evaluate()` (`src/evaluate.py:66`).
- `search_dataset --k 100000` writes `"k": 18737` (capped). Subject VI.5: `k` = "number of
  results requested" → keep the requested value: `out = StudentSearchResults(..., k=requested_k)`
  (save it before `k = min(k, len(chunks))` at `src/search.py:80`).

### T11 `[~]` Layout + default paths
- **`src/search.py:67`** default still `data/datasets_public/public/...` →
  `search_dataset` with no args fails. Fix:
  `'data/datasets/UnansweredQuestions/dataset_docs_public.json'`
- Regenerate the repo outputs (not committed, `/data/*` is gitignored, but needed for the demo):
  ```bash
  for ds in docs code; do
    uv run python -m src search_dataset --dataset_path data/datasets/UnansweredQuestions/dataset_${ds}_public.json \
        --k 10 --save_directory data/output/search_results/UnansweredQuestions
  done
  ```
- Full `answer_dataset` on docs + code (~40 min each, after T6) →
  `data/output/search_results_and_answer/UnansweredQuestions/`.

### T12 `[ ]` Docstrings PEP 257 (subject V.1) — AST scan on the working tree
- **Missing (14):** `answer_dataset` (`answer.py:60`), `Augmentation` (`augmentation.py:6`),
  `Generator` (`generation.py:7`), `chunk_nodes` (`python_file_chunker.py:5`), all 10 models in
  `models.py:7-56` (`MinimalSource`, `UnansweredQuestion`, `AnsweredQuestion`, `RagDataset`,
  `MinimalSearchResults`, `MinimalAnswer`, `StudentSearchResults`,
  `StudentSearchResultsAndAnswer`, `MoulinetteAnsweredQuestion`, `MoulinetteDataset`).
- **No Args/Returns (20):** every other function. Subject: "document purpose, parameters, and
  returns". Google style:
  ```python
  def hard_split(s: int, e: int, line_offsets: list[int],
                 max_size: int) -> list[tuple[int, int]]:
      """Split [s, e) into ranges of at most max_size characters.

      Cuts at line starts when possible, else hard at max_size.

      Args:
          s: start offset (inclusive).
          e: end offset (exclusive).
          line_offsets: start offset of every line of the file.
          max_size: max characters per range.

      Returns:
          Contiguous (start, end) ranges covering [s, e).

      Raises:
          ValueError: if max_size <= 0.
      """
  ```
  Models: one line is enough, e.g. `"""One retrieved span: file path + character range."""`.
- Typos in existing docstrings: `igonore`, `breakk`, `waht`, `Clearify`, `retreved`, `deppend`,
  `Check your answer protocol` (evaluate).

### T13 `[ ]` Error messages
- `src/__main__.py:23,27,31`: drop `Error404` / `ERROR414` / `-_-!`, print to `sys.stderr`,
  one line for pydantic (now 3 lines + URL):
  ```python
      except ValidationError as e:
          err = e.errors()[0]
          print(f"Error: invalid JSON: {err['msg']} at {err['loc']}", file=sys.stderr)
          sys.exit(1)
      except Exception as e:
          print(f"Error: {e}", file=sys.stderr)
          sys.exit(1)
      except KeyboardInterrupt:
          print('Interrupted', file=sys.stderr)
          sys.exit(130)
  ```
- `src/search.py:113` `ErroR form serach dataset` → `Cannot run search_dataset`.
- `evaluate` with docs results vs code truth → silently `0.000`. Add after `truth = ...`
  (`src/evaluate.py:86`):
  ```python
      common = sum(r.question_id in truth for r in questions.search_results)
      if common == 0:
          raise ValueError('No question id in common with the ground truth')
  ```
- `src/evaluate.py:78` prints `Student data is valid` but only checks length → rename to
  `Sources within max_context_length: ...` (do not look like the moulinette).
- Known limits (document, don't fix): query ≥ ~1500 words → Fire `Parser stack overflowed`;
  `search "zzqxv"` returns zero-score hits; unknown flag (`--bogus 1`) runs then rc 2.

### T14 `[ ]` Dead code
- `src/index.py:31-41` (`skip_file`, `skip_folder`), `:91-92`, `:134`.
- `src/evaluate.py:8`, `:28`, `:44-52`; `g_checker` param of `recalling` (`:20`, unused).
- `src/generation.py:33-34`, `src/search.py:99`, `src/txt_file_chunker.py:8-9`,
  `src/python_file_chunker.py:57-58`.
- `chunk_nodes(..., src_file, ...)` unused param; `chunk_txt_file(filename)` receives the
  **content** → rename to `text`.
- `.mini_docs.json` (empty, still tracked) → `git rm .mini_docs.json`.

### T17 `[ ]` Answer quality / prompt strategy (subject VI.3: grounding, prompt strategy)
Measured with the real model:
| Question | Answer | |
|---|---|---|
| default of `trust_remote_code` in `LLM` (code set) | `True` — truth `False` | ❌ wrong |
| What is the capital of France? | `Paris` — not from sources | ⚠️ not grounded |
| `zzqxv blorp` | "sources do not contain..." | ✅ |
| How do I enable prefix caching? (k=10) | `enable_prefix_caching=True` | ✅ |

Prompt improvement in `src/augmentation.py:28-41` (cheap, no code change elsewhere):
```python
'content': (
    'You answer questions about the vLLM codebase using ONLY the numbered '
    'sources. Quote exact names and values from the sources. If the sources '
    'do not contain the answer, reply exactly: "The sources do not contain '
    'the answer." Do not use outside knowledge. Answer in 1-3 sentences.')
```
and put the question **before and after** the context (small models forget the start):
`f'Question: {query}\n\nSources:\n{self._context}\nQuestion: {query}\nAnswer:'`.
Re-run the 4 questions above; record before/after in README "Challenges".

### T15 `[~]` README sync (done this pass; redo after T6–T17)
- After T7: add the token budget to "Design decisions" and the k=99 table row.
- After T17: update "Prompt" bullet.
- After T16: recall tables.

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

## Defense prep (not code)
- "Why is your Markdown chunker not Markdown-specific?" → line packing keeps lines/code blocks
  whole; heading splitter tried and removed (README says so).
- Recode practice (subject X.1, few minutes): change default k, add a field to `MinimalAnswer`
  (e.g. `model: str = 'Qwen/Qwen3-0.6B'`), print scores next to `search` results, change
  `max_new_tokens`. Know where each lives.
- Fresh `git clone` + `uv sync` on a machine with several GB free (not done: `/tmp` here 1.7 GB).
- Optional (not graded, subject V.3): pytest for `hard_split`, chunk coverage, tokenizer,
  `check_k`, CLI no-traceback (subprocess). The cases in `test.md` are ready-made test inputs.

## Hypotheses (low risk, not proven)
- 4 corpus files use `\r\n`; `open()` translates newlines → offsets count translated text.
  None in public datasets.
- Indexer filters with the cwd `./.gitignore` matched on names (`data`, `build`, `dist`);
  no effect on vLLM 0.10.1, but depends on where you run it.
- `max_new_tokens=128` may cut long answers (none cut in tests).

---

# Bonus — only after **everything** above (subject IX)

Graded only if the mandatory part validates fully **and** the reviewer cannot break it.
Each bonus = 1 point, must **run** on a CPU-only machine, flake8 + mypy apply to bonus files.
Recommended order: **I4 → I1 → I2 → I5 → I3** (cheapest first; I2 needs I1).

## I1 `[ ]` Bonus 1 — Semantic embeddings

**Idea:** BM25 matches **words**; embeddings match **meaning** ("load adapter" ≈ "register
LoRA"). Each chunk → vector of 384 numbers; the question too; nearest vectors = similar.

| Step | How |
|---|---|
| I1.1 | `uv add sentence-transformers` (reuses the torch you have) |
| I1.2 | new `src/semantic.py`: `model = SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2', device='cpu')` |
| I1.3 | in `index()` after chunking, behind a flag `--semantic True`: `emb = model.encode(txt, batch_size=64, show_progress_bar=True, normalize_embeddings=True, convert_to_numpy=True).astype('float32')` |
| I1.4 | `np.save(os.path.join(save_dir, 'embeddings.npy'), emb)` — **row i = chunk i** (same order as `chunks.json` and BM25) |
| I1.5 | `retrieve_semantic(query, k, save_dir)`: `emb = np.load(..., mmap_mode='r')`; `q = model.encode([query], normalize_embeddings=True)[0]`; `scores = emb @ q`; `top = np.argpartition(-scores, k)[:k]`; sort `top` by score; return `MinimalSource(**chunks[i])` |
| I1.6 | flag `--method bm25\|semantic\|hybrid` (default `bm25`) on `search`, `search_dataset`, `answer` |
| I1.7 | `search_dataset`: encode all questions in **one** `model.encode(list_of_questions)` call (speed) |
| I1.8 | measure: index time, `search_dataset` time, moulinette R@1/3/5/10 docs + code; table in README |

```python
def retrieve_semantic(query: str, k: int, save_dir: str) -> list[int]:
    """Return the ids of the k chunks closest to query (cosine)."""
    emb = np.load(os.path.join(save_dir, 'embeddings.npy'), mmap_mode='r')
    q = get_model().encode([query], normalize_embeddings=True)[0]
    scores = emb @ q
    top = np.argpartition(-scores, min(k, len(scores) - 1))[:k]
    return [int(i) for i in top[np.argsort(-scores[top])]]
```
**Watch out:** 18737 chunks on this i7-7600U ≈ several minutes → check `index --semantic True`
stays **< 5 min** total; if not, embed only `.py/.md/.rst/.txt` and give other chunks a zero
vector. MiniLM truncates at 256 word pieces → a 2000-char chunk is partly cut (say it in README).
Lazy-import `sentence_transformers` (like torch) so `search` with BM25 stays fast.
**Expect:** better on paraphrased docs questions, worse on exact identifiers.

## I2 `[ ]` Bonus 2 — Hybrid retrieval (needs I1)

**Idea:** merge both rankings with **Reciprocal Rank Fusion** — uses only ranks, so BM25
scores (0–30) and cosine (0–1) never need to be compared.

| Step | How |
|---|---|
| I2.1 | top 50 ids from BM25 (`retriever.retrieve(..., k=50)`) and top 50 from `retrieve_semantic` |
| I2.2 | `score[id] += 1 / (60 + rank)` for each list (rank from 1; 60 = standard constant) |
| I2.3 | sort ids by fused score, keep k → `MinimalSource` |
| I2.4 | `--method hybrid`; moulinette table BM25 vs semantic vs hybrid (docs + code) |

```python
def rrf(rankings: list[list[int]], k: int, c: int = 60) -> list[int]:
    """Fuse several ranked id lists with Reciprocal Rank Fusion."""
    score: dict[int, float] = {}
    for ranking in rankings:
        for rank, doc in enumerate(ranking, start=1):
            score[doc] = score.get(doc, 0.0) + 1.0 / (c + rank)
    return sorted(score, key=lambda d: score[d], reverse=True)[:k]
```
**Accept when:** hybrid R@5 ≥ the best single method on at least one dataset. If not, keep it
as an option and report the numbers honestly. Optional: weight BM25 ×2 for code questions.

## I3 `[ ]` Bonus 3 — Incremental indexing

**Idea:** a changed file re-indexes only that file.

| Step | How |
|---|---|
| I3.1 | `sorted()` folders and files in `index_machine` (`folder.sort()`, `sorted(files)`) → stable order |
| I3.2 | save `manifest.json` in `save_dir`: `{path: {"mtime": st.st_mtime, "size": st.st_size, "sha1": ..., "first": id, "count": n}}` |
| I3.3 | also save `tokens.json` (token list per chunk) — tokenizing is the slow part |
| I3.4 | `index --incremental True`: walk, compare with manifest → `added`, `changed` (mtime/size differ **and** sha1 differs), `deleted` |
| I3.5 | keep chunks + tokens of unchanged files; re-chunk + re-tokenize only `added + changed`; drop `deleted` |
| I3.6 | **rebuild BM25** from all token lists (`bm25s` cannot patch in place; build is fast) |
| I3.7 | rewrite `chunks.json`, BM25, `tokens.json`, `embeddings.npy` (if I1: re-encode only new chunks, reuse old rows) **in the same order** |
| I3.8 | print `Re-indexed <n> files, kept <m>, removed <d>` |

**Accept when:** `touch` + edit one file → incremental run re-chunks 1 file, much faster than a
full index, and the moulinette gives the **same** numbers as a full rebuild.
**Watch out:** the parallel-list invariant (chunk i = BM25 doc i = embedding row i) — this is
where it breaks silently; add a check `len(chunks) == num_docs == len(emb)` after saving.
No manifest → fall back to a full index.

## I4 `[ ]` Bonus 4 — Caching (cheapest, do first)

| Step | How |
|---|---|
| I4.1 | measure cold start now: time to load `chunks.json` + BM25, and the model |
| I4.2 | index cache: module-level `_INDEX: dict[str, tuple[BM25, list[dict]]]` keyed by `save_dir`, filled once by `load_index(save_dir)`; `retrieve` and `search_dataset` use it; `bm25s.BM25.load(save_dir, mmap=True)` |
| I4.3 | query cache in memory: `@functools.lru_cache(maxsize=1024)` on `_retrieve_ids(query: str, k: int, save_dir: str) -> tuple[int, ...]` (**tuple**: lists are unhashable/mutable) |
| I4.4 | query cache on disk: `data/cache/search.json` `{sha1(query + k + index_mtime): [ids]}` → second CLI run is instant |
| I4.5 | answer cache on disk: `data/cache/answers.json` keyed by `sha1(question + source ids + model name + PROMPT_VERSION)` |
| I4.6 | `--no_cache True` flag to bypass; `make clean` removes `data/cache` |
| I4.7 | measure first vs second call (search + answer), table in README |

**Watch out:** the key must change when the index or the prompt changes (index mtime,
`PROMPT_VERSION = 2` constant), or stale answers come back. Write the cache file atomically
(`tmp` + `os.replace`).

## I5 `[ ]` Bonus 5 — Local HTTP API

| Step | How |
|---|---|
| I5.1 | `uv add fastapi uvicorn` |
| I5.2 | `src/api.py`: `app = FastAPI()`; load index (I4 cache) at startup; load `Generator` **lazily** on first `/answer` |
| I5.3 | `GET /search?q=...&k=5` → `list[MinimalSource]` (pydantic serializes directly) |
| I5.4 | `POST /answer` body model `AskRequest(question: str, k: int = 3)` → `MinimalAnswer` |
| I5.5 | errors → HTTP 400 with the message (empty query, bad k), 404 if no index; never a 500 traceback: `except ValueError as e: raise HTTPException(400, str(e))` |
| I5.6 | `serve --host 127.0.0.1 --port 8000` command in `src/__main__.py` → `uvicorn.run(app, host=host, port=port)` |
| I5.7 | flake8 + mypy on `src/api.py` (subject IX) |

```python
class AskRequest(BaseModel):
    """Body of POST /answer."""
    question: str
    k: int = Field(3, gt=0, le=50)


@app.get('/search')
def search_api(q: str, k: int = 5) -> list[MinimalSource]:
    """Return the top-k sources for q."""
    try:
        return retrieve(q, k)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
```
Test:
```bash
uv run python -m src serve &
curl 'http://127.0.0.1:8000/search?q=lora+adapter&k=3'
curl -X POST http://127.0.0.1:8000/answer -H 'Content-Type: application/json' \
     -d '{"question":"What HTTP endpoint loads a LoRA adapter?"}'
curl 'http://127.0.0.1:8000/search?q=&k=3'      # → 400
```
**Bind to `127.0.0.1`**, not `0.0.0.0` — "local" API; nothing on the network should reach a
model server.
