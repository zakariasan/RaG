import fire
from python_file_chunker import chunk_pfile


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
