import json
from .models import (StudentSearchResults, MoulinetteDataset)

# from tqdm import tqdm


def iou(a: int, b: int, c: int, d: int) -> float:
    """Calculate march of hard chunk and overload"""
    inter = max(0, min(b, d) - max(a, c))
    union = max(b, d) - min(a, c)
    return inter / union if union else 0.0


def recalling(
    questions: StudentSearchResults,
    g_checker: MoulinetteDataset,
    k: int
) -> float:
    """Calculate the recall@k one time"""
    hits = 0
    for question in questions.search_results:
        # truth = g_checker.rag_questions[f'{question.question_id}']
        truth = next((
            q for q in g_checker.rag_questions
            if q.question_id == question.question_id),
                     None
                     )
        if truth is None:
            continue
        for src in question.retrieved_sources[:k]:
            if src.file_path == truth.sources[0].file_path and\
                    iou(src.first_character_index,
                        src.last_character_index,
                        truth.sources[0].first_character_index,
                        truth.sources[0].last_character_index) >= 0.05:
                hits += 1
                break
    recall = hits / len(questions.search_results)

    return recall


def evaluate(
    student_search_results_path: str =
    'data/output/search_results/UnansweredQuestions/dataset_docs_public.json',
    dataset_path: str =
    'data/datasets_public/public/AnsweredQuestions/dataset_docs_public.json',
    k: int = 10,
    max_context_length: int = 2000
) -> None:
    """Check your answer protocol"""
    try:
        with open(student_search_results_path, encoding='utf-8') as f:
            questions = json.load(f)
        with open(dataset_path, encoding='utf-8') as f:
            ground_checker = json.load(f)

        questions = StudentSearchResults(
            search_results=questions['search_results'],
            k=k)
        g_checker = MoulinetteDataset(
            rag_questions=ground_checker['rag_questions']
        )
        oversized = [s for r in questions.search_results
                     for s in r.retrieved_sources
                     if s.last_character_index - s.first_character_index
                     > max_context_length
                     ]
        print(f"Student data is valid: {len(oversized) == 0}")
        print(f"Total number of questions: {len(questions.search_results)}")
        ss = [r for r in questions.search_results
              if len(r.retrieved_sources) > 0
              ]
        print(f"Total number of questions with student sources: {len(ss)}")
        print("Evaluation Results \n ========================================")
        for kk in (1, 3, 5, 10):
            out = recalling(questions, g_checker, kk)
            kk += 2 if kk < 5 else 5
            print(f"racll@{kk}: {out}")

    except (OSError, PermissionError, FileNotFoundError) as e:
        print(e)
