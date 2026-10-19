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

