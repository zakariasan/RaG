# SUMMARY.md — swarm review of RAG against the machine

Review date: 2026-10-31. Code tested: working tree on top of `877dfb5 markdown_ enhancing`
(one uncommitted change: the markdown-chunker branch in `src/index.py` is commented out).
Review only: no file in `src/` was changed. All runs used a scratch index, never
`data/processed` or `data/output`.

This file replaces `TEST_REPORT.md`, `solutions.md` and `test.md`.

## How it was tested

| Agent | Scope |
|---|---|
| 1 Data engineering | ingestion, chunkers, index integrity, markdown_chunker measurement, md chunker prototype |
| 2 Search & RAG | recall, throughput, output validity, failure analysis, tokenizer experiments, evaluate |
| 3 CLI & answer | every command with degenerate inputs, 4 real Qwen generations, prompt token counts |
| 4 QA & compliance | lint, Makefile, docstrings, subject checklist (ch. V–X), repo hygiene, missing tests |
| 5 Adversarial | re-ran all 16 key claims independently: 14 CONFIRMED, 2 PARTIAL, 0 REJECTED |

## Verdict

- **Working tree:** retrieval passes the subject with margin.
- **Not ready to submit yet:**
  - `make lint` fails (flake8 + mypy).
  - The fix that makes recall pass is **uncommitted**.
  - The committed HEAD is broken: the markdown_chunker produces invalid sources, so the moulinette would reject the whole output.

---

## 1. What is good (tested, passed)

| Check | Result | Requirement |
|---|---|---|
| Index full corpus | 7.3 s, 18738 chunks, peak RSS ~394 MB | ≤ 300 s |
| Chunk size | 0 chunks > 2000 (min/median/max 0/1506/2000) | ≤ 2000 |
| Coverage | 2693 files: start 0, end = len(text), no gaps/overlaps | — |
| chunks.json ↔ BM25 order | 18738 = num_docs, contiguous per file | — |
| Skipped files | 181, all justified: 122 empty `__init__.py`, 56 images, 3 `.gitignore` | — |
| Docs recall @1/3/5/10 | 0.540 / 0.760 / **0.830** / 0.880 | @5 ≥ 0.80 |
| Code recall @1/3/5/10 | 0.354 / 0.566 / **0.657** / 0.697 | @5 ≥ 0.50 |
| `evaluate` vs independent scorer | identical on public sets | — |
| Throughput, 200 questions | 1.1 s incl. process start | ≤ 90 s |
| Output JSON | validates `StudentSearchResults` / `StudentSearchResultsAndAnswer`, ids kept, paths `data/raw/...` | VI.5 |
| Determinism | two runs byte-identical | — |
| Pydantic models | field-for-field match VI.4 | VI.4 |
| Fire CLI, 6 commands, tqdm bars | present | VI.6 |
| BM25 (bm25s), default chunk 2000 | yes | VI.1 |
| Python AST chunker | works, decorators kept, recursive split | VI.1 |
| Degenerate inputs | no traceback anywhere: empty/whitespace query, k=0/-1, huge k, missing/malformed/wrong-schema JSON, directory as path, file as save dir, `/proc`, empty datasets, Ctrl-C (rc 130) | VI.6 |
| Answers (4 generations) | 3/3 dataset answers correct and grounded, no hallucination; ~34 s single, ~31 s/question in dataset | VI.3 |
| uv | `uv lock --check` OK, pyproject ↔ uv.lock agree | V.4 |
| Context managers | every `open()` in `src/` uses `with`, no bare `except` | V.1 |
| README | italic first line + all chapter VIII sections | VIII |
| Moulinette not imported | yes | VI.6 |

---

## 2. Markdown chunker (markdown_chunker library) — verdict: drop it

Measured on HEAD `877dfb5`, where the md branch is enabled:

| | HEAD (library) | Working tree (line packing) |
|---|---|---|
| Index time, full corpus | 67.9 s, one core pegged | 12 s |
| Index time, docs only | 28–46 s | 0.4–0.6 s |
| Peak RAM | 392 MB | 394 MB |
| Warnings printed (stdout) | 465 | 0 |
| Chunks that are exact file slices | 0 of 1575 | all |
| Chunks with end ≤ start | 832 | 0 |
| Chunks over 2000 chars | 18–174 (max 10280) | 0 |
| Docs recall@5 | **0.280** | 0.830 |

