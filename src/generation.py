class Generator:

    def __init__(self, name: str = 'Qwen/Qwen3-0.6B') -> None:
        self.model_name = name

    def generate(self, msg: list[dict]) -> str:

        return f'{msg}'
