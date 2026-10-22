from .utils import ft_open

from .models import MinimalSource


class Augmentaion:
    def __init__(self) -> None:
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
        self._context = context

    def build_prompt(self) -> list[dict[str, str]]:
        """Build prom for the llm can give us ans"""

        prompt = [
            {
                'role': 'system',
                'content': (
                    'You answer questions about the vLLM codebase.'
                    'Use ONLY the sources below. If they do not contain '
                    'the answer, say so.')
            },
            {
                'role': 'user',
                'content': self._context
            }
        ]

        return prompt
