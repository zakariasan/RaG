from src.retrieve import retrieve
from src.augmentation import Augmentation
q = 'What HTTP endpoint is used to dynamically load a LoRA adapter in vLLM?'
a = Augmentation()
a.read_sources(retrieve(q, k=5))
p = a.build_prompt(q)
for m in p:
    print('=====', m['role']); print(m['content'])
c = p[1]['content']
print('endpoint:', '/v1/load_lora_adapter' in c, '| question:', q in c)

