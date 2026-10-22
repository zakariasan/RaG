import os
import json

from .search import search
from .augmentation import Augmentation

from .generation import Generator
from .utils import ft_open

from tqdm import tqdm
from .models import MinimalAnswer, StudentSearchResultsAndAnswer


def answer(query: str, k: int = 10) -> None:

    sources = search(query, k)

    a = Augmentation()
    a.read_sources(sources)
    msg = a.build_prompt(query)
    print(Generator().generat(msg))


def answer_dataset(
    student_search_results_path: str =
    'data/output/search_results/UnansweredQuestions/dataset_docs_public.json',
    save_directory: str =
    'data/output/search_results_and_answer/UnansweredQuestions',
    k: int = 5
) -> None:

    questions = StudentSearchResultsAndAnswer.model_validate_json(
        ft_open(student_search_results_path)
    )

    print(f'Loaded {len(questions.search_results)} Questions')

    a = Augmentation()
    g = Generator()

    question_ans = []
    for question in tqdm(
            questions.search_results,
            desc='Answering',
            unit=' Question'
    ):
        a.read_sources(question.retrieved_sources[:k])
        msg = a.build_prompt(question.question)
        ans = g.generat(msg)
        question_ans.append(
            MinimalAnswer(**question.model_dump(), answer=ans)
        )
        out = StudentSearchResultsAndAnswer(
            search_results=question_ans, k=question.k
        )

        os.makedirs(save_directory, exist_ok=True)
        path = os.path.join(
            save_directory, os.path.basename(student_search_results_path))
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(out, f, indent=4)
        print(f'Saved student search results and answer to {path}')
