import os

from .augmentation import Augmentation

from .utils import ft_open

from tqdm import tqdm
from .models import (
    MinimalAnswer,
    StudentSearchResultsAndAnswer,
    StudentSearchResults
)

from .search import retrieve

import uuid


def answer(
    query: str = '',
    k: int = 3,
    save_directory: str =
    'data/output/search_results_and_answer/query',
    index_dir: str = 'data/processed',
    out_file: str = 'student_search_result_and_answer.json'
) -> None:
    """Answer the query from retreved data"""

    from .generation import Generator
    os.makedirs(save_directory, exist_ok=True)
    sources = retrieve(query, k=k, save_directory=index_dir)

    a = Augmentation()
    a.read_sources(sources)
    msg = a.build_prompt(query)
    ans = Generator().generate(msg)
    search_res = MinimalAnswer(
        question_id=str(uuid.uuid4()),
        question=query,
        retrieved_sources=sources,
        answer=ans
    )

    out = StudentSearchResultsAndAnswer(
        search_results=[search_res],
        k=k
    )

    path = os.path.join(
        save_directory, os.path.basename(out_file)
    )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(out.model_dump_json(indent=4))

    print(f"Answer for the query : {ans}")
    print(f'Saved student_search_result_and_answer to {path}')


def answer_dataset(
    student_search_results_path: str =
    'data/output/search_results/UnansweredQuestions/dataset_docs_public.json',
    save_directory: str =
    'data/output/search_results_and_answer/UnansweredQuestions',
    k: int = 3
) -> None:

    if isinstance(k, bool) or not isinstance(k, int) or k <= 0:
        raise ValueError('--K must be positive.')

    from .generation import Generator

    os.makedirs(save_directory, exist_ok=True)
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
        try:
            a.read_sources(question.retrieved_sources[:k])
            msg = a.build_prompt(question.question)
            ans = g.generate(msg)
        except OSError as e:
            ans = f'Could not read sources: {e}'
        question_ans.append(MinimalAnswer(
            **question.model_dump(),
            answer=ans
        ))
        tqdm.write(f'Q: {question.question}\nA: {ans}\n')

    out = StudentSearchResultsAndAnswer(
        search_results=question_ans,
        k=k
        )

    path = os.path.join(
        save_directory, os.path.basename(student_search_results_path)
    )

    with open(path, 'w', encoding='utf-8') as f:
        f.write(out.model_dump_json(indent=4))
    print(
        f'Processed {question_ans} '
        f'of {len(questions.search_results)} questions'
    )
    print(f'Saved student_search_results_and_answer to {path}')
