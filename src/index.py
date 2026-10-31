import fnmatch
import json
import os
import re

import bm25s
from tqdm import tqdm

from .models import MinimalSource
from .python_file_chunker import chunk_pfile
from .txt_file_chunker import chunk_txt_file
from .utils import ft_open


def git_file() -> list[str]:
    """ Scrape Every git file to igonore it"""
    try:
        tmp = ft_open('./.gitignore')
    except (OSError):
        return []
    res = []
    for item in tmp.splitlines():
        if item.strip().startswith('#') or item.strip() == '':
            continue
        res.append(item.strip())
    res.append('.git')
    res.append('.gitignore')
    return res


def skip_file(path: str) -> bool:
    """skip files in .gotignore"""
    to_skip = git_file()
    return path in to_skip


def skip_folder(path: str) -> bool:
    """skip folders ignored by git"""
    path = path.split('/')[-1]
    to_skip = git_file()
    return path + '/' in to_skip


def is_ignored(name: str, patterns: list[str]) -> bool:
    """ Replace is ignored file or folder deppend on """
    for item in patterns:
        pat = item.strip('/').removesuffix('/*')
        if fnmatch.fnmatch(name, pat):
            return True
    return False


def index_machine(
    main_path: str,
    max_size: int
) -> tuple[list[MinimalSource], list[str]]:
    """machine that check if file can chunk it or no"""

    chunk_meta = []
    chunk_texts = []
    pattern = git_file()
    files_work = []

    for path, folder, files in os.walk(main_path):
        folder[:] = [d for d in folder if not is_ignored(d, pattern)]
        for file in files:
            if is_ignored(file, pattern):
                continue
            else:
                full_path = os.path.join(path, file)
                files_work.append(full_path)

    for fil in tqdm(files_work, desc='Chunking', unit=' file'):
        try:
            src = ft_open(fil)
            if fil.endswith('.py'):
                pairs = chunk_pfile(src, max_size)
            else:
                pairs = chunk_txt_file(src, max_size)
            for (start, end) in pairs:
                minimal_src = MinimalSource(
                    file_path=fil,
                    first_character_index=start,
                    last_character_index=end)
                chunk_meta.append(minimal_src)
                chunk_texts.append(src[start:end])
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
        # print(chunk_meta)
        # sorted(chunk_meta, key=lambda item: item.file_path)

    return chunk_meta, chunk_texts


def tokenizer(string: str) -> list[str]:
    """ Clearify meaning with waht we want for bm25"""
    res = []
    words = re.findall(r'[A-Za-z0-9]+', string)
    for item in words:
        res.append(item.lower())
        parts = re.findall(
            r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+', item
        )
        if len(parts) > 1:
            for part in parts:
                res.append(part.lower())
    return [ibm for ibm in res if len(ibm) > 1]


def index(
    max_chunk_size: int = 2000,
    files: str = 'data/raw',
    save_dir: str = 'data/processed/'
) -> None:
    """Chunk file into chunks and index it depend on the chunk """

    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be positive")

    try:

        chunk_meta, txt = index_machine(files, max_chunk_size)
        os.makedirs(save_dir, exist_ok=True)
        chunks_path = os.path.join(save_dir, 'chunks.json')
        with open(chunks_path, 'w', encoding='utf-8') as file_opend:
            json.dump(
                [item.model_dump() for item in chunk_meta],
                file_opend,
                indent=4
            )

    except (OSError):
        raise ValueError("Extract Chunks probleme.")
    corpus_tokens = [
        tokenizer(t) for t in tqdm(txt, desc='Tokenizing', unit=' chunk')]
    # corpus_tokens = bm25s.tokenize(''.join(txt))
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)
    retriever.save(save_dir)

    print(f"Ingestion complete! Indexed {len(chunk_meta)}", end='')
    print(f" chunks under {save_dir}")
