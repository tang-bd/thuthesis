"""Compute and plot Verilog code length distribution for thesis Chapter 4.

Tokenization: Qwen3-8B tokenizer (the actual stage-2 model tokenizer).
Lines: non-empty, non-comment lines.

Results: lines median=61, mean=89; tokens median=558, mean=956

Data source: tbd-lab/verilog-wavedrom-gpt-oss (wavedrom_to_verilog_train/test.json)
Requires: /tmp/verilog-wavedrom-gpt-oss/ extracted dataset

Usage:
    python scripts/code_length_analysis.py
"""
import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
from transformers import AutoTokenizer

matplotlib.rcParams['font.family'] = ['Arial']

DATA_DIR = Path('/tmp/verilog-wavedrom-gpt-oss')
OUT_PATH = Path(__file__).resolve().parent.parent / 'figures' / 'code_length_dist.pdf'


def main():
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", trust_remote_code=True)

    with open(DATA_DIR / 'wavedrom_to_verilog_train.json') as f:
        train = json.load(f)
    with open(DATA_DIR / 'wavedrom_to_verilog_test.json') as f:
        test = json.load(f)
    all_data = train + test
    print(f"Total samples: {len(all_data)}")

    line_counts = []
    token_counts = []
    for sample in all_data:
        code = sample['messages'][1]['content']
        lines = [l for l in code.split('\n') if l.strip() and not l.strip().startswith('//')]
        line_counts.append(len(lines))
        tokens = tok.encode(code, add_special_tokens=False)
        token_counts.append(len(tokens))

    line_counts = np.array(line_counts)
    token_counts = np.array(token_counts)

    print(f"Lines:  median={np.median(line_counts):.0f}, mean={line_counts.mean():.0f}")
    print(f"Tokens: median={np.median(token_counts):.0f}, mean={token_counts.mean():.0f}")
    in_21_120 = np.sum((line_counts >= 21) & (line_counts <= 120))
    in_200_1200 = np.sum((token_counts >= 200) & (token_counts <= 1200))
    print(f"Lines 21-120: {in_21_120/len(line_counts)*100:.0f}%")
    print(f"Tokens 200-1200: {in_200_1200/len(token_counts)*100:.0f}%")

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))

    ax = axes[0]
    bins_lines = np.arange(0, 320, 20)
    ax.hist(line_counts, bins=bins_lines, color='steelblue', edgecolor='white', linewidth=0.5)
    ax.set_xlabel('Lines of Code')
    ax.set_ylabel('Count')
    ax.set_title('(a) Code Line Count')
    ax.set_xlim(0, 300)
    ax.axvline(np.median(line_counts), color='red', linestyle='--', linewidth=1,
               label=f'Median={np.median(line_counts):.0f}')
    ax.legend()

    ax = axes[1]
    bins_tokens = np.arange(0, 3600, 200)
    ax.hist(token_counts, bins=bins_tokens, color='steelblue', edgecolor='white', linewidth=0.5)
    ax.set_xlabel('Token Count')
    ax.set_ylabel('Count')
    ax.set_title('(b) Token Count (Qwen3-8B)')
    ax.set_xlim(0, 3400)
    ax.axvline(np.median(token_counts), color='red', linestyle='--', linewidth=1,
               label=f'Median={np.median(token_counts):.0f}')
    ax.legend()

    plt.tight_layout()
    plt.savefig(OUT_PATH, bbox_inches='tight')
    print(f"\nSaved to {OUT_PATH}")


if __name__ == '__main__':
    main()
