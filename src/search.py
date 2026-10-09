import json
from .index import tokenizer
import os
import bm25s


def search(
    query: str = '',
    k: int = 10,
    save_dir: str = 'data/processed/',
    load_dir: str = 'chunks.json'
) -> None:
    """
    Search for a query in the corpus of processed/chunks.json get the
    least top-K
    """
    if k <= 0:
        raise ValueError('K must be positive.')
    try:
        with open(os.path.join(save_dir, load_dir), encoding='utf-8') as file:
            chunks = json.load(file)

        retriever = bm25s.BM25.load(save_dir)
        tokens = tokenizer(query)
        if len(tokens) == 0:
            raise ValueError('Empty query')
        k = min(k, len(chunks))
        res, scores = retriever.retrieve([tokens], k=k, show_progress=False)
        for i in res[0]:
            c = chunks[i]
            print(
                f"{c['file_path']} "
                +
                "[{c['first_character_index']}:{c['last_character_index']}]")
    except (OSError, FileNotFoundError):
        raise ValueError('Index file not Found.')

    def search_dataset(
        dataset_path: str = 'data/datasets/AnsweredQuestions/',
        k: int = 5,
        save_dir: str = '/data/output/search_results',
        save_processed='/data/processed/chunks.json'
    ) -> None:
        """search from the input datasets"""

        with open(dataset_path, encoding='utf-8') as f:
            questions = json.load(f)
        with open(save_processed, encoding='utf-8') as f:
            load_index = json.load(f)

        for question in tqdm(questions,
                             desc='answare question',
                             unit='question'):
            pass
