# solutions.md — proposed fixes for TEST_REPORT.md

Each fix maps to a bug number in `TEST_REPORT.md`. Snippets are suggestions to
apply yourself. After any change to `index.py` / `tokenizer`, re-run
`make run` and re-check recall.

Order: 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8, then recall, then the low ones.

---

## 1. `make lint` fails (Blocker)

### 1a. mypy error `src/generation.py:46`

`tokenizer.decode` is typed `str | list[str]`. Return a real `str`:

```python
    def generate(
        self,
        msg: list[dict[str, str]],
        max_new_tokens: int = 256
    ) -> str:
        """Return the model answer for a chat prompt."""
        ...
        answer = self.tokenizer.decode(new, skip_special_tokens=True)
        return str(answer).strip()
```

### 1b. Makefile: use `uv run`, lint `.` like the subject says

```makefile
debug:
	uv run python -m pdb -m src

lint:
	uv run flake8 .
	uv run mypy . --warn-return-any --warn-unused-ignores \
		--ignore-missing-imports \
		--disallow-untyped-defs \
		--check-untyped-defs

lint-strict:
	uv run flake8 .
	uv run mypy . --strict
```

(`pdb` is the built-in debugger the subject names; keep `pudb` only if you prefer it, but via `uv run`.)

### 1c. Exclude corpus and venv from `.` lint

New file `.flake8` at root:

```ini
[flake8]
exclude = .venv,.git,__pycache__,.mypy_cache,data
```

In `pyproject.toml`:

```toml
[tool.mypy]
exclude = ['^data/', '^\.venv/']
```

### 1d. Root files

Delete `main.py`, `test.py`, `mini_docs.json`, `.mini_docs.json`
(`git rm`), or fix them: `test.py:4` has E703 (`;`) and crashes on the empty
`.mini_docs.json`; `main.py` needs `-> None`.

Verify: `make lint` from a plain shell (venv NOT activated) → no output, rc 0.

---

## 2. README (Blocker)

Done: see the new `README.md`. Review the "AI usage" and "Challenges" parts and
correct anything that does not match what you actually did — you must be able
to defend every line.

---

## 3. Failed index destroys the existing one (High)

`src/index.py`: validate before writing anything, write `chunks.json` last.

```python
    chunk_meta, txt = index_machine(files, max_chunk_size)
    if not chunk_meta:
        raise ValueError(f"No indexable files found under '{files}'")
    corpus_tokens = [
        tokenizer(t) for t in tqdm(txt, desc='Tokenizing', unit=' chunk')]
    if not any(corpus_tokens):
        raise ValueError("No tokens produced: max_chunk_size too small?")
    try:
        os.makedirs(save_dir, exist_ok=True)
        retriever = bm25s.BM25()
        retriever.index(corpus_tokens)
        retriever.save(save_dir)
        chunks_path = os.path.join(save_dir, 'chunks.json')
        with open(chunks_path, 'w', encoding='utf-8') as file_opend:
            json.dump([item.model_dump() for item in chunk_meta],
                      file_opend, indent=4)
    except OSError as e:
        raise ValueError(f"Cannot save index: {e}")
```

Optional guard in `retrieve` / `search_dataset`: if
`len(chunks) != retriever.scores['num_docs']` → `ValueError('Index out of date, run index')`.

Verify: `index --files /nonexistent --save_dir /tmp/x` → clean error, nothing written.

---

## 4. `./` prefix breaks grading (High)

`src/index.py:70`:

```python
                full_path = os.path.relpath(os.path.join(path, file))
```

`relpath` turns `./data/raw/a.md` and `/abs/.../data/raw/a.md` into
`data/raw/a.md` (relative to the project root you run from).

Verify: `index --files ./data/raw` then `search lora --k 1` → path starts with `data/raw/`.

---

## 5. Fire turns queries into int / bool / list (Medium)

Top of `retrieve` in `src/search.py` (and use the same k check in
`search_dataset`, `answer_dataset`, `index`):

```python
    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError('k must be a positive integer.')
    query = str(query)
```

Same for each question in `search_dataset` is already safe (pydantic forces `str`).

Verify: `search 123`, `search True`, `--k abc`, `--k 2.5` → results or a clear message.

---

## 6. Answers cut mid-sentence (Medium)

