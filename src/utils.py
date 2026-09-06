def ft_open(filename):
    """Open a file """
    with open(filename, 'r', encoding='utf-8') as f:
        src_file = f.read()
    return src_file


def get_offsets(lines):
    line_offsets = [0]
    for i, item in enumerate(lines):
        offset = line_offsets[i] + len(item)
        line_offsets.append(offset)
    return line_offsets


def hard_split(s, e, line_offsets, max_size):
    """breakk into our string"""
    chunk_start = s
    if e - s <= max_size:
        return [(s, e)]
    elem = [off for off in line_offsets if s < off < e]
    bound = elem + [e]
    res = []
    i = 0
    while chunk_start < e:
        last_good = None
        while i < len(bound) and bound[i] - chunk_start <= max_size:
            last_good = bound[i]
            i += 1
        if last_good is not None:
            res.append((chunk_start, last_good))
            chunk_start = last_good
        else:
            res.append((chunk_start, chunk_start + max_size))
            chunk_start += max_size
    return res
