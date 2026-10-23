from .utils import ft_open

from .models import MinimalSource


class Augmentation:
    def __init__(self) -> None:
        """Start Up the augmentation pipeLine"""
        self._context = ''
        self.cache: dict[str, str] = {}

    def read_sources(self, sources: list[MinimalSource]) -> None:
        """Read the resources from the query"""

        context = ''
        for i, elem in enumerate(sources):
            if elem.file_path not in self.cache:
                self.cache[elem.file_path] = ft_open(elem.file_path)
            context += f'[{i + 1}]: {elem.file_path}\n'
            context += self.cache[elem.file_path][
                elem.first_character_index:elem.last_character_index
            ]
            context += '\n'
        self._context = context

    def build_prompt(self, query: str) -> list[dict[str, str]]:
        """Turn retrieved sources into chat messages for the LLM"""

        prompt = [
            {
                'role': 'system',
                'content': (
                    'You answer questions about the vLLM codebase. '
                    'Use ONLY the sources below. If they do not contain '
                    'the answer, say so.')
            },
            {
                'role': 'user',
                'content': f'{self._context}\nQuestion: {query}'
            }
        ]

        return prompt
