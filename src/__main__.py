import fire

from .index import index
from .search import (search, search_dataset)
from .evaluate import evaluate
from .answer import answer

if __name__ == '__main__':
    try:
        fire.Fire(
            {
                'index': index,
                'search': search,
                'search_dataset': search_dataset,
                'evaluate': evaluate,
                'answer': answer
            })
    except Exception as e:
        print(f"ERROR414: {e}")
    except KeyboardInterrupt:
        print('KeyboardInterrupt -_-!')