The machine heat comes from 5.7× more CPU time, not memory.

Warnings seen:
- `Possible content loss during chunking! Missing approximately N bytes` ×177
- `List item count mismatch!` ×175
- `Code block count mismatch!` ×102
- `Heading count mismatch!` ×6
- `Table row count mismatch!` ×5

Root causes:
1. `src/txt_file_chunker.py:28`: `end = len(chunk)` should be `offset + len(chunk)`.
2. Even with that fix, offsets are meaningless. With `add_metadata=True` the library puts a YAML header (`---\nchunk:\n id: 1 ...`) in front of each chunk, and it drops or rewrites text (duplicate removal, header/footer detection). Its chunks are not substrings of the file.
3. `max_size` is ignored: `hard_max_len=2000` is hard-coded at `src/index.py:18-25`.
4. `strategy` is built twice (`src/index.py:16` and `:18`, the first is dead).

HEAD's search output contains 23 sources with negative or > 2000 width. One such source invalidates the whole output for the moulinette.

### Replacement: own Markdown chunker (exact offsets, cheap)

The subject wants two distinct strategies (Python + Markdown/text). The current
line packing works, but it does not use Markdown structure.

Agent 1 prototyped one in scratch:
- cut at ATX headings outside code fences;
- split oversize sections at blank lines, keeping fences whole;
- fall back to `hard_split`;
- pack neighbouring pieces up to `max_size`.

Measured: docs @1/3/5/10 = **0.63 / 0.81 / 0.85 / 0.87**, code @5 0.667, 0 coverage errors, 0 chunks > 2000, build time unchanged.

Suggested code, close to the prototype. It was **not** measured as written: re-run recall after adding it.

```python
import re

from .utils import get_offsets, hard_split

HEADING = re.compile(r' {0,3}#{1,6}\s')
FENCE = re.compile(r' {0,3}(```|~~~)')


def chunk_md_file(src_file: str, max_size: int) -> list[tuple[int, int]]:
    """Chunk Markdown at headings and paragraphs outside code fences.

    Args:
        src_file: file content.
        max_size: maximum chunk size in characters.

    Returns:
        Contiguous (start, end) character ranges covering the file.
    """
    if not src_file:
        return []
    lines = src_file.splitlines(keepends=True)
    offsets = get_offsets(lines)
    bounds = [0]
    in_fence = False
    for i, line in enumerate(lines):
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and i > 0 and (
                HEADING.match(line) or not lines[i - 1].strip()):
            bounds.append(offsets[i])
    bounds.append(len(src_file))
    pieces: list[tuple[int, int]] = []
    for s, e in zip(bounds, bounds[1:]):
        if s < e:
            pieces.extend(hard_split(s, e, offsets, max_size))
    out = [pieces[0]]
    for s, e in pieces[1:]:
        if e - out[-1][0] <= max_size:
            out[-1] = (out[-1][0], e)
        else:
            out.append((s, e))
    return out
