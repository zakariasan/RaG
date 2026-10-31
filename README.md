*This project has been created as part of the 42 curriculum by zhaouzan.*

# RAG against the machine

## Description

A Retrieval-Augmented Generation (RAG) system that answers questions about the
vLLM codebase. It indexes the vLLM repository (`data/raw/vllm-0.10.1`), retrieves
the most relevant code and documentation snippets for a question with BM25, and
passes them to the local model `Qwen/Qwen3-0.6B` to generate a grounded answer.
Retrieval quality is measured with recall@k.

The pipeline has four stages:

1. **Indexing**: split every file into chunks (≤ 2000 characters) and build a BM25 index.
2. **Retrieving**: score all chunks against the question and return the top-k source locations.
3. **Augmenting**: read the text of the retrieved sources and build a chat prompt.
4. **Generating**: Qwen3-0.6B answers using only the given sources.

## Instructions

Requirements: Python ≥ 3.13, [uv](https://docs.astral.sh/uv/), several GB of free
disk space (torch + model weights). Runs on CPU; uses a GPU if available.

```bash
make install      # uv sync
make run          # index the corpus (data/raw -> data/processed)
make lint         # flake8 + mypy
make debug        # run the CLI under the debugger
make clean        # remove __pycache__ and .mypy_cache
```

Expected layout:

```
data/raw/                                   # corpus (vLLM repository)
data/processed/                             # index produced by `index`
data/datasets/UnansweredQuestions/          # questions
data/datasets/AnsweredQuestions/            # ground truth
data/output/search_results/<Scope>/         # search_dataset output
data/output/search_results_and_answer/<Scope>/  # answer_dataset output
```

All paths are CLI arguments; the defaults are only conveniences.

## Example usage

Every command: `uv run python -m src <command> [options]`.

```bash
# 1. Build the index
uv run python -m src index --max_chunk_size 2000

# 2. Single query
uv run python -m src search "How to configure LoRA?" --k 5

# 3. Whole dataset -> StudentSearchResults JSON
uv run python -m src search_dataset \
    --dataset_path data/datasets/UnansweredQuestions/dataset_docs_public.json \
    --k 10 \
    --save_directory data/output/search_results/UnansweredQuestions

# 4. Own recall@k against the ground truth
uv run python -m src evaluate \
    --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
    --dataset_path data/datasets/AnsweredQuestions/dataset_docs_public.json

# 5. Answer one question
uv run python -m src answer "How do I serve a LoRA adapter with vLLM?" --k 3

# 6. Answer a whole search-results file -> StudentSearchResultsAndAnswer JSON
uv run python -m src answer_dataset \
    --student_search_results_path data/output/search_results/UnansweredQuestions/dataset_docs_public.json \
    --save_directory data/output/search_results_and_answer/UnansweredQuestions
```

| Command | Options |
|---|---|
| `index` | `--max_chunk_size` (2000), `--files` (`data/raw`), `--save_dir` (`data/processed/`) |
| `search` | `query`, `--k` (10), `--save_directory` (index dir) |
| `search_dataset` | `--dataset_path`, `--k` (10), `--save_directory`, `--save_processed` (index dir) |
| `answer` | `query`, `--k` (3) |
| `answer_dataset` | `--student_search_results_path`, `--save_directory`, `--k` (3, sources per prompt) |
| `evaluate` | `--student_search_results_path`, `--dataset_path`, `--max_context_length` (2000) |

Degenerate inputs (empty query, `k <= 0`, missing files, malformed JSON) print an
error and exit with code 1; Ctrl-C exits with 130.

## System architecture

```
data/raw ──> index_machine ──> chunkers ──> tokenizer ──> BM25 (bm25s)
                (walk files)    (.py: AST)                   │
                                (text: lines)                ▼
                                              data/processed/{chunks.json, *.npy, vocab}
question ──> tokenizer ──> BM25 retrieve ──> top-k MinimalSource
                                                  │
                                    Augmentation (read spans, build prompt)
                                                  │
                                    Generator (Qwen3-0.6B) ──> answer
```

| Module | Role |
|---|---|
| `src/__main__.py` | Fire CLI, top-level error handling and exit codes |
| `src/index.py` | Walk the corpus, chunk, tokenize, build and save the BM25 index |
| `src/python_file_chunker.py` | AST-based chunking for `.py` files |
| `src/txt_file_chunker.py` | Line-based chunking for Markdown and other text |
| `src/utils.py` | File reading, line offsets, size-bounded splitting |
| `src/search.py` | `retrieve`, `search`, `search_dataset` |
| `src/augmentation.py` | Load source spans and build the chat prompt |
| `src/generation.py` | Load Qwen3-0.6B and generate the answer |
| `src/answer.py` | `answer`, `answer_dataset` |
| `src/evaluate.py` | recall@k with IoU ≥ 0.05 |
| `src/models.py` | pydantic models exchanged between stages |

`chunks.json` stores one `MinimalSource` (file path + character range) per chunk,
in the same order as the BM25 documents, so a BM25 document id maps directly to
a source location.

## Chunking strategy

Two strategies, both guaranteeing every chunk is ≤ `max_chunk_size` characters
and that chunks of a file cover it contiguously (no gaps, no overlap):

- **Python** (`ast`): the file is parsed and split at top-level statement
  boundaries (decorators stay with their function/class). Consecutive small
  statements are merged while they fit. A statement that is too large (e.g. a big
  class) is split recursively at its body statements; if it has no body (a long
  expression) it falls back to line-based splitting.
- **Markdown / text**: lines are packed greedily into chunks up to the limit, so a
  chunk never cuts a line in the middle. A single line longer than the limit is
  cut hard at the limit.

Files that are not valid UTF-8 (images, binaries) or Python files with syntax
errors are skipped.

## Retrieval method

BM25 via the `bm25s` library (default k1/b). Ranking is by BM25 score over the
chunk tokens.

Custom tokenizer, shared by indexing and querying:

- extract alphanumeric words, lowercase them;
- additionally split `camelCase` / `PascalCase` / `HTTPServer`-style words into
  their parts (`LoRARequest` → `lorarequest`, `lo`, `ra`, `request`), so a question
  in plain words can match identifiers;
- drop 1-character tokens.

Questions are retrieved in one batched call for `search_dataset`.

## Performance analysis

Measured on an Intel i7-7600U (2 cores / 4 threads, no GPU), public datasets,
`max_chunk_size 2000`:

| Metric | Result | Requirement |
|---|---|---|
| Indexing time (2874 files, 18738 chunks) | 7.9 s | ≤ 300 s |
| `search_dataset`, 100 questions | ~0.5 s | ≤ 90 s / 200 q |
| Docs recall@1 / @3 / @5 / @10 | 0.540 / 0.760 / **0.830** / 0.880 | @5 ≥ 0.80 |
| Code recall@1 / @3 / @5 / @10 | 0.354 / 0.566 / **0.657** / 0.697 | @5 ≥ 0.50 |
| `answer`, one question, k=3 | ~60 s (fp32 CPU) | — |

Effect of chunk size on recall@5:

| `max_chunk_size` | chunks | docs@5 | code@5 |
|---|---|---|---|
| 2000 | 18742 | 0.830 | 0.657 |
| 1500 | 24900 | 0.810 | 0.646 |
| 1000 | 37050 | 0.830 | 0.596 |

Smaller chunks mostly hurt code questions: a function split in several pieces
spreads its identifiers, and each piece scores lower.

## Design decisions

- **BM25 over TF-IDF**: length normalisation and term saturation work better on
  chunks of very different sizes (one-line config vs. 2000-char function).
- **`bm25s`**: sparse-matrix BM25, fast to build and to query, index saved to disk.
- **Character offsets, not text, in `chunks.json`**: the output format needs exact
  `file_path` + range; text is re-read from the file only when answering.
- **Identifier-aware tokenizer**: questions paraphrase, code uses `camelCase`;
  splitting identifiers lets both match.
- **Lazy import of torch/transformers**: only `answer` commands load the model, so
  `search` starts in about a second instead of 20–40 s.
- **fp32 on CPU, bf16 only on GPU**: bf16 matmul on a CPU without native bf16 was
  far too slow to finish.
- **Greedy decoding, thinking disabled** (`enable_thinking=False`): deterministic
  answers, no long reasoning output from Qwen3.
- **Prompt**: system message restricts the model to the given sources and asks it
  to say so when they do not contain the answer.

## Challenges faced

- **CPU generation speed**: the default bf16 dtype never finished on this CPU;
  switching to fp32 brought one answer to about a minute. Fewer sources (k=3)
  and a token limit keep prompts short.
- **Slow CLI start**: importing torch for every command made `search` take
  20–40 s; moving the import into the answer functions fixed it.
- **Chunks over the 2000-character limit**: the moulinette rejects the whole output
  for one oversized source; the recursive AST split + hard line split guarantee the
  limit.
- **Degenerate inputs**: empty or punctuation-only questions produce no tokens;
  they now return empty sources instead of random results, and `k <= 0`, missing
  files and malformed JSON give clear errors and a non-zero exit code.
- **Exact paths**: the grader compares `file_path` verbatim, so paths are stored
  exactly as walked from `data/raw`.

## Resources

- Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks* (2020) — https://arxiv.org/abs/2005.11401
- Robertson & Zaragoza, *The Probabilistic Relevance Framework: BM25 and Beyond* (2009)
- bm25s — https://github.com/xhluca/bm25s
- Qwen3-0.6B model card — https://huggingface.co/Qwen/Qwen3-0.6B
- Hugging Face Transformers, chat templates and generation — https://huggingface.co/docs/transformers
- Python `ast` module — https://docs.python.org/3/library/ast.html
- Python Fire — https://github.com/google/python-fire
- pydantic — https://docs.pydantic.dev
- uv — https://docs.astral.sh/uv/

### AI usage

AI (Claude) was used for:

- reviewing code and finding bugs, testing edge cases of the CLI, and measuring
  recall and timings;
- drafting this README and the test report.

All code in `src/` was written by me; every suggestion was checked, tested and
understood before being kept.
