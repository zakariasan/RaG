import fire
import ast


def chunk_pfile(filename, max_size):
    """ try to chunks a file """
    with open(filename, 'r') as f:
        src_file = f.read()
    tree = ast.parse(src_file)
    nodes = ast.iter_child_nodes(tree)
    content = src_file.splitlines(keepends=True)
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