```

Then in `src/index.py`:
- use `elif fil.endswith('.md'): pairs = chunk_md_file(src, max_size)`;
- delete the `markdown_chunker` import and both `strategy` blocks;
- run `uv remove markdown-chunker`.

Add a check that every chunk satisfies `0 <= s < e <= len(src)`, chunks are contiguous, and each is ≤ max_size.

---

## 3. What to fix (confirmed bugs, verified by agent 5)

Line numbers are for the current working tree.

### Blocker

**B1. `make lint` fails.**
- `uv run flake8 src` → `src/index.py:12:1: F401 '.txt_file_chunker.chunk_md_file' imported but unused`. This comes from your uncommitted edit; HEAD passed flake8.
- mypy (mandatory flags) → `src/generation.py:46: Item "list[str]" of "str | list[str]" has no attribute "strip"`.
- Fix for `generation.py`: your own commented-out lines 51-53 are the fix.
  ```python
      ) -> str:
          ...
          answer = self.tokenizer.decode(new, skip_special_tokens=True)
          if not isinstance(answer, str):
              raise TypeError("Expected decode to return a string")
          return answer.strip()
  ```
- Subject V.2 says lint runs `flake8 .` and `mypy .`. Today `mypy .` aborts with `Duplicate module named "utils"` (from `data/raw`), and `flake8 .` crawls `.venv` for minutes. Add:
  - `.flake8`:
    ```ini
    [flake8]
    exclude = .venv,.git,__pycache__,.mypy_cache,data
    ```
  - `pyproject.toml`:
    ```toml
    [tool.mypy]
    exclude = ['^data/', '^\.venv/']
    ```
- Makefile:
  - use `uv run flake8 .`, `uv run mypy . ...`;
  - `debug: uv run python -m pdb -m src` (pudb is not on PATH outside the venv);
  - add `.PHONY`.

**B2. Committed HEAD is broken** (section 2). Commit the working-tree fix together with the B1 F401 fix, or replace it with the new md chunker.

### High

**H1. A failed `index` leaves an inconsistent index** (`src/index.py:136-154`).
- `chunks.json` is written before BM25 is built.
- `index --files /nonexistent` writes `[]`, then fails with `ERROR414: max() iterable argument is empty`. The old BM25 files stay in place, so `search` then prints **nothing with rc 0**.
- A partial run with a different size leaves chunks.json with 174415 entries and BM25 with 4339 docs, so results would be silently wrong.
- `--files <single file>` fails the same way (`os.walk` on a file yields nothing).
- Fix: check first, save BM25, write chunks.json last, and check the lengths at load time.
  ```python
      chunk_meta, txt = index_machine(files, max_chunk_size)
      if not chunk_meta:
          raise ValueError(f"No indexable files found under '{files}'")
      corpus_tokens = [...]
      if not any(corpus_tokens):
          raise ValueError("No tokens produced: max_chunk_size too small")
      retriever.index(corpus_tokens)
      retriever.save(save_dir)
      # then write chunks.json
  ```
  In `src/search.py` after `BM25.load`:
  ```python
      if retriever.scores['num_docs'] != len(chunks):
          raise ValueError('Index and chunks.json do not match, re-run index')
  ```

**H2. `--max_chunk_size` above 2000 is accepted** (`src/index.py:132`). `--max_chunk_size 999999` gives rc 0 with a 22680-char chunk. The subject says one source over 2000 invalidates the output. `--max_chunk_size 1` crashes, because 1-char tokens are dropped. `abc`, `2.5`, `1e3` and `True` give cryptic errors.
```python
    if isinstance(max_chunk_size, bool) or not isinstance(max_chunk_size, int) \
            or not 0 < max_chunk_size <= 2000:
        raise ValueError("--max_chunk_size must be an integer in 1..2000")
