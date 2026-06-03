"""生成论文第四章所有分布图（中文标注）。

数据来源: ~/wavedrom-data/
输出: figures/ 下的 PDF 文件

Usage:
    python scripts/generate_all_figures.py
"""
import json
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from pathlib import Path
from PIL import Image

matplotlib.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'STHeiti', 'SimHei']
matplotlib.rcParams['axes.unicode_minus'] = False

FIGURES_DIR = Path(__file__).resolve().parent.parent / 'figures'
DATA_DIR = Path.home() / 'wavedrom-data'
GPT_DIR = DATA_DIR / 'gpt-oss'
STAGE1_DIR = DATA_DIR / 'stage1_eval'
STAGE2_DIR = DATA_DIR / 'stage2_eval'


def gen_signal_count_dist():
    """信号数量分布 → signal_count_dist.pdf"""
    json_files = sorted(GPT_DIR.glob('*_tb_wavedrom.json'))
    counts = []
    for f in json_files:
        try:
            with open(f) as fh:
                wj = json.load(fh)
            counts.append(sum(1 for s in wj.get('signal', []) if isinstance(s, dict) and 'name' in s))
        except:
            pass
    counts = np.array(counts)

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(counts, bins=np.arange(2.5, 16.5, 1), color='steelblue', edgecolor='white', linewidth=0.5)
    ax.set_xlabel('信号数量')
    ax.set_ylabel('样本数')
    ax.set_xticks(range(3, 16))
    ax.set_xlim(2.5, 15.5)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'signal_count_dist.pdf', bbox_inches='tight')
    plt.close()
    print(f"signal_count_dist.pdf: median={np.median(counts):.0f}, 5-10占{np.sum((counts>=5)&(counts<=10))/len(counts)*100:.0f}%")


def gen_image_dim_dist():
    """图像尺寸分布 → image_dim_dist.pdf"""
    png_files = sorted(GPT_DIR.glob('*_tb_wavedrom.png'))
    widths, heights = [], []
    for f in png_files:
        try:
            img = Image.open(f)
            widths.append(img.width)
            heights.append(img.height)
        except:
            pass
    widths, heights = np.array(widths), np.array(heights)
    ratios = widths / heights
    pixels = widths * heights / 1000

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    axes[0].hist(ratios, bins=np.arange(2, 22, 2), color='steelblue', edgecolor='white', linewidth=0.5)
    axes[0].set_xlabel('宽高比')
    axes[0].set_ylabel('样本数')
    axes[0].set_title('（a）宽高比分布')
    axes[0].set_xlim(2, 20)

    axes[1].hist(pixels, bins=np.arange(0, 2200, 200), color='steelblue', edgecolor='white', linewidth=0.5)
    axes[1].set_xlabel('像素总数（×1000）')
    axes[1].set_ylabel('样本数')
    axes[1].set_title('（b）像素总数分布')
    axes[1].set_xlim(0, 2000)

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'image_dim_dist.pdf', bbox_inches='tight')
    plt.close()
    print(f"image_dim_dist.pdf: ratio median={np.median(ratios):.2f}, pixels median={np.median(pixels):.0f}K")


def gen_code_length_dist():
    """代码长度分布 → code_length_dist.pdf（需要Qwen3-8B tokenizer）"""
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen3-8B", trust_remote_code=True)

    with open(GPT_DIR / 'wavedrom_to_verilog_train.json') as f:
        train = json.load(f)
    with open(GPT_DIR / 'wavedrom_to_verilog_test.json') as f:
        test = json.load(f)
    all_data = train + test

    line_counts, token_counts = [], []
    for sample in all_data:
        code = sample['messages'][1]['content']
        line_counts.append(len([l for l in code.split('\n') if l.strip() and not l.strip().startswith('//')]))
        token_counts.append(len(tok.encode(code, add_special_tokens=False)))
    line_counts, token_counts = np.array(line_counts), np.array(token_counts)

    fig, axes = plt.subplots(1, 2, figsize=(10, 3.5))
    axes[0].hist(line_counts, bins=np.arange(0, 320, 20), color='steelblue', edgecolor='white', linewidth=0.5)
    axes[0].set_xlabel('代码行数')
    axes[0].set_ylabel('样本数')
    axes[0].set_title('（a）代码行数分布')
    axes[0].set_xlim(0, 300)
    axes[0].axvline(np.median(line_counts), color='red', linestyle='--', linewidth=1,
                    label=f'中位数={np.median(line_counts):.0f}')
    axes[0].legend()

    axes[1].hist(token_counts, bins=np.arange(0, 3600, 200), color='steelblue', edgecolor='white', linewidth=0.5)
    axes[1].set_xlabel('词元数（Qwen3-8B）')
    axes[1].set_ylabel('样本数')
    axes[1].set_title('（b）词元数分布')
    axes[1].set_xlim(0, 3400)
    axes[1].axvline(np.median(token_counts), color='red', linestyle='--', linewidth=1,
                    label=f'中位数={np.median(token_counts):.0f}')
    axes[1].legend()

    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'code_length_dist.pdf', bbox_inches='tight')
    plt.close()
    print(f"code_length_dist.pdf: lines median={np.median(line_counts):.0f}, tokens median={np.median(token_counts):.0f}")


def gen_stage1_f1_dist():
    """Stage 1 F1分布 → stage1_f1_dist.pdf"""
    m = json.load(open(STAGE1_DIR / 'manifest.json'))
    f1s = [s['f1'] for s in m['samples']]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(f1s, bins=np.arange(0, 1.05, 0.05), color='steelblue', edgecolor='white', linewidth=0.5)
    ax.set_xlabel('F1分数')
    ax.set_ylabel('样本数')
    ax.set_xlim(0, 1.05)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'stage1_f1_dist.pdf', bbox_inches='tight')
    plt.close()
    print(f"stage1_f1_dist.pdf: mean={np.mean(f1s):.4f}, F1=1.0占{sum(1 for f in f1s if f==1.0)}")


def gen_stage2_f1_dist():
    """Stage 2 F1分布 → stage2_f1_dist.pdf"""
    m = json.load(open(STAGE2_DIR / 'manifest.json'))
    f1s = [s['f1'] for s in m['samples']]

    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.hist(f1s, bins=np.arange(0, 1.05, 0.05), color='steelblue', edgecolor='white', linewidth=0.5)
    ax.set_xlabel('F1分数')
    ax.set_ylabel('样本数')
    ax.set_xlim(0, 1.05)
    plt.tight_layout()
    plt.savefig(FIGURES_DIR / 'stage2_f1_dist.pdf', bbox_inches='tight')
    plt.close()
    print(f"stage2_f1_dist.pdf: mean={np.mean(f1s):.4f}, F1=1.0占{sum(1 for f in f1s if f==1.0)}")


if __name__ == '__main__':
    gen_signal_count_dist()
    gen_image_dim_dist()
    gen_stage1_f1_dist()
    gen_stage2_f1_dist()
    gen_code_length_dist()  # slow (tokenizer)
    print("\nAll figures generated.")
