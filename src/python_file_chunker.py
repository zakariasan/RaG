import ast
from .utils import get_offsets, hard_split


def chunk_nodes(nodes, start, end, src_file, line_offsets, max_size):
    starts = []
    for node in nodes:
        start_line = node.lineno
        decorators = getattr(node, 'decorator_list', [])
        if decorators:
            start_line = decorators[0].lineno
        starts.append((line_offsets[start_line - 1], node))

    if not starts or starts[0][0] > start:
        starts.insert(0, (start, None))
    starts.append((end, None))

    pairs = []
    for (s, node), (e, _) in zip(starts, starts[1:]):
        if s < e:
            pairs.append((s, e, node))

    cuts = []
    curr = None
    for (s, e, node) in pairs:
        if e - s > max_size:
            if curr:
                cuts.append(curr)
                curr = None
            if node is not None and getattr(node, 'body', None):
                cuts.extend(chunk_nodes(node.body, s, e,
                                        src_file, line_offsets, max_size))
            else:
                cuts.extend(hard_split(s, e, line_offsets, max_size))
        elif curr is None:
            curr = (s, e)
        elif e - curr[0] <= max_size:
            curr = (curr[0], e)
        else:
            cuts.append(curr)
            curr = (s, e)
    if curr:
        cuts.append(curr)
    return cuts


def chunk_pfile(filename, max_size):
    """ try to chunks a file """
    with open(filename, 'r', encoding='utf-8') as f:
        src_file = f.read()
    tree = ast.parse(src_file)
    line_offsets = get_offsets(src_file.splitlines(keepends=True))
    chunks = chunk_nodes(tree.body, 0, len(src_file),
                         src_file, line_offsets, max_size)
    return chunks
    # assert ''.join(src_file[a:b] for a, b in chunks) == src_file
    # res = []
    # for chunk in chunks:
    #    res.append(src_file[chunk[0]: chunk[1]])
    # return res
