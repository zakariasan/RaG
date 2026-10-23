import os

from .search import search
from .augmentation import Augmentation

from .generation import Generator
from .utils import ft_open

from tqdm import tqdm
from .models import (
    MinimalAnswer,
    StudentSearchResultsAndAnswer,
    StudentSearchResults
)


def answer(query: str, k: int = 5) -> None:
    """Answer the query from retreved data"""

    sources = search(query, k)

    a = Augmentation()
    a.read_sources(sources)
    msg = a.build_prompt(query)
    print(Generator().generate(msg))


def answer_dataset(
    student_search_results_path: str =
    'data/output/search_results/UnansweredQuestions/dataset_docs_public.json',
    save_directory: str =
    'data/output/search_results_and_answer/UnansweredQuestions',
    k: int = 5
) -> None:

    questions = StudentSearchResults.model_validate_json(
        ft_open(student_search_results_path)
    )

    print(f'Loaded {len(questions.search_results)} questions')

    a = Augmentation()
    g = Generator()

    question_ans = []
    for question in tqdm(
            questions.search_results,
            desc='Answering',
            unit='question'
    ):
        a.read_sources(question.retrieved_sources[:k])
        msg = a.build_prompt(question.question)
        ans = g.generate(msg)
        question_ans.append(
            MinimalAnswer(**question.model_dump(), answer=ans)
        )
    out = StudentSearchResultsAndAnswer(
        search_results=question_ans,
        k=questions.k
        )

    os.makedirs(save_directory, exist_ok=True)
    path = os.path.join(
        save_directory, os.path.basename(student_search_results_path))
    with open(path, 'w', encoding='utf-8') as f:
        f.write(out.model_dump_json(indent=4))
    print(f'Saved student_search_results_and_answer to {path}')
