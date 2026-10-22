from .utils import ft_open
from .search import search

from .model import MinimalSource


class Augmentaion:
    def __init__(self):
        """Start Up the augmentation pipeLine"""
        self._context = ''

    def read_sources(self, sources: list[MinimalSource]) -> None:
        """Read the resources from the query taht we have"""

        context = ''
        for i, elem in enumerate(sources):
            file = ft_open(elem.file_path)
            context += f'file[{i}]: {elem.file_path}\n'
            context += file[
                elem.first_character_index:elem.last_character_index]
            context += '\n'
        self._context = context + f'\nQuestion: {query}'

    def build_prompt(self) -> str:
        """Build prom for the llm can give us ans"""
        prompt = (
            'SYSTEM: You answer questions about the vLLM codebase.'
            'Use ONLY the sources below. If they do not contain '
            f'the answer, say so.\n'
            'USER:\n{self._context}'
        )

        return prompt

