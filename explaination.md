# explaination.md — how the answer-generation part works

How the "G" in RAG works in this project: what `torch` and `transformers` are for, what Qwen3-0.6B
does step by step, how it fits into our files, and how to make it fast. Read this before writing
`src/rag_flow.py`. What is left to do is in `task.md` section 5; what is built is in `completed.md`.

---

# 1. The two libraries — why `transformers` and `torch`

| Library | Role | Analogy |
|---|---|---|
| **torch** (PyTorch) | The math engine. Qwen is ~600 million numbers (weights) in a file; generating text is matrix multiplication over them. torch does those multiplications on CPU (or GPU). It knows nothing about language. | the engine |
| **transformers** (Hugging Face) | Sits on top of torch. Knows the Qwen architecture, downloads the weights from the Hub, provides the **tokenizer** (text ↔ numbers) and `generate()` (the token-by-token loop). | the car around the engine |

You need both: transformers describes the model, torch runs it.

Install (CPU machine, no GPU here — 19 GB RAM, plenty for 0.6B):
```
uv add transformers torch
```
The default `torch` wheel on Linux pulls CUDA libraries (several GB) that a CPU-only machine never
uses. The uv guide below shows how to point at the CPU-only index instead.

The first run downloads the weights (~1.2 GB) into `~/.cache/huggingface/hub/`. Later runs read
them from there, offline.

**Read more**
- PyTorch install selector (pick CPU): https://pytorch.org/get-started/locally/
- uv + PyTorch, CPU-only index: https://docs.astral.sh/uv/guides/integration/pytorch/
- transformers quick tour: https://huggingface.co/docs/transformers/quicktour
- Qwen3-0.6B model card (recommended settings, thinking mode): https://huggingface.co/Qwen/Qwen3-0.6B

---

# 2. How an LLM answers — the general mechanism

An LLM never "looks things up". It does one thing: **given a sequence of tokens, predict the next
one**. Repeat that in a loop and you get text.

```
"What is vLLM?"  --tokenizer-->  [3838, 374, 348, 4086, 44, 30]
```

1. **Tokenize** — text → integer ids. Roughly ¾ of a word per token. Code tokenizes worse than
   prose (symbols, indentation).
2. **Forward pass** — the ids go through the 28 transformer layers. Output: a score for every
   token in the vocabulary (~150 000 candidates) saying how likely it is to come next.
3. **Pick one** — greedy decoding takes the highest-scoring token. Same input → same output.
4. **Append and repeat** — the new token joins the sequence; predict again.
5. **Stop** — at the end-of-turn token `<|im_end|>`, or at `max_new_tokens`.
6. **Decode** — ids → text.

So the model only knows its frozen training data **plus whatever is in the prompt**. That is
the whole reason RAG exists: we put the right vLLM snippets in the prompt, so the "next most likely
words" are the ones that repeat those snippets back as an answer.

**Read more**
- The Illustrated Transformer (visual, best first read): https://jalammar.github.io/illustrated-transformer/
- 3Blue1Brown, "Transformers, the tech behind LLMs" (video): https://www.youtube.com/watch?v=wjZofJX0v4M
- Karpathy, "Let's build GPT from scratch" (video, deep): https://www.youtube.com/watch?v=kCc8FmEb1nY
- Hugging Face course, tokenizers chapter: https://huggingface.co/learn/llm-course/chapter6/1
- The original RAG paper (Lewis et al., 2020): https://arxiv.org/abs/2005.11401

---

# 3. One real question through our project, step by step

Question from `dataset_docs_public.json`:
*"What HTTP endpoint is used to dynamically load a LoRA adapter in vLLM?"*

## Which file does what

```
index.py          (done)  chunks + BM25 index on disk
search.py         (done)  question  ->  top-k MinimalSource (path + char range)
utils.ft_open     (done)  read a file
rag_flow.py       (TODO)  sources -> text -> prompt -> Qwen -> answer
__main__.py       (TODO)  register `answer` and `answer_dataset`
models.py         (done)  StudentSearchResultsAndAnswer for the output JSON
```

