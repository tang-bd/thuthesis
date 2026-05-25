"""Dataset analysis scripts for thesis Chapter 4.

Usage:
    python scripts/dataset_analysis.py --random-dir /tmp/wavedrom_data/random \
                                       --gpt-dir /tmp/wavedrom_data
"""
from __future__ import annotations

import csv
import glob
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# 1. Verilog_GitHub row count
# ---------------------------------------------------------------------------

def count_verilog_github(csv_path: str) -> int:
    csv.field_size_limit(sys.maxsize)
    with open(csv_path, encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        next(reader)
        return sum(1 for _ in reader)


# ---------------------------------------------------------------------------
# 2. Basic dataset stats
# ---------------------------------------------------------------------------

def dataset_stats(folder: str, label: str, exclude_subdir: str | None = None):
    jsons = sorted(glob.glob(os.path.join(folder, "*_tb_wavedrom.json")))
    if exclude_subdir:
        jsons = [p for p in jsons if exclude_subdir not in p]

    signal_counts = []
    total_signals = 0
    binary_signals = 0
    data_signals = 0
    wave_lengths = []

    for jpath in jsons:
        try:
            with open(jpath) as f:
                obj = json.load(f)
            sigs = [s for s in obj.get("signal", []) if isinstance(s, dict) and "name" in s]
            signal_counts.append(len(sigs))
            for s in sigs:
                total_signals += 1
                wave = s.get("wave", "")
                wave_lengths.append(len(wave))
                if s.get("data"):
                    data_signals += 1
                elif all(c in "01." for c in wave):
                    binary_signals += 1
        except Exception:
            pass

    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}")
    print(f"Samples: {len(jsons)}")
    print(f"Total signals: {total_signals}")
    print(f"Avg signals/sample: {sum(signal_counts)/len(signal_counts):.2f}")
    print(f"Signal count range: {min(signal_counts)}--{max(signal_counts)}, median={sorted(signal_counts)[len(signal_counts)//2]}")
    print(f"Binary signals: {binary_signals} ({binary_signals/total_signals*100:.1f}%)")
    print(f"Data-labeled signals: {data_signals} ({data_signals/total_signals*100:.1f}%)")
    print(f"Avg wave length: {sum(wave_lengths)/len(wave_lengths):.2f}")

    dist = Counter(signal_counts)
    print("\nSignal count distribution:")
    for k in sorted(dist):
        print(f"  {k}: {dist[k]} ({dist[k]/len(signal_counts)*100:.1f}%)")

    return signal_counts


# ---------------------------------------------------------------------------
# 3. Module functionality classification (fine-grained)
# ---------------------------------------------------------------------------

def _wb(kw: str) -> str:
    """Wrap keyword with word boundaries to avoid substring false positives."""
    return r"\b" + kw + r"\b"


KEYWORDS_MAP = {
    "FIFO": [_wb("fifo"), "first.in.first.out", "circular buffer", "ring buffer"],
    "计数器": [r"(?<!cycle\s)\bcounter\b", "count up", "count down",
               "up.counter", "down.counter",
               r"increment.*decrement", "modulo.*counter"],
    "寄存器堆": ["register file", "register bank", _wb("regfile"),
                 "register array", "reg_file"],
    "移位寄存器": ["shift register", _wb("shifter"), "barrel shift",
                   "shift left", "shift right", _wb("LFSR"),
                   "linear feedback"],
    "状态机": ["state machine", _wb("FSM"), "finite state",
               "state transition", _wb("mealy"), _wb("moore")],
    "编解码器": [_wb("encoder"), _wb("decoder"), "priority encoder",
                 "7.segment", "seven.segment", _wb("bcd"),
                 "gray code", "binary to", "to binary", "one.hot"],
    "多路选择器": ["multiplexer", _wb("mux"), _wb("demux"),
                   "demultiplexer"],
    "算术逻辑单元": [_wb("ALU"), "arithmetic logic", _wb("adder"),
                     _wb("subtractor"), _wb("multiplier"),
                     _wb("divider"), _wb("accumulator")],
    "比较器": [_wb("comparator"), _wb("magnitude")],
    "存储器": [_wb("memory"), _wb("RAM"), _wb("ROM"), _wb("SRAM"),
               _wb("DRAM"), _wb("cache"), "lookup table"],
    "时钟与同步": ["clock divider", "frequency divider", _wb("prescaler"),
                   "clock gating", _wb("PLL"), "clock domain",
                   _wb("synchronizer"), _wb("sync")],
    "通信控制器": [_wb("UART"), _wb("SPI"), _wb("I2C"), _wb("AMBA"),
                   _wb("AXI"), _wb("APB"), _wb("AHB"), _wb("Wishbone"),
                   "bus interface"],
    "PWM控制器": [_wb("PWM"), "pulse width", "duty cycle"],
    "触发器与锁存器": ["flip.flop", _wb("latch"), "D.flip", _wb("JK"),
                       "T.flip", "SR.flip"],
    "定时器": [_wb("timer"), _wb("watchdog"), _wb("timeout")],
    "CRC与校验": [_wb("CRC"), _wb("checksum"), _wb("parity"), _wb("ECC"),
                  "error correction", "error detect", _wb("hamming")],
    "GPIO与外设": [_wb("GPIO"), _wb("LED"), _wb("keypad")],
}


