import json

from .models import (StudentSearchResults, RagDataset)
from tqdm import tqdm

def iou(a, b, c, d):
        inter = max(0, min(b, d) - max(a, c))
        union = max(b, d) - min(a, c)
        return inter / union if union else 0.0

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

        for question in tqdm(questions, desc='Evaluation', unit=' question'):
            quest = [d for d in g_checker if d.question_id == question.id][0]


    except (OSError, PermissionError, FileNotFoundError) as e:

        print(e)
#    for question in student_search_results_path:

    print("Evaluation Results \n ========================================")


