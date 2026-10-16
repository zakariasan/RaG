import fire

from .index import index
from .search import search

if __name__ == '__main__':
    try:
        fire.Fire({'index': index, 'search': search})
    # except Exception as e:
    #    print(f"ERROR414: {e}")
    except KeyboardInterrupt:
        print('KeyboardInterrupt -_-!')