`src/generation.py`: raise `max_new_tokens` to 256 and ask for short answers in
the system prompt (`src/augmentation.py`):

```python
                    'You answer questions about the vLLM codebase. '
                    'Use ONLY the sources below. If they do not contain '
                    'the answer, say so. Answer in 1-3 sentences.'
```

Trade-off: more tokens = slower on CPU (~60 s/question measured at 128).

---

## 7. `answer` index path hard-coded (Medium)

`src/answer.py`:

```python
def answer(
    query: str = '',
    k: int = 3,
    save_directory: str = 'data/processed/'
) -> None:
    """Answer one query from the retrieved sources."""
    from .generation import Generator
    sources = retrieve(query, k=k, save_directory=save_directory)
    ...
    for s in sources:
        print(f"{s.file_path} "
              f"[{s.first_character_index}:{s.last_character_index}]")
    print(Generator().generate(msg))
```

---

## 8. `answer_dataset` all-or-nothing (Medium)

`src/answer.py` loop: one bad question must not kill the run, and save as you go.

```python
    for question in tqdm(...):
        try:
            a.read_sources(question.retrieved_sources[:k])
            ans = g.generate(a.build_prompt(question.question))
        except OSError as e:
            ans = f"Could not read sources: {e}"
        question_ans.append(MinimalAnswer(**question.model_dump(), answer=ans))
        if len(question_ans) % 10 == 0:
            save(question_ans)   # small helper that writes the JSON
    save(question_ans)
```

Wrap the loop with `except KeyboardInterrupt: save(question_ans); raise` so
Ctrl-C keeps finished answers.

---

## 9. `evaluate` KeyError + first source only (Low)

`src/evaluate.py` `recalling`, matching the subject definition
(share of correct sources found, averaged over truth questions):

```python
    total = 0.0
    student = {q.question_id: q for q in questions.search_results}
    for qid, elem in truth.items():
        got = student.get(qid)
        if got is None or not elem.sources:
            continue
        found = sum(
            any(src.file_path == t.file_path and
                iou(src.first_character_index, src.last_character_index,
                    t.first_character_index, t.last_character_index) >= 0.05
                for src in got.retrieved_sources[:k])
            for t in elem.sources)
        total += found / len(elem.sources)
    return total / len(truth)
```

Also remove the unused `g_checker` parameter, and use or remove `k`.

---

## 10. Missing docstrings (Low)

Add one-line docstrings to: `answer_dataset`, `chunk_nodes`, classes
`Augmentation`, `Generator`, and every pydantic model in `src/models.py`.

---

## 11. Empty file → `[0:0]` chunk (Low)

`src/txt_file_chunker.py` and `src/python_file_chunker.py`, after reading:

```python
    if not src_file:
        return []
```

---

## Recall improvement (measured)

Keep whole `snake_case` identifiers as extra tokens. In `tokenizer`
(`src/index.py`), before the final filter:

```python
    res += [w.lower() for w in
            re.findall(r'[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+', string)]
```

Measured on the public sets (k=5): docs 0.830 → 0.840, code 0.657 → 0.697.
Do NOT filter to `.py`/`.md` only (docs drops to 0.820) and keep chunk size 2000
(1500 → docs 0.810, 1000 → code 0.596).

---

## Smaller cleanups

- Errors to stderr: `print(..., file=sys.stderr)` in `src/__main__.py`, one short
  line for `ValidationError` (`e.errors()[0]['msg']`), consistent label `Error:`.
- `src/search.py:41` `show_progress=False` so the bar does not mix with results.
- Indexer uses the project `./.gitignore` to filter the corpus
  (`src/index.py:15-28`): replace with a fixed skip list (`.git`, binaries) so
  results do not depend on the current directory.
- Typos in messages/docstrings: `igonore`, `waht`, `breakk`, `Clearify`,
  `SOmthing`, `Erro form serach`, `retreved`, `pipeLine`.

## To verify before defense

- Get the moulinette binary and run it on both datasets: requires
  `Student data is valid: True` first.
- CRLF: 4 corpus files contain `\r\n`; check one with the moulinette to see
  whether offsets read with `open()` (newline translation) are accepted.
- Run `uv sync` in a fresh clone on a disk with several GB free.
