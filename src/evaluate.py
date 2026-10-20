import json
from .models import (StudentSearchResults, RagDataset)

from tqdm import tqdm


def iou(a, b, c, d):
    """Calculate march of hard chunk and overload"""
    inter = max(0, min(b, d) - max(a, c))
    union = max(b, d) - min(a, c)
    return inter / union if union else 0.0


def recalling(questions: StudentSearchResults, g_checker: RagDataset, k: int):
    """Calculate the recall@k one time"""
    hits = 0
    for question in questions.search_results:
        truth = g_checker.rag_questions[f'{question.question_id}']
        for src in question.retrieved_sources[:k]:
            if src.file_path == truth.sources[0] and\
                    iou(src.first_character_index,
                        src.last_character_index,
                        truth.first_character_index,
                        truth.last_character_index) >= 0.05:
                hits += 1
                break
    recall = hits / len(question.search_results)

    return recall


def evaluate(
    student_search_results_path: str =
    'data/output/search_results/UnansweredQuestions/dataset_docs_public.json',
    dataset_path: str =
    'data/datasets_public/public/AnsweredQuestions/dataset_docs_public.json',
    k: int = 10,
    max_context_length: int = 2000
):
    """Check your answer protocol"""
    try:
        with open(student_search_results_path, encoding='utf-8') as f:
            questions = json.load(f)
        with open(dataset_path, encoding='utf-8') as f:
            ground_checker = json.load(f)

        questions = StudentSearchResults(search_results=questions['search_results'], k=k)
        g_checker = RagDataset(rag_questions=ground_checker['rag_questions'])

        k = 1
        for i in range(4):
            out = recalling(questions, g_checker, k)
            k += 2 if k < 5 else 5
            print(f"racll@{k}: {out}")

    except (OSError, PermissionError, FileNotFoundError) as e:
        print(e)

    print("Evaluation Results \n ========================================")

