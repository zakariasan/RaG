from .utils import get_offsets, hard_split
from markdown_chunker import MarkdownChunkingStrategy


def chunk_txt_file(filename: str, max_size: int) -> list[tuple[int, int]]:
    """ try to chunks a text file """
    # with open(filename, 'r', encoding='utf-8') as f:
    #    src_file = f.read()
    line_offsets = get_offsets(filename.splitlines(keepends=True))
    chunks = hard_split(0, len(filename), line_offsets, max_size)
    return chunks


def chunk_md_file(
    src_file: str,
    max_size: int,
    strategy: MarkdownChunkingStrategy
) -> list[tuple[int, int]]:
    """chunk md file into chunks"""

    # with open(filename, 'r', encoding='utf-8') as f:
    #    src_file = f.read()
    chunks = strategy.chunk_markdown(src_file)
    offset = 0
    arr_chunks = []
    for chunk in chunks:
        start = offset
        end = len(chunk)
        offset = end
        arr_chunks.append((start, end))
    return arr_chunks