def classify_modules(llm_output_folder: str,
                     valid_modules: set[str] | None = None):
    llm_files = sorted(glob.glob(os.path.join(llm_output_folder,
                                              "*_llm_output.txt")))
    categories = Counter()

    for fpath in llm_files:
        basename = os.path.basename(fpath).replace("_llm_output.txt", "")
        if valid_modules is not None and basename not in valid_modules:
            continue
        try:
            text = open(fpath, encoding="utf-8", errors="ignore").read()
            m = re.search(r"<analysis>(.*?)(?:</analysis>|<testbench)", text,
                          re.DOTALL | re.IGNORECASE)
            if not m:
                m = re.search(r"(.*?)(?:<testbench)", text, re.DOTALL)
            analysis = m.group(1) if m else text[:2000]

            matched = False
            for cat, keywords in KEYWORDS_MAP.items():
                for kw in keywords:
                    if re.search(kw, analysis, re.IGNORECASE):
                        categories[cat] += 1
                        matched = True
                        break
                if matched:
                    break
            if not matched:
                categories["其他"] += 1
        except Exception:
            categories["解析失败"] += 1

    total = sum(categories.values())
    print(f"\nTotal modules: {total}")
    print("\nModule functionality classification:")
    for k, v in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  {k}: {v} ({v/total*100:.1f}%)")

    return categories


# ---------------------------------------------------------------------------
# 4. Signal transition analysis
# ---------------------------------------------------------------------------

def count_transitions(wave: str) -> int:
    expanded = []
    for c in wave:
        if c == "." and expanded:
            expanded.append(expanded[-1])
        else:
            expanded.append(c)
    return sum(1 for i in range(1, len(expanded)) if expanded[i] != expanded[i - 1])


def transition_analysis(folder: str, label: str, exclude_subdir: str | None = None):
    flat_signals = 0
    total_signals = 0
    flat_samples = 0
    total_samples = 0
    all_transitions = []

    for jpath in sorted(glob.glob(os.path.join(folder, "*_tb_wavedrom.json"))):
        if exclude_subdir and exclude_subdir in jpath:
            continue
        try:
            obj = json.load(open(jpath))
            sigs = [s for s in obj.get("signal", []) if isinstance(s, dict) and "name" in s]
            total_samples += 1
            sample_flat = True
            for s in sigs:
                total_signals += 1
                n = count_transitions(s.get("wave", ""))
                all_transitions.append(n)
                if n == 0:
                    flat_signals += 1
                else:
                    sample_flat = False
            if sample_flat:
                flat_samples += 1
        except Exception:
            pass

    avg_t = sum(all_transitions) / len(all_transitions) if all_transitions else 0
    print(f"\n{label}:")
    print(f"  Samples: {total_samples}, Signals: {total_signals}")
    print(f"  Constant signals: {flat_signals} ({flat_signals/total_signals*100:.1f}%)")
    print(f"  All-constant samples: {flat_samples} ({flat_samples/total_samples*100:.1f}%)")
    print(f"  Avg transitions/signal: {avg_t:.2f}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--random-dir", default="/tmp/wavedrom_data/random")
    parser.add_argument("--gpt-dir", default="/tmp/wavedrom_data")
    args = parser.parse_args()

    valid = {
        os.path.basename(p).replace("_tb_wavedrom.json", "")
        for p in glob.glob(os.path.join(args.random_dir, "*_tb_wavedrom.json"))
    }

    dataset_stats(args.random_dir, "Random stimuli")
    dataset_stats(args.gpt_dir, "LLM (GPT-OSS)", exclude_subdir="/random/")
    classify_modules(args.gpt_dir, valid_modules=valid)
    transition_analysis(args.random_dir, "Random stimuli")
    transition_analysis(args.gpt_dir, "LLM (GPT-OSS)", exclude_subdir="/random/")
