"""评测 Claude 模型在 Stage 2 (WaveJSON→Verilog) 上的表现。

调用 Anthropic API 对 117 个测试样本进行推理，保存结果为 JSONL。
后续用 wavedrom-llm 的 eval-verilog 进行仿真评分。

Usage:
    python scripts/eval_claude_stage2.py --model claude-sonnet-4-6
    python scripts/eval_claude_stage2.py --model claude-opus-4-6
"""
import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import anthropic
from tqdm import tqdm

BASE_URL = "https://llm-proxy.devops.beta.xiaohongshu.com/bedrock"
API_KEY = "fdf043b8b84b43cea2d317dbff340184"

DATA_DIR = Path.home() / "wavedrom-data" / "gpt-oss"
PROMPT_JSON = DATA_DIR / "wavedrom_to_verilog_test_vllm_api_prompt.json"
OUT_DIR = Path.home() / "wavedrom-data" / "claude-eval"


def load_dataset(path: Path) -> list[dict]:
    with open(path) as f:
        return json.load(f)


def call_claude(client: anthropic.Anthropic, model: str, user_content: str, 
                max_tokens: int = 16384, temperature: float = 0.0) -> str:
    resp = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": user_content}],
    )
    return resp.content[0].text


def infer_sample(client, model, sample, idx, max_retries=3):
    user_content = sample["messages"][0]["content"]
    for attempt in range(max_retries):
        try:
            result = call_claude(client, model, user_content)
            return idx, {"predict": result}
        except Exception as e:
            if attempt == max_retries - 1:
                return idx, {"predict": "", "api_error": str(e)[:500]}
            time.sleep(2 ** attempt)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="claude-sonnet-4-6 or claude-opus-4-6")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="0=all")
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()

    dataset = load_dataset(PROMPT_JSON)
    n = len(dataset) if args.limit <= 0 else min(len(dataset), args.limit)
    print(f"Dataset: {len(dataset)} samples, running {n}")

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    save_path = OUT_DIR / f"stage2_w2v_{args.model.replace('/', '_')}.jsonl"

    # Load existing results
    rows = [{"predict": ""} for _ in range(n)]
    if save_path.exists() and not args.restart:
        for i, line in enumerate(save_path.read_text().splitlines()):
            if i >= n or not line.strip():
                break
            rows[i] = json.loads(line)

    # Find samples that need inference
    todo = [i for i in range(n) if not rows[i].get("predict", "").strip() or rows[i].get("api_error")]
    if not todo:
        print(f"All {n} samples already done.")
    else:
        print(f"Need to infer {len(todo)} samples (model={args.model})")
        client = anthropic.Anthropic(base_url=BASE_URL, api_key=API_KEY)

        with ThreadPoolExecutor(max_workers=args.max_workers) as pool:
            futures = {pool.submit(infer_sample, client, args.model, dataset[i], i): i for i in todo}
            for fut in tqdm(as_completed(futures), total=len(futures), desc=args.model):
                idx, result = fut.result()
                rows[idx] = result
                # Save incrementally
                save_path.write_text(
                    "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n"
                )

    # Summary
    done = sum(1 for r in rows[:n] if r.get("predict", "").strip())
    errors = sum(1 for r in rows[:n] if r.get("api_error"))
    print(f"\nResults: {done}/{n} done, {errors} errors")
    print(f"Saved to: {save_path}")


if __name__ == "__main__":
    main()
