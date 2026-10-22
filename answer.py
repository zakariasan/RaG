from .search import search
from .augmentation import Augmentation

from .generation impor Generator


def answer(query: str, k: int = 10) -> None:

    sources = search(query, k)

    a = augmentation()
    a.read_sources(sources)
    msg = a.build_prompt(query)

    print(Generator().generate(msg))

