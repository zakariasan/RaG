# TEST_REPORT.md

Review date: 2026-10-25. Review only: no project source file was modified.
All index/search runs used a scratch index (`index --save_dir <scratch>`), so
`data/processed/` was not touched.

## Project health

The retrieval core is correct and fast: indexing, chunking, BM25 search and
`search_dataset` all pass with large margins. The main defense risks are
`make lint` failing, a near-empty README, and docs recall@5 sitting only 3
points above the required threshold.

## Tests

| Test | Command | Result |
|---|---|---|
| flake8 on src | `uv run flake8 src` | PASS |
| mypy (Makefile flags) | `uv run mypy src --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs` | FAIL: `src/generation.py:46: Item "list[str]" of "str \| list[str]" has no attribute "strip"` |
| mypy strict | `uv run mypy src --strict` | FAIL: 8 errors (optional rule) |
| flake8 / mypy on `.` (as the subject words it) | `uv run flake8 .` / `uv run mypy . ...` | FAIL: thousands of E501 in `data/raw`, mypy aborts on duplicate modules |
| Makefile lint outside venv | `command -v mypy pudb` with plain PATH | FAIL: `mypy` and `pudb` not found |
| Index full corpus | `uv run python -m src index --max_chunk_size 2000 --save_dir <scratch>` | PASS: 7.9 s (limit 300 s), 18738 chunks |
| Chunk integrity | scratch audit script | PASS: 0 chunks > 2000, every indexed file covered contiguously from 0 to EOF |
| Skipped files | scratch audit script | PASS: 181 skipped = 122 empty `.py`, 59 images/binaries |
| Local index freshness | `cmp data/processed/chunks.json <scratch>/chunks.json` | PASS: identical |
| search_dataset docs (100 q) | `search_dataset --dataset_path .../UnansweredQuestions/dataset_docs_public.json --k 10 ...` | PASS: ~0.5 s |
| search_dataset code (99 q) | same, `dataset_code_public.json` | PASS: ~0.5 s |
| Recall docs | `evaluate ...docs...` | Recall@1 0.540, @3 0.760, **@5 0.830**, @10 0.880 (need @5 ≥ 0.80) |
| Recall code | `evaluate ...code...` | Recall@1 0.354, @3 0.566, **@5 0.657**, @10 0.697 (need @5 ≥ 0.50) |
| evaluate vs independent scorer | scratch script (multi-source, mean over truth) | PASS: identical numbers |
| search edge cases: `""`, `"   ?!"`, `--k 0`, `--k -1`, `--k 999999`, missing index, missing vocab file, corrupt `chunks.json` | `search ...` | PASS: clean message, rc=1, no traceback |
| search nonsense word | `search xqzvbnmplk` | PASS (returns zero-score results, no crash) |
| search numeric/bool/list query | `search 123`, `search True`, `search "[1,2]"` | FAIL (no traceback, but valid query refused) |
| search bad k type | `--k abc`, `--k 2.5` | PASS no traceback, cryptic message |
| unknown command | `python -m src nosuchcmd` | PASS: Fire usage, rc=2 |
| search_dataset edge cases: missing file, malformed JSON, `[]`, empty `rag_questions`, empty/punctuation questions, directory as path, save_directory is a file | `search_dataset ...` | PASS: no traceback |
| evaluate edge cases: malformed JSON, empty results, Unanswered file as truth | `evaluate ...` | PASS: no traceback |
| evaluate mismatched datasets | docs results vs code truth | FAIL: `ERROR414: '17526382-...'` (raw KeyError) |
| index edge cases | `--max_chunk_size 0`, `--max_chunk_size abc` | PASS |
| index missing raw dir | `index --files /nonexistent --save_dir <scratch>` | FAIL: see Bug 3 |
| index tiny chunk size | `index --max_chunk_size 1 --files data/raw/vllm-0.10.1/docs/features` | FAIL: `max() iterable argument is empty` |
| index `./` prefix | `index --files ./data/raw/...` | FAIL: see Bug 4 |
| answer edge cases | `answer ""`, `answer lora --k 0` | PASS |
| answer single query | `answer "How do I serve a LoRA adapter with vLLM?" --k 3` | PASS (rc 0, 64 s), answer truncated |
| answer_dataset 2 questions | `answer_dataset --student_search_results_path <2q file> --save_directory <scratch>` | PASS: valid `StudentSearchResultsAndAnswer`, 2nd answer truncated |
| answer_dataset empty results | `{"search_results": [], "k": 10}` | PASS |
| answer_dataset missing source file | file_path `data/raw/nope.md` | FAIL: whole run aborts (see Bug 8) |
| Clean-environment install | fresh `git clone` + `uv sync --frozen` | BLOCKED: `/tmp` is 1.8 GB, `No space left on device` |
| Official moulinette | `./moulinette evaluate_student_search_results ...` | NOT RUN: binary not present in repo |
| Token-budget overflow (large k in answer) | — | NOT RUN: too slow on this CPU |

## Confirmed bugs

