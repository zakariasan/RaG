Good move — iou is correct, both files load, you're reading AnsweredQuestions now. Three things stop it running, then the scoring itself is still missing.

Crashes:

1. for question in tqdm(questions, ...) — questions is a StudentSearchResults model, not a list. Pydantic models aren't iterable → TypeError: 'StudentSearchResults' object is not iterable. You want questions.search_results.
2. for d in g_checker — same thing. g_checker.rag_questions.
3. question.id — the field is question_id. AttributeError.

Wrong path: data/datasets_public/public/AnsweredQuestions/... — I checked, data/datasets_public doesn't exist. It's:
data/datasets/AnsweredQuestions/dataset_docs_public.json

Missing the actual work. The loop finds quest and then stops — flake8 says it too: F841 local variable 'quest' is assigned to but never used. iou is never called, nothing is counted, nothing is printed. What's left:

hits = 0
for each row in questions.search_results:
    truth = gt[row.question_id]                  # dict lookup
    for src in row.retrieved_sources[:k]:        # rank order, first k only
        if src.file_path == truth_source.file_path and iou(...) >= 0.05:
            hits += 1
            break                                 # one hit per question, stop
recall = hits / len(questions.search_results)
The break matters — a question counts once, not once per matching source.

Build the lookup dict before the loop, not a list scan inside it:
gt = {q.question_id: q for q in g_checker.rag_questions}
Your [d for d in g_checker if d.question_id == question.id][0] rescans all 100 questions for every question — 10000 comparisons — and raises IndexError instead of a clear message when an id is missing.

Smaller:

- Use StudentSearchResults.model_validate_json(f.read()) instead of rebuilding with k=k. Right now you overwrite the file's own k with the CLI one, so the model says k=10 when the file holds 5 sources.
- k: int = 10 can't work on your data — your files have 5 sources per row, so @10 equals @5. Print @1, @3, @5 and let k cap it.
- except (OSError, PermissionError, FileNotFoundError) — the last two are subclasses of OSError, so just OSError. And it prints then falls through into the rest with undefined variables. raise ValueError(...) or return.
- max_context_length still unused.
- Missing -> None, and no type hints on iou's four params (mypy runs --disallow-untyped-defs).

flake8, exact:
6:1  E302 expected 2 blank lines, found 1
7:9  E117 over-indented          (iou body has 8 spaces, use 4)
11:1 E302 expected 2 blank lines, found 1
26:80 E501 line too long (89 > 79)
30:13 F841 'quest' assigned but never used
33:5 E303 too many blank lines (2)
40:1 W391 blank line at end of file

Also move from tqdm import tqdm above from .models import ... — stdlib, then third-party, then local.

Target when it runs: docs 0.540 / 0.760 / 0.830.

What IoU is

"Did my chunk land on the same text as the right answer?" Both are ranges of characters in the same file, so compare the ranges.

IoU = Intersection over Union = (characters both ranges share) ÷ (characters either range covers).

Your real question 0:

ground truth   lora.md  4695 ────────────────── 6098
your rank 1    lora.md  3843 ──────────── 5716
                             ^^^^^^^^^^^^
                             shared: 4695 → 5716

- intersection = min(end) - max(start) = min(5716,6098) - max(3843,4695) = 5716 - 4695 = 1021
- union = max(end) - min(start) = 6098 - 3843 = 2255
- IoU = 1021 / 2255 = 0.453 ≥ 0.05 → hit

Why those two formulas: the overlap starts at whichever range starts later and ends at whichever ends earlier. The union spans from the earliest start to the latest end. max(0, ...) on the intersection because when the ranges don't touch at all the subtraction goes negative, and a negative overlap is meaningless — it's zero.

Your rank 2 on the same question: 5716-7714 vs 4695-6098 → ove27 → also a hit. Rank 3 is a different file → miss, no matter
the numbers.

And the tiny-chunk case from the old index: 4745-4833 vs 4695-, IoU 0.063. Correct file, correct spot, almost rejected. That's
the whole reason 2000-char chunks beat 62-char chunks.

def iou(a: int, b: int, c: int, d: int) -> float:
    inter = max(0, min(b, d) - max(a, c))
    union = max(b, d) - min(a, c)
    return inter / union if union else 0.0

What evaluate has to do

1. load YOUR file        -> StudentSearchResults  (has question_id + retrieved_sources)
2. load GROUND TRUTH     -> RagDataset            (has questio
3. index ground truth by question_id into a dict
4. for each of your rows:
       look up its ground truth by question_id
       walk your retrieved_sources in rank order, first k only
       hit = same file_path AND iou >= 0.05
       first hit -> count 1, stop looking at that row
5. recall@k = hits / number of rows
6. print for k = 1, 3, 5, 10

Step 3 matters: match by question_id, never by list position. Your file and the ground truth are not guaranteed in the same order.

Bugs in your draft

    student_search_results_path: str = 'data/output/search_res
    dataset_path: str = 'data/datasets_public/public/UnansweredQuestions/dataset_code_public.json'

1. No commas after those two parameters → SyntaxError. Nothing
2. student_search_results_path default is a directory, not a ftions/dataset_docs_public.json.
3. dataset_path points at the wrong folder twice. data/datasetst — it's data/datasets/. And it must be AnsweredQuestions, not
   UnansweredQuestions: only the answered twin has the sources. The unanswered file has nothing to compare with.
4. open(student_search_results) — that name doesn't exist, theresults_path → NameError.
5. questions = f.read() then questions.search_results — f.readave no .search_results → AttributeError. Use
   StudentSearchResults.model_validate_json(f.read()), then .s
6. Ground truth is never loaded. You open one file; you need b
7. for question in student_search_results_path: iterates the pacter — d, a, t, a… Loop over the parsed rows.
8. except prints and falls through. After the error you keep g and crash anyway. raise ValueError(...) or return.
9. max_context_length is unused — drop it, or use it to assert
10. Missing -> None return annotation; mypy runs with --disall

Your test: it must print 0.540 / 0.760 / 0.830 for docs and 0. Those are verified values.

