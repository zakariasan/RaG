import fire
from python_file_chunker import chunk_pfile
from txt_file_chunker import chunk_txt_file
from utils import ft_open
import os


def should_skip(path):
    ignore_files = ft_open(p)
    if path.startswith('./.git') or path in to_skip:
        return True
    return False


def index_machine(main_path, max_size):
    chunk_meta = []      # will hold (file_path, a, b)
    chunk_texts = []     # will hold the chunk's text

    ignore_files = ft_open()   

    for path, folder, file in os.walk(main_path):
        if should_skip(path):
            continue
        if path.endswith('.py'):
            print("........>python file here to chunk")
            # pairs = chunk_pfile(path, 2000)
        elif path.endswith('.md'):
            print(".>txt file to chunk here......<")
            # pairs = chunk_txt_file(path, 2000)
        else:
            continue


def hello(name="World"):
    return "Hello %s!" % name


def index_cli(max_chunk_size=5):
    return f"max chunks in indexing is {max_chunk_size}"


def chunk_cli(file, max_size):
    # import pudb; pudb.set_trace()
    res = chunk_pfile(file, max_size)
    print(res)


if __name__ == '__main__':
    # fire.Fire(hello)
    fire.Fire(chunk_cli)