Qwen lives only in `rag_flow.py`. Everything before it already works and is verified.

## Step 1 — Retrieve (done)

`search` returns **locations**, not text:
```
1. data/raw/vllm-0.10.1/docs/features/lora.md  [3843:5716]
2. data/raw/vllm-0.10.1/docs/features/lora.md  [5716:7714]
...
```

## Step 2 — Locations become text

```python
text = ft_open(src.file_path)[src.first_character_index:src.last_character_index]
```
Source 1 contains `## Dynamically serving LoRA Adapters ...` and, further in, the
`/v1/load_lora_adapter` endpoint. The answer is now in hand — the model just has to read it.

## Step 3 — Build the prompt (just a Python string)

```
SYSTEM: You answer questions about the vLLM codebase. Use ONLY the sources
below. If they do not contain the answer, say so.

USER:
[1] data/raw/vllm-0.10.1/docs/features/lora.md
<text of chunk 1>

[2] data/raw/vllm-0.10.1/docs/features/lora.md
<text of chunk 2>

Question: What HTTP endpoint is used to dynamically load a LoRA adapter in vLLM?
```
This is the "prompt strategy" the subject grades (VI.3). Sources numbered, file path on each (it is
context too), question **last** so it is the freshest thing the model read.

## Step 4 — Tokenize and fit the budget

A 2000-character chunk ≈ 500–600 tokens. Five chunks + rules + question ≈ 3000 tokens.
Count with the model's own tokenizer: `len(tok(text).input_ids)`. If over budget, **drop source 5,
then 4, …** — never cut a source in half; half a function misleads more than it helps.

## Step 5 — Chat template

Qwen was trained on a fixed conversation format. `apply_chat_template` produces it:
```
<|im_start|>system
...rules...<|im_end|>
<|im_start|>user
[1] ... Question: ...<|im_end|>
<|im_start|>assistant
```
The trailing `assistant` line (`add_generation_prompt=True`) means "your turn". Without the
template the model does not know it is supposed to answer and tends to ramble.

**Qwen3 specific:** by default it first writes a `<think>...</think>` reasoning block. Pass
`enable_thinking=False` to `apply_chat_template` to skip it.

## Step 6 — Generate (the loop from section 2)

```
read all ~3000 prompt tokens once            (prefill)
predict "The"                 append         (decode, 1 token per step)
predict " endpoint"           append
predict " is"                 append
predict " `/v1/load_lora_adapter`" ...
predict <|im_end|>            STOP
```

## Step 7 — Keep only the new tokens

`generate` returns **prompt + answer** in one tensor. Slice off the prompt length, decode the rest:
```
"The endpoint is /v1/load_lora_adapter, called with a POST request ..."
```

## Step 8 — Save

One `MinimalAnswer(question_id, question, retrieved_sources, answer)` per question, all wrapped
in `StudentSearchResultsAndAnswer(search_results=[...], k=k)`, written with `model_dump_json`.

## Minimal shape, for understanding

```python
tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-0.6B")            # once
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3-0.6B")   # once

msgs = [{"role": "system", "content": RULES},
        {"role": "user", "content": sources_text + "\n\nQuestion: " + question}]
text = tok.apply_chat_template(msgs, tokenize=False,
                               add_generation_prompt=True,
                               enable_thinking=False)
ids = tok(text, return_tensors="pt")
with torch.inference_mode():
    out = model.generate(**ids, max_new_tokens=256, do_sample=False)
answer = tok.decode(out[0][ids.input_ids.shape[1]:], skip_special_tokens=True)
```

**Read more**
- Chat templates: https://huggingface.co/docs/transformers/main/en/chat_templating
- Generation with LLMs (tutorial, common pitfalls): https://huggingface.co/docs/transformers/main/en/llm_tutorial
- `generate()` parameters and decoding strategies: https://huggingface.co/docs/transformers/main/en/generation_strategies
- Prompting guide for RAG / grounding: https://www.promptingguide.ai/techniques/rag

