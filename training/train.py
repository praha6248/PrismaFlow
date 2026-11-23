"""LoRA fine-tune of a copy of Gemma 3 instruct on the PrismaFlow Deliver tasks and UX knowledge.

Loss is computed on the assistant answer only. Held-out losses of the base and the tuned model are
written to out/<name>/losses.json; the merged bf16 model is saved to out/<name>/merged for GGUF conversion.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import shutil
import time
from pathlib import Path

import torch
from peft import LoraConfig, PeftModel, get_peft_model
from torch.nn import functional as F
from transformers import AutoTokenizer, BitsAndBytesConfig, Gemma3ForConditionalGeneration, get_cosine_schedule_with_warmup

from distill_mc import near_quiz

ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data"
OUT = ROOT / "out"
TARGETS = r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)"


def load(name: str) -> list[dict]:
    path = DATA / name
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def encode(tokenizer, example: dict, max_len: int) -> dict | None:
    """Tokenise one chat example with labels masked outside the assistant answer."""
    messages = example["messages"]
    prompt = tokenizer.apply_chat_template(messages[:-1], tokenize=False, add_generation_prompt=True)
    answer = messages[-1]["content"] + "<end_of_turn>\n"
    prompt_ids = tokenizer(prompt, add_special_tokens=False)["input_ids"]
    answer_ids = tokenizer(answer, add_special_tokens=False)["input_ids"]
    ids = prompt_ids + answer_ids
    if len(ids) > max_len:
        return None
    return {"input_ids": ids, "labels": [-100] * len(prompt_ids) + answer_ids, "task": example["task"]}


def batches(items: list[dict], size: int, pad: int):
    """Yield padded tensor batches."""
    for start in range(0, len(items), size):
        group = items[start:start + size]
        width = max(len(i["input_ids"]) for i in group)
        ids = torch.full((len(group), width), pad)
        labels = torch.full((len(group), width), -100)
        mask = torch.zeros((len(group), width), dtype=torch.long)
        for row, item in enumerate(group):
            n = len(item["input_ids"])
            ids[row, :n] = torch.tensor(item["input_ids"])
            labels[row, :n] = torch.tensor(item["labels"])
            mask[row, :n] = 1
        yield ids, labels, mask


class Output:
    def __init__(self, loss):
        self.loss = loss


def forward(model, ids, labels, mask):
    """Answer-token loss with logits computed only where an answer token is predicted (batch size 1)."""
    ids, labels, mask = ids.cuda(), labels.cuda(), mask.cuda()
    keep = (labels[0, 1:] != -100).nonzero().squeeze(-1)
    out = model(input_ids=ids, attention_mask=mask, token_type_ids=torch.zeros_like(ids), logits_to_keep=keep)
    logits = out.logits[0].float()
    return Output(F.cross_entropy(logits, labels[0, keep + 1]))


@torch.no_grad()
def evaluate(model, items: list[dict], pad: int) -> dict[str, float]:
    """Mean answer-token loss per task."""
    model.eval()
    sums: dict[str, list[float]] = {}
    for item in items:
        ids, labels, mask = next(batches([item], 1, pad))
        out = forward(model, ids, labels, mask)
        tokens = int((labels[:, 1:] != -100).sum())
        bucket = sums.setdefault(item["task"], [0.0, 0])
        bucket[0] += float(out.loss) * tokens
        bucket[1] += tokens
    model.train()
    return {task: round(total / count, 4) for task, (total, count) in sums.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--epochs", type=float, default=2.0)
    parser.add_argument("--lr", type=float, default=2e-4)
    parser.add_argument("--rank", type=int, default=16)
    parser.add_argument("--accum", type=int, default=8)
    parser.add_argument("--max-len", type=int, default=2048)
    parser.add_argument("--knowledge-share", type=float, default=0.35)
    parser.add_argument("--mc-share", type=float, default=0.0, help="share of the knowledge slots given to multiple-choice items")
    parser.add_argument("--base", default="gemma-3-4b-it")
    parser.add_argument("--name", default="")
    parser.add_argument("--train-file", default="train.jsonl")
    parser.add_argument("--qlora", action="store_true", help="4-bit base weights for training when the GPU is shared; merged into bf16 on the CPU")
    parser.add_argument("--test-files", nargs="+", default=["test.jsonl", "knowledge_test.jsonl"])
    args = parser.parse_args()
    base = ROOT / "weights" / args.base
    out = OUT / args.name if args.name else OUT

    rng = random.Random(0)
    torch.manual_seed(0)
    tokenizer = AutoTokenizer.from_pretrained(base)
    pad = tokenizer.pad_token_id
    tasks = load(args.train_file)
    extra = load("knowledge_mc_train.jsonl") if args.mc_share else []
    knowledge = load("knowledge_train.jsonl") + [x for x in extra if x["task"] == "knowledge"]
    if args.mc_share:
        knowledge = [x for x in knowledge if not near_quiz(x["messages"][1]["content"])]
    choices = [x for x in extra if x["task"] == "knowledge_mc"]
    cap = int(len(tasks) * args.knowledge_share / (1 - args.knowledge_share))
    rng.shuffle(knowledge)
    rng.shuffle(choices)
    mc_cap = min(len(choices), int(cap * args.mc_share))
    train_raw = tasks + choices[:mc_cap] + knowledge[: cap - mc_cap]
    train = [e for e in (encode(tokenizer, x, args.max_len) for x in train_raw) if e]
    test = [e for e in (encode(tokenizer, x, args.max_len) for name in args.test_files for x in load(name)) if e]
    print(f"train {len(train)} (tasks {len(tasks)}, multiple choice {mc_cap}, knowledge {min(cap - mc_cap, len(knowledge))}), test {len(test)}, "
          f"longest {max(len(e['input_ids']) for e in train)} tokens", flush=True)

    if args.qlora:
        quant = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
        model = Gemma3ForConditionalGeneration.from_pretrained(base, dtype=torch.bfloat16, attn_implementation="eager", quantization_config=quant, device_map={"": 0})
    else:
        model = Gemma3ForConditionalGeneration.from_pretrained(base, dtype=torch.bfloat16, attn_implementation="eager").cuda()
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    model.config.use_cache = False
    config = LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, target_modules=TARGETS, task_type="CAUSAL_LM")
    model = get_peft_model(model, config)
    model.print_trainable_parameters()

    out.mkdir(parents=True, exist_ok=True)
    with model.disable_adapter():
        base_losses = evaluate(model, test, pad)
    print("base held-out loss", base_losses, flush=True)

    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=args.lr, weight_decay=0.0)
    steps = math.ceil(len(train) * args.epochs / args.accum)
    scheduler = get_cosine_schedule_with_warmup(optimizer, max(1, steps // 20), steps)
    model.train()
    log = []
    step, seen, running = 0, 0, 0.0
    started = time.time()
    order: list[dict] = []
    while step < steps:
        if not order:
            order = train[:]
            rng.shuffle(order)
        item = order.pop()
        ids, labels, mask = next(batches([item], 1, pad))
        loss = forward(model, ids, labels, mask).loss / args.accum
        loss.backward()
        running += float(loss)
        seen += 1
        if seen % args.accum == 0:
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            optimizer.step()
            scheduler.step()
            optimizer.zero_grad(set_to_none=True)
            step += 1
            log.append({"step": step, "loss": round(running, 4), "lr": scheduler.get_last_lr()[0]})
            if step % 5 == 0 or step == steps:
                print(f"step {step}/{steps} loss {running:.4f} {time.time() - started:.0f}s "
                      f"mem {torch.cuda.max_memory_allocated() / 2**30:.1f} GiB", flush=True)
            running = 0.0

    tuned_losses = evaluate(model, test, pad)
    print("tuned held-out loss", tuned_losses, flush=True)
    model.save_pretrained(out / "adapter")
    (out / "losses.json").write_text(json.dumps({
        "args": vars(args),
        "train_examples": len(train),
        "test_examples": len(test),
        "steps": steps,
        "minutes": round((time.time() - started) / 60, 1),
        "peak_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "base": base_losses,
        "tuned": tuned_losses,
        "log": log,
    }, indent=1), encoding="utf-8")

    if args.qlora:
        del model, optimizer
        torch.cuda.empty_cache()
        full = Gemma3ForConditionalGeneration.from_pretrained(base, dtype=torch.bfloat16, low_cpu_mem_usage=True)
        merged = PeftModel.from_pretrained(full, out / "adapter").merge_and_unload()
    else:
        merged = model.merge_and_unload()
    target = out / "merged"
    if target.exists():
        shutil.rmtree(target)
    merged.save_pretrained(target, safe_serialization=True)
    tokenizer.save_pretrained(target)
    for name in ("tokenizer.model", "preprocessor_config.json", "processor_config.json", "chat_template.json", "chat_template.jinja", "generation_config.json"):
        if (base / name).exists():
            shutil.copy(base / name, target / name)
    print(f"merged model -> {target}")


if __name__ == "__main__":
    main()