| # | Severity | Bug | Reproduction | Root cause |
|---|---|---|---|---|
| 1 | Blocker | `make lint` fails | `make lint` | mypy error at `src/generation.py:46` (`decode` typed `str \| list[str]`); Makefile calls bare `mypy`/`pudb`, not on PATH outside venv (use `uv run`); no flake8/mypy exclude for `.venv`/`data` if run on `.`; root `test.py` E703, `main.py` untyped |
| 2 | Blocker | README fails chapter VIII | `cat README.md` (2 lines) | Missing Description, Instructions, Resources + AI usage, architecture, chunking, retrieval, performance, design decisions, challenges, example usage |
| 3 | High | Failed index destroys the existing one | `index --files /nonexistent` | `src/index.py:122-130` writes `chunks.json` before BM25 is built; BM25 crashes on empty corpus, old `.npy`/vocab remain. Mismatched `chunks.json`/BM25 then gives `list index out of range`; if chunks are larger than BM25, sources would silently be wrong (reasoned, not reproduced) |
| 4 | High | `./` prefix breaks grading | `index --files ./data/raw/...` then `search lora` returns `./data/raw/...` | `src/index.py:70` stores `os.path.join` result as-is; grader compares paths verbatim. Normalize with `os.path.normpath` |
| 5 | Medium | Fire coerces queries to non-str | `search 123` → `expected string or bytes-like object, got 'int'` | `query` passed straight to `tokenizer` (`src/search.py:31`); needs `str(query)`. Same for `--k abc` / `--k 2.5` cryptic messages (no int check) |
| 6 | Medium | Answers truncated mid-sentence | `answer ...` → `vllm serve s3://my-b` | `max_new_tokens=128` at `src/generation.py:22` |
| 7 | Medium | `answer` index path hard-coded, plain-text output | `answer` has no index-dir option | `src/answer.py:21` calls `retrieve(query, k=k)` with default `data/processed/`; subject requires all paths configurable; no sources/JSON printed |
| 8 | Medium | `answer_dataset` all-or-nothing | missing source file, or Ctrl-C mid-run | `src/answer.py:51-75`: no per-question try/except, writes only at end (~1 min/question here) |
| 9 | Low | `evaluate` raw KeyError, first source only | docs results vs code truth | `src/evaluate.py:139` `truth[...]`; `:141` checks only `sources[0]`, divides by student count. Public datasets all have exactly 1 source, so current numbers are correct |
| 10 | Low | Missing docstrings | AST scan | `answer_dataset`, `chunk_nodes`, `Augmentation`, `Generator`, all pydantic models |
| 11 | Low | Empty file → zero-length chunk | `vllm/vllm_flash_attn/.gitkeep [0:0]` | `hard_split` returns `(0, 0)` for empty file |

## Hypotheses (not proven)

- CRLF offsets: 4 corpus files contain `\r\n`; `open()` translates newlines, so offsets
  shift (`tests/test_seed_behavior.py`: 793 vs 817 chars). Only matters if the moulinette
  counts raw characters. Low impact (test files).
- No token budget in `src/augmentation.py`: a large `answer --k` could overflow the
  model context. Not run.
- `src/index.py:15-28` filters the corpus with the project's own cwd-relative
  `.gitignore` (`/data/*`, `build/`, `dist/`...). Currently skips no corpus directory
  (verified), but fragile.

## Fixes

None applied (review-only request). Fix order: 1, 2, then 3–6, then recall.

## RAG audit

- Ingestion: 2874 raw files, 2693 indexed, all skips justified.
- Chunking: Python AST-based (`src/python_file_chunker.py`), text line-packing
  (`src/txt_file_chunker.py`); sizes always ≤ max, full contiguous coverage.
- Indexing: BM25 (bm25s), 7.9 s. Partial-write issue (Bug 3).
- Retrieval: thresholds met; docs margin is thin.

Scratch recall experiment (project untouched, k=5):

| Variant | docs@5 | code@5 | chunks |
|---|---|---|---|
| Current | 0.830 | 0.657 | 18742 |
| + whole `snake_case` identifiers as extra tokens | **0.840** | **0.697** | 18742 |
| Only `.py` / `.md` | 0.820 | 0.657 | 15751 |
| Chunk size 1500 | 0.810 | 0.646 | 24900 |
| Chunk size 1000 | 0.830 | 0.596 | 37050 |

Keeping whole identifiers helps; filtering file types or smaller chunks hurts.
At k=5, 8 docs and 21 code questions miss the right file entirely.

## API / CLI audit

- No unhandled traceback found in any tested edge case; exit codes 1 (error), 2 (Fire usage), 130 (Ctrl-C).
- Broken/weak: numeric/bool queries (Bug 5), `answer` path not configurable (Bug 7),
  error messages go to stdout with `Error404`/`ERROR414` labels and multi-line pydantic dumps.
- HTTP API: none (bonus only).

## Strengths

- Indexing ~40x under the time limit.
- Chunk size limit never exceeded; no gaps or overlaps.
- `search_dataset` ~180x faster than the 90 s / 200 questions requirement.
- Recall thresholds met on both public datasets.
- Output JSON validates against the pydantic models.
- Degenerate inputs handled without tracebacks.

## Remaining issues / missing coverage

- No unit tests in the repo (root `test.py` crashes: it loads the empty `.mini_docs.json`).
- Root leftovers: `main.py`, `test.py`, `mini_docs.json`, `.mini_docs.json`; 1.6 MB subject PDF committed.
- Official moulinette score, clean-env install and token-budget overflow not tested.

## External tests

Attempted a fresh clone + `uv sync --frozen` in a temp directory: BLOCKED by
`/tmp` size (1.8 GB) during wheel install. No cloud environment used.
