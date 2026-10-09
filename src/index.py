from .python_file_chunker import chunk_pfile
from .txt_file_chunker import chunk_txt_file
from .utils import ft_open
import os
import fnmatch
import re
import bm25s
import json
from tqdm import tqdm


def git_file() -> list[str]:
    """ Scrape Every git file to igonore it

    """
    try:
        tmp = ft_open('./.gitignore')
    except (FileNotFoundError, Exception):
        return []
    res = []
    for item in tmp.splitlines():
        if not item.strip().startswith('#'):
            res.append(item.strip())
    res.append('.git')
    res.append('.gitignore')
    return res


def skip_file(path):
    to_skip = git_file()
    if path in to_skip:
        return True
    return False


def skip_folder(path):
    path = path.split('/')[-1]
    to_skip = git_file()
    if path + '/' in to_skip:
        return True
    return False


def is_ignored(name: str, patterns: list[str]) -> bool:
    """ Replace is ignored file or folder deppend on """
    for item in patterns:
        pat = item.strip('/').removesuffix('/*')
        if fnmatch.fnmatch(name, pat):
            return True
    return False

def index_machine(main_path: str, max_size: int) -> tuple[list[tuple[str, int, int]], list[str]]:
    chunk_meta = []      # will hold (file_path, a, b)
    chunk_texts = []     # will hold the chunk's text

    pattern = git_file()
    space = ''
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
                chunk_meta.append((fil, start, end))
                chunk_texts.append(src[start: end])
        except (SyntaxError, UnicodeDecodeError, OSError):
            continue
    return chunk_meta, chunk_texts


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
    save_dir: str = './data/processed/'
) -> None:
    """Chunk file into chunks and index it depend on the chunk """

    if max_chunk_size <= 0:
        raise ValueError("max_chunk_size must be positive")
    meta, txt = index_machine(files, max_chunk_size)
    os.makedirs(save_dir, exist_ok=True)
    chunks_path = os.path.join(save_dir, 'chunks.json')
    with open(chunks_path, 'w', encoding='utf-8') as file_opend:
        json.dump([{'file_path': f, 'first_character_index': a, 'last_character_index': b}
                   for f, a, b in meta], file_opend)

    corpus_tokens = [tokenizer(t) for t in tqdm(txt, desc='Tokenizing:')]
    retriever = bm25s.BM25()
    retriever.index(corpus_tokens)
    retriever.save(save_dir)
    print("Ingestion complete! Indexed ", end='')
    print(f"chunks under {len(meta)}")
