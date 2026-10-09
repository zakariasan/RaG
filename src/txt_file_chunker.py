from .utils import get_offsets, hard_split


def chunk_txt_file(filename, max_size):
    """ try to chunks a text file """
    with open(filename, 'r', encoding='utf-8') as f:
        src_file = f.read()
    line_offsets = get_offsets(src_file.splitlines(keepends=True))
    chunks = hard_split(0, len(src_file), line_offsets, max_size)
    return chunks
