import torch
from transformers import AutoModelForCausalLM, AutoTokenizer

from typing import Any


class Generator:
    def __init__(self, name: str = 'Qwen/Qwen3-0.6B') -> None:
        """Generating Answer from llms"""
        self.model_name = name
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        self.model: Any = AutoModelForCausalLM.from_pretrained(
            self.model_name,
            dtype=(torch.bfloat16 if torch.cuda.is_available()
                   else torch.float32)
        )
        self.model.eval()

    def generate(
        self,
        msg: list[dict[str, str]],
        max_new_tokens: int = 128
    ) -> Any:
        """Return the msg from llm"""

        text = self.tokenizer.apply_chat_template(
            msg,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=False
        )

        # if not isinstance(text, str):
        #    raise TypeError("Expected chat template to return a string")

        ids = self.tokenizer(text, return_tensors='pt')
        with torch.inference_mode():
            out = self.model.generate(
                **ids,
                max_new_tokens=max_new_tokens,
                do_sample=False)

        new = out[0][ids[
            'input_ids'
        ].shape[1]:]
        return self.tokenizer.decode(
            new,
            skip_special_tokens=True
        ).strip()

    #    if not isinstance(answering, str):
    #        raise TypeError("Expected decode template to return a string")
    #    return answering.strip()
