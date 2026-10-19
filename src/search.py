import json
import os

import bm25s
from tqdm import tqdm

from .index import tokenizer
from .models import (
    RagDataset,
    MinimalSource,
    MinimalSearchResults,
    StudentSearchResults
)

from .utils import ft_open


def search(
    query: str = '',
    k: int = 10,
    save_directory: str = 'data/processed/',
    load_dir: str = 'chunks.json'
) -> None:
    """
    Search for a query in the corpus of processed/chunks.json get the
    least top-K
    """
    if k <= 0:
        raise ValueError('K must be positive.')
    try:
        with open(os.path.join(save_directory, load_dir), encoding='utf-8') as file:
            chunks = json.load(file)

        retriever = bm25s.BM25.load(save_directory)
        tokens = tokenizer(query)
        if len(tokens) == 0:
            raise ValueError('Empty query')
        k = min(k, len(chunks))
        res, _scores = retriever.retrieve([tokens], k=k, show_progress=True)
        for i in res[0]:
            c = chunks[i]
            print(
                f"{c['file_path']} "
                +
                f"[{c['first_character_index']}:{c['last_character_index']}]")
    except (OSError, FileNotFoundError, PermissionError):
        raise ValueError('Index file not Found.')


def search_dataset(
    dataset_path: str = 'data/datasets_public/Public/UnansweredQuestions/dataset_docs_public.json',
    k: int = 5,
    save_directory: str = 'data/output/search_results/UnansweredQuestions',
    save_processed='data/processed',
    saved_file='chunks.json'
) -> None:
    """search from the input datasets"""

    try:
        with open(
            dataset_path,
            encoding='utf-8'
        ) as f:
            questions = f.read()

        ds = RagDataset.model_validate_json(questions)

        with open(
            os.path.join(save_processed, saved_file),
            encoding='utf-8'
        ) as f:
            chunks = json.load(f)

        all_tokens = [tokenizer(q.question) for q in ds.rag_questions]
        retriever = bm25s.BM25.load(save_processed)
        res, _scores = retriever.retrieve(all_tokens, k=k)

        rows = []
        for i, q in enumerate(
            tqdm(
                ds.rag_questions,
                desc='Searching',
                unit='question')):
            srcs = [MinimalSource(**chunks[j]) for j in res[i]]
            rows.append(
                MinimalSearchResults(
                    question_id=q.question_id,
                    question=q.question,
                    retrieved_sources=srcs))
        out = StudentSearchResults(search_results=rows, k=k)
        os.makedirs(save_directory, exist_ok=True)
        path = os.path.join(save_directory, os.path.basename(dataset_path))

        with open(path, 'w', encoding='utf-8') as f:
            f.write(out.model_dump_json(indent=4))
    except (OSError, PermissionError, FileNotFoundError) as e:
        raise ValueError(f"Erro form serach dataset: {e}")
    print(f'Saved student_search_results to {path}')