```

### Medium

**M1. `./` prefix kills recall** (`src/index.py:83`). `index --files ./data/raw/...` stores `./data/raw/...`, which never matches the grader. Fix: `full_path = os.path.normpath(os.path.join(path, file))`.

**M2. `answer` hard-codes the index path** (`src/answer.py:17-21`). It calls `retrieve(query, k=k)` and always reads `data/processed/`. The subject says all paths are configurable. Add a `save_directory` parameter and pass it through. The command also prints plain text with no sources; print the source spans before the answer.

**M3. `answer_dataset` is all-or-nothing** (`src/answer.py:30-77`).
- No per-question try/except: one missing source file (`ft_open`, `augmentation.py:18`) aborts the run.
- `os.makedirs(save_directory)` runs only after the whole generation loop, so a bad save dir fails after ~1 h.
- Ctrl-C loses every answer.
- Fix: `makedirs` before `Generator()`, `try/except OSError` around each question, write every N questions and in `finally`.

**M4. No token budget** (`src/augmentation.py`). Measured with the Qwen tokenizer: k=3 ≈ 750–1600 tokens, k=50 ≈ 18–23k, k=200 ≈ 72–94k. The model limit is 40960 positions, so roughly k ≥ 90–110 overflows. Count tokens per source and stop adding sources at the budget (subject VI.3: "within its token budget").

**M5. Fire turns arguments into int/bool/float/list.**
- `search 123` / `True` / `[1,2]` → `expected string or bytes-like object, got 'int'`.
- `--k 2.5` → `Partition index must be integer`; `--k abc` → `'<=' not supported...`.
- No traceback, but valid queries are refused. Fix in `retrieve`, and reuse the k check in `search_dataset`, `answer_dataset`:
  ```python
      if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
          raise ValueError('--k must be a positive integer')
      query = str(query)
  ```

**M6. Docstrings missing** (subject V.1):
- `chunk_nodes` (`python_file_chunker.py:5`), `answer_dataset` (`answer.py:30`), classes `Augmentation` and `Generator`, and all 11 pydantic models.
- Existing docstrings are one-liners without Args/Returns.

### Low

- **L1. `evaluate` is wrong for multi-source truth** (`src/evaluate.py:31-40`). It scores only `sources[0]`, divides by the student count instead of the truth count, raises a raw KeyError on an unknown id (`ERROR414: 'zzz'`), and ignores `--k`. No effect on the public sets (1 source each). Fix:
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
- **L2. A mistyped flag runs the whole command, then fails** (`search lora --bogus 1` prints results, then rc 2). For `answer_dataset` this means ~1 h of generation into the default path. Fix: compare `--flags` in `sys.argv` against `inspect.signature(command).parameters` before `fire.Fire`.
- **L3. Output `k` values are wrong.** `answer_dataset` copies the search k (`answer.py:67`) while using only `--k 3` sources. `search_dataset` writes the clamped k (`"k": 18738` for a huge k) instead of the requested one.
- **L4. Very long `search` queries fail.** About 1500 words gives `ERROR414: Parser stack overflowed` (Fire). Document it.
- **L5. Errors go to stdout** with `Error404`/`ERROR414` labels and 3-line pydantic dumps. Use `print(..., file=sys.stderr)` and one line (`e.errors()[0]['msg']`).
- **L6. Empty non-.py file gives a `[0:0]` chunk** (`vllm_flash_attn/.gitkeep`). Return `[]` for empty text.
- **L7. Dead code:** `skip_file`/`skip_folder` (`index.py:44-54`), `g_checker` param, `src_file` param of `chunk_nodes`, 18 commented-out lines. `chunk_txt_file`'s parameter `filename` now receives the content: rename it.
- **L8. Typos:** `Erro form serach dataset`, `SOmthing`, `Extract Chunks probleme.`, `igonore`, `.gotignore`, `breakk`, `waht`, `Clearify`, `retreved`, `deppend`, `march of hard chunk`.
- **L9. Root leftovers.** `test01.py` imports the non-existent `src.retrieve`. `test.py` crashes on the empty `.mini_docs.json` and overwrites `mini_docs.json`. Both fail flake8 (E703, E702, W391). Also `main.py` (uv stub) and the 1.6 MB subject PDF. `git rm` them, or `flake8 .` fails.
- **L10. README options table is incomplete.** It is missing search `--load_dir`, search_dataset `--saved_file`, evaluate `--k`; update it after M2 adds `--save_directory` to `answer`. Index-dir option names are inconsistent (`--save_dir` / `--save_directory` / `--save_processed`): pick one.

### Hypotheses (not proven, low risk)

- 4 corpus files use `\r\n`. `open()` translates newlines, so their offsets are counted in translated text. This only matters if the moulinette counts raw characters, and none of these files are in the public datasets.
- The indexer filters the corpus with the cwd `./.gitignore`, matched against folder names (`data`, `build`, `dist`, `wheels`). It has no effect on vLLM 0.10.1 (verified), but results depend on where the command runs.
- `get_offsets` uses `str.splitlines`, which also splits on `\x0b \x0c \x1c-\x1e \x85`, while `ast` line numbers count only `\n`/`\r`. None of those characters are in the corpus.
- `max_new_tokens=128` can cut long answers. In the 4 runs, answers were 14–50 tokens, so none were cut. One answer missed a line because its source chunk ended mid code block.

---

## 4. Recall improvements (measured, scratch only, tuned on public sets)

| Variant | docs@5 | code@5 | code@10 |
|---|---|---|---|
| Current | 0.830 | 0.657 | 0.697 |
| + whole `snake_case` identifiers | 0.840 | 0.697 | 0.758 |
| + file name tokens added to each chunk | 0.830 | 0.747 | 0.808 |
| + English stopwords removed (bm25s, 33 words) | 0.840 | 0.657 | 0.687 |
| **all three together** (re-verified by agent 5) | **0.860** | **0.798** | 0.848 |
| + tests/ down-weighted ×0.7 | 0.860 | 0.808 | 0.879 |
| Markdown chunker prototype (section 2) | 0.850 | 0.667 | 0.697 |
| Full path tokens | 0.810 | 0.768 | 0.808 |
| Changing k1/b | 0.82 | 0.63–0.65 | worse |
| Down-weighting .json | 0.830 | 0.657 | no change |
| Chunk size 1500 / 1000 | 0.810 / 0.830 | 0.646 / 0.596 | worse |

Recommended: all three tokenizer changes, plus the md chunker. Keep bm25s defaults and size 2000.

```python
from bm25s.stopwords import STOPWORDS_EN

