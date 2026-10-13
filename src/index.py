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
    """ Scrape Every git file to igonore it
    """
    try:
        tmp = ft_open('./.gitignore')
    except (FileNotFoundError):
        return []
    res = []
    for item in tmp.splitlines():
        if not item.strip().startswith('#'):
            res.append(item.strip())
    res.append('.git')
    res.append('.gitignore')
    return res


def skip_file(path):
    """skip files in .gotignore"""
    to_skip = git_file()
    return path in to_skip


def skip_folder(path):
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
) -> tuple[list[tuple[str, int, int]], list[str]]:
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

    for fil in tqdm(files_work, desc='Chunking:', unit='file'):
        try:
            if fil.endswith('.py'):
                pairs = chunk_pfile(fil, max_size)
            else:
                pairs = chunk_txt_file(fil, max_size)
            src = ft_open(fil)
            for (start, end) in pairs:
                minimal_src = MinimalSource(fil, start, end)
                chunk_meta.append(minimal_src)
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
    return chunk_meta

def tokenizer(string: str) -> list[str]:
    """ Clearify meaning with waht we want for bm25"""
    res = []
    words = re.findall(r'[A-Za-z0-9]+', string)
    for item in words:
        res.append(item.lower())
        parts = re.findall(r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+', item)
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

    chunk_meta = index_machine(files, max_chunk_size)
    os.makedirs(save_dir, exist_ok=True)
    chunks_path = os.path.join(save_dir, 'chunks.json')
    with open(chunks_path, 'w', encoding='utf-8') as file_opend:
        json.dump(
            [item.model_dump() for item in chunk_meta],
            file_opend,
            indent=4)

#    corpus_tokens = [tokenizer(t) for t in tqdm(txt, desc='Tokenizing:')]
#    retriever = bm25s.BM25()
#    retriever.index(corpus_tokens)
#    retriever.save(save_dir)
    print("Ingestion complete! Indexed ", end='')
    print(f"chunks under {len(chunk_meta)}")
