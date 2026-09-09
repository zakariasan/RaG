import fire
from python_file_chunker import chunk_pfile
from txt_file_chunker import chunk_txt_file
from utils import ft_open
import os


def git_file():
    tmp = ft_open('./.gitignore')
    if tmp and tmp != []:
        tmp.splitlines(keepends=True)
        res = []
        for item in tmp:
            if not tmp.startswith('#'):
                res.append(item)
        tmp += '.gitignore'
        return res
    return []


def skip_file(path):
    # path = path.split('/')[-1]
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

def index_machine(main_path, max_size):
    chunk_meta = []      # will hold (file_path, a, b)
    chunk_texts = []     # will hold the chunk's text

    space = ''
    for path, folder, files in os.walk(main_path):
        if path.startswith('./.git'):
            continue
        if skip_folder(path):
            continue
        for file in files:
            if skip_file(file):
                continue
            if file.endswith('.py'):
                print(f"{space}[{path}]{file}")
                # pairs = chunk_pfile(file, 2000)
            elif file:
                print(f"{space}[{path}]{file}<")
                # pairs = chunk_txt_file(file, 2000)
        space += '.>'


def hello(name="World"):
    return "Hello %s!" % name


def index_cli(max_chunk_size=5):
    return f"max chunks in indexing is {max_chunk_size}"


def chunk_cli(file, max_size):
    # import pudb; pudb.set_trace()
    # res = chunk_pfile(file, max_size)
    index_machine('./', max_size)


if __name__ == '__main__':
    # fire.Fire(hello)
    fire.Fire(chunk_cli)