STOP = set(STOPWORDS_EN)


def tokenizer(string: str) -> list[str]:
    ...  # current body builds res
    res += [w.lower() for w in
            re.findall(r'[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+', string)]
    return [t for t in res if len(t) > 1 and t not in STOP]


def path_tokens(path: str) -> list[str]:
    """Tokens of the file name, added to every chunk of that file."""
    stem = os.path.splitext(os.path.basename(path))[0]
    return tokenizer(stem) + [stem.lower()]

# in index():
corpus_tokens = [tokenizer(t) + path_tokens(m.file_path)
                 for t, m in zip(txt, chunk_meta)]
```

Where misses come from at k=5:
- docs (17 misses): 9 right file but wrong span, 6 right file only in the top 10, 2 wrong file. `.py`/`.sh`/tests files outrank the `.md` page.
- code (34 misses): 13 wrong file, 13 wrong span, 8 right file only in the top 10. Causes: the question names the module (file names are not indexed), `tests/` outranks source files, and whole identifiers are lost.

---

## 5. Missing tests (no pytest suite exists)

Proposed `tests/`, to be run with `uv run pytest` (not graded):

- `test_hard_split_bounds`: spans ≤ max and contiguous; ValueError if max ≤ 0.
- `test_chunk_pfile_cover`: decorator, huge class, long expression → full coverage, ≤ max.
- `test_chunk_txt_cover` / `test_chunk_md_cover`: same, including one line > max; md chunks are exact slices.
- `test_tokenizer`: camelCase split, snake_case kept, 1-char tokens dropped.
- `test_index_roundtrip(tmp_path)`: chunks.json length = BM25 docs; empty corpus raises and writes nothing; `./` is normalized.
- `test_retrieve_edge`: empty query, k ≤ 0, non-int k, missing index → ValueError; huge k capped.
- `test_search_dataset_output`: validates the model; empty questions give `[]`.
- `test_evaluate_recall`: multi-source fixture, unknown id, IoU boundary 0.05.
- `test_cli_no_traceback` (subprocess): each degenerate command gives rc 1, one line, no `Traceback`.
- `test_answer_dataset_mocked`: monkeypatch `Generator`; output validates; partial save works.

## 6. Not tested

- **Official moulinette:** binary not in the repo. Run it on both datasets and require `Student data is valid: True`.
- **Fresh clone + `uv sync`:** `/tmp` is 1.8 GB. Do it on a disk with several GB free.
- **Full `answer_dataset` on 100 questions:** ~1 h on this CPU; 4 generations were run instead.

## 7. Task list (in order)

1. [ ] B1: fix F401 + mypy; add `.flake8` and `[tool.mypy]` excludes; `uv run` in the Makefile, pdb for debug.
2. [ ] B2: commit the working tree (md library removed), or the new md chunker; `uv remove markdown-chunker`.
3. [ ] H1, H2: safe index writes, `max_chunk_size` 1..2000, index/chunks length check.
4. [ ] M1–M5: normpath, `answer --save_directory`, robust `answer_dataset`, token budget, Fire types.
5. [ ] M6, L7, L8: docstrings, dead code, typos.
6. [ ] Recall: tokenizer changes + md chunker; re-index, re-measure, update the README tables.
7. [ ] L9: remove root leftovers; L10: fix the README options table.
8. [ ] Run the moulinette on docs and code; fresh-clone `uv sync`; `make lint` from a plain shell.
9. [ ] Optional: the tests in section 5.
