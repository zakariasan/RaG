import fire
import ast


def get_offsets(lines):
    line_offsets = [0]
    for i, item in enumerate(lines):
        offset = line_offsets[i] + len(item)
        line_offsets.append(offset)
    return line_offsets


def chunk_pfile(filename, max_size):
    """ try to chunks a file """
    with open(filename, 'r') as f:
        src_file = f.read()
    tree = ast.parse(src_file)
    nodes = tree.body
    lines = src_file.splitlines(keepends=True)
    line_offsets = get_offsets(lines)
    cut_points = []
    for node in nodes:
        start_line = node.lineno
        decorators = getattr(node, 'decorator_list', [])
        if decorators:
            start_line = decorators[0].lineno
        else:
            start_line = node.lineno
        cut_points.append(line_offsets[start_line - 1])

    pair_offsets = list(zip(cut_points, cut_points[1:])) 

    print("line_offsets: ", line_offsets)
    print("cut_pts: ", cut_points)
    print("pairs: ", pair_offsets)
    print(lines)

    content = lines
    chunks = []
    curr = []
    len_curr = 0

    for item in nodes:
        elem = []
        start = item.lineno - 1
        end = item.end_lineno
        elem_to = content[start] if start + 1 == end else content[start: end]
        elem.append(elem_to)
        for line in elem:
            if len(line) + len_curr <= max_size:
                curr.append(line)
                len_curr += len(line)
            else:
                if curr:
                    chunks.append(curr)
                    curr = []
                    len_curr = 0
                else:
                    chunks.append(line[:max_size])
                    curr = line[max_size:]
                    len_curr = len(curr)

    if curr:
        chunks.append(curr)
    print(chunks)


"""
for node in tree.body:
        print("---------------------------------")
        print(ast.get_source_segment(src_file, node))
        print("---------------------------------")
        start_line = node.lineno - 1
        end_line = node.end_lineno
        node_lines = lines[start_line: end_line]
        node_code = '\n'.join(node_lines)
        node_size = len(node_code)

        if node_size > max_size:
            if curr:
                chunks.append("\n".join(curr))
                curr = []
                len_curr = 0
                continue

        if len_curr + node_size > max_size and curr:
            chunks.append("\n".join(curr))
            curr = [node_code]
            len_curr = node_size
        else:
            curr.append(node_code)
            len_curr += node_size
    if curr:
        chunks.append('\n'.join(curr))
    return chunks
"""


def hello(name="World"):
    return "Hello %s!" % name


def index_cli(max_chunk_size=5):
    return f"max chunks in indexing is {max_chunk_size}"


def chunk_cli(file, max_size):
    #import pudb; pudb.set_trace()
    chunk_pfile(file, max_size)


if __name__ == '__main__':
    # fire.Fire(hello)
    fire.Fire(chunk_cli)
