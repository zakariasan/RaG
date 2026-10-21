from .models import (StudentSearchResults, MoulinetteDataset)
from .utils import ft_open

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

    truth = {q.question_id: q for q in g_checker.rag_questions}
    if len(truth) == 0:
        raise ValueError("SOmthing wrong with the dataset to check")
    for question in questions.search_results:
        for src in question.retrieved_sources[:k]:
            elem = truth[src.question_id]
            if src.file_path == elem.sources[0].file_path and\
                    iou(src.first_character_index,
                        src.last_character_index,
                        elem.sources[0].first_character_index,
                        elem.sources[0].last_character_index) >= 0.05:
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
        questions = StudentSearchResults.model_validate_json(
            search_results=ft_open(
                student_search_results_path)['search_results'],
            k=k)
        g_checker = MoulinetteDataset.model_validate_json(
            rag_questions=ft_open(dataset_path)['rag_questions']
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
            print(f"Reacll@{kk}: {out:3f}")

    except (OSError) as e:
        print(e)