---

# 4. Why a class — how the method fits

Loading the model takes several seconds and happens **once**. Answering happens **100 times**.
So split the two:

```
class Generator:
    __init__()               load tokenizer + model ONCE, keep as self.tok, self.model
    read_sources(srcs)       step 2
    build_prompt(q, texts)   step 3 + budget of step 4
    answer(q, srcs) -> str   steps 3-7
```

The commands reuse it:

```
answer "<query>" --k     search()  ->  Generator().answer()  ->  print

answer_dataset           read the search_dataset JSON (NOT the index, no retrieval here)
                         gen = Generator()                 once
                         for each question (tqdm):
                             gen.answer(...)  ->  MinimalAnswer
                         write StudentSearchResultsAndAnswer
                         print "Loaded <n> questions" / "Saved student_search_results_and_answer to <path>"
```

`answer_dataset` reuses what `search_dataset` already saved, so retrieval and generation stay
separate stages — the RAG separation from `completed.md` 1.1. Subject V.4 allows this class to be
a plain class (service/orchestration), not pydantic.

---

# 5. Where time goes, and how to go faster

Two phases:
- **Prefill** — reading the prompt once. Grows with prompt length, but tokens are processed in
  parallel, so it is the cheaper phase.
- **Decode** — writing the answer one token at a time; every token is a full pass through the
  600 M weights. Grows with answer length. **The slow phase on CPU.**

| Trick | Why it helps |
|---|---|
| `enable_thinking=False` | Qwen3 otherwise writes hundreds of `<think>` tokens before the answer. Biggest single win. |
| `max_new_tokens` ≈ 200–256 | Caps the slow decode phase. |
| Top 3–5 sources, ~2–3k tokens | Shorter prefill. R@5 is already 0.830; sources 6–10 add cost for little gain. |
| Load the model once | `__init__`, never inside the loop. |
| `torch.inference_mode()` | Disables gradient tracking (training only). Less memory, a bit faster. |
| `do_sample=False` | Greedy: deterministic, slightly cheaper than sampling. |
| CPU torch wheel | Smaller install; the CUDA build does nothing on this machine. |
| KV cache | Already on by default: past tokens' attention results are kept, so each new token does not recompute the whole prompt. |
| Batching (later, optional) | Several questions per `generate` call. Needs left padding; skip at first. |

Expect roughly 5–20 s per question on CPU → 10–30 min for 100 questions. That is why the subject
requires tqdm on this loop.

**Read more**
- KV cache explained: https://huggingface.co/docs/transformers/main/en/kv_cache
- `torch.inference_mode`: https://docs.pytorch.org/docs/stable/generated/torch.inference_mode.html
- LLM inference optimization (transformers docs): https://huggingface.co/docs/transformers/main/en/llm_optims

---

# 6. Suggested build order

1. `read_sources` + `build_prompt` only — **print the prompt**, no model. Read it: is the right
   text there? Are the paths there? Is the question last?
2. Add the model: `answer` on one question from the command line. Check the answer against the
   ground truth `answer` field in `AnsweredQuestions/`.
3. Tune the prompt on 5–10 questions (rules wording, number of sources).
4. `answer_dataset` with tqdm, write the JSON, check it parses back as
   `StudentSearchResultsAndAnswer`.

# 7. Questions to be able to answer at the defense

- Why the model gets locations' **text** and never the index or the corpus.
- What the chat template is and what happens without it.
- Why `enable_thinking=False`, and what it costs (less reasoning, much faster).
- Prefill vs decode — which one `max_new_tokens` controls.
- Why sources are dropped whole instead of truncated.
- Why the model is loaded once, in `__init__`.
- Why greedy decoding (`do_sample=False`) — reproducible answers.
