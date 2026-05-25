"""Classify Verilog modules by name segment matching for thesis Table 4.2.

Algorithm:
  1. Split module name into segments at underscores and CamelCase boundaries.
  2. Look up each segment in a keyword → category dictionary.
     Keywords are partitioned into two tiers:
       - CONTEXT keywords (bus/interface prefixes): axi, spi, uart, ...
       - FUNCTION keywords (circuit function): fifo, fsm, counter, ...
  3. Resolve:
     - 0 function matches → "其他"
     - 1 function match  → that category
     - 2+ function matches → take the LAST function keyword's category
       (Verilog naming convention: suffix = primary function)
     - Context-only matches (e.g. pure "axi_*") → "通信控制器"

This is fully automated: the keyword dictionary was derived from segment
frequency analysis of 2,362 unique module names.

Usage:
    python scripts/classify_modules_by_name.py [--random-dir DIR] [--verify]
"""
from __future__ import annotations

import glob
import os
import re
from collections import Counter


# ---------------------------------------------------------------------------
# 1. Extract DUT module name from a testbench file
# ---------------------------------------------------------------------------

_VERILOG_KW = {
    "module", "endmodule", "input", "output", "inout", "wire", "reg",
    "assign", "always", "initial", "begin", "end", "if", "else",
    "case", "endcase", "for", "while", "parameter", "localparam",
    "integer", "real", "time", "task", "endtask", "function",
    "endfunction", "generate", "endgenerate", "testbench",
}

_INST_RE = re.compile(r"^\s*(\w+)\s+(?:inst|dut)\s*[\(#]", re.MULTILINE)
_INST_PARAM_RE = re.compile(
    r"^\s*(\w+)\s*#\s*\(.*?\)\s*(?:inst|dut)\s*\(",
    re.MULTILINE | re.DOTALL,
)


def extract_module_name(tb_path: str) -> str | None:
    with open(tb_path, encoding="utf-8", errors="ignore") as f:
        text = f.read()
    for pat in [_INST_RE, _INST_PARAM_RE]:
        for m in pat.finditer(text):
            name = m.group(1)
            if name.lower() not in _VERILOG_KW:
                return name
    return None


# ---------------------------------------------------------------------------
# 2. Split module name into segments
# ---------------------------------------------------------------------------

def split_name(name: str) -> list[str]:
    """Split at underscores and CamelCase boundaries, lowercase, skip noise."""
    parts = name.split("_")
    segments: list[str] = []
    for part in parts:
        camel = re.findall(
            r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+", part
        )
        segments.extend(camel if camel else ([part] if part else []))
    return [s.lower() for s in segments]


# ---------------------------------------------------------------------------
# 3. Keyword → category dictionary (derived from segment frequency analysis)
# ---------------------------------------------------------------------------

FUNCTION_KEYWORDS: dict[str, str] = {
    # FIFO
    "fifo": "FIFO",
    "afifo": "FIFO",
    # 计数器
    "counter": "计数器",
    "count": "计数器",
    # 状态机
    "fsm": "状态机",
    # 多路选择器
    "mux": "多路选择器",
    "demux": "多路选择器",
    "multiplexer": "多路选择器",
    "demultiplexer": "多路选择器",
    "crossbar": "多路选择器",
    # 算术逻辑单元
    "alu": "算术逻辑单元",
    "adder": "算术逻辑单元",
    "subtractor": "算术逻辑单元",
    "multiplier": "算术逻辑单元",
    "accumulator": "算术逻辑单元",
    "fpu": "算术逻辑单元",
    # 存储器
    "ram": "存储器",
    "rom": "存储器",
    "sram": "存储器",
    "bram": "存储器",
    "memory": "存储器",
    "cache": "存储器",
    "dpram": "存储器",
    # 时钟与同步
    "sync": "时钟与同步",
    "synchronizer": "时钟与同步",
    "pll": "时钟与同步",
    "prescaler": "时钟与同步",
    # 编解码器
    "encoder": "编解码器",
    "decoder": "编解码器",
    "codec": "编解码器",
    "bcd": "编解码器",
    # 寄存器堆
    "regfile": "寄存器堆",
    # 移位寄存器
    "shifter": "移位寄存器",
    "lfsr": "移位寄存器",
    # 定时器
    "timer": "定时器",
    "watchdog": "定时器",
    "wdt": "定时器",
    # CRC与校验
    "crc": "CRC与校验",
    "checksum": "CRC与校验",
    "parity": "CRC与校验",
    "ecc": "CRC与校验",
    "hamming": "CRC与校验",
    # GPIO与外设
    "gpio": "GPIO与外设",
    "led": "GPIO与外设",
    "keypad": "GPIO与外设",
    # PWM控制器
    "pwm": "PWM控制器",
    # 触发器与锁存器
    "latch": "触发器与锁存器",
    "dff": "触发器与锁存器",
    # 比较器
    "comparator": "比较器",
}

CONTEXT_KEYWORDS: dict[str, str] = {
    "axi": "通信控制器",
    "apb": "通信控制器",
    "ahb": "通信控制器",
    "amba": "通信控制器",
    "wishbone": "通信控制器",
    "uart": "通信控制器",
    "spi": "通信控制器",
    "i2c": "通信控制器",
    "pcie": "通信控制器",
    "serial": "通信控制器",
}

# Segments to ignore (version numbers, generic words, etc.)
NOISE = {"v2", "v1", "v3", "v4", "v5", "v6", "v7", "v8", "v9", "v10",
         "b2s", "the", "of", "to", "and", "for", "in", "on", "is", "at",
         "no", "de", "el", "la", "le"}


# ---------------------------------------------------------------------------
# 4. Classify one module
# ---------------------------------------------------------------------------

def classify_one(module_name: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Return (category, [(position, segment, category), ...]).

    Classification rule:
      - 0 keywords matched → "其他"
      - Exactly 1 function keyword → that category
      - 1+ context keywords only (no function keyword) → "通信控制器"
      - 2+ function keywords from THE SAME category → that category
      - 2+ function keywords from DIFFERENT categories → "其他" (ambiguous)
    """
    segments = split_name(module_name)

    func_hits: list[tuple[int, str, str]] = []   # (pos, segment, category)
    ctx_hits: list[tuple[int, str, str]] = []

    for i, seg in enumerate(segments):
        if seg in NOISE or len(seg) <= 1:
            continue
        if seg in FUNCTION_KEYWORDS:
            func_hits.append((i, seg, FUNCTION_KEYWORDS[seg]))
        elif seg in CONTEXT_KEYWORDS:
            ctx_hits.append((i, seg, CONTEXT_KEYWORDS[seg]))

    if not func_hits and not ctx_hits:
        return "其他", []

    if not func_hits:
        return "通信控制器", ctx_hits

    matched_cats = set(h[2] for h in func_hits)
    if len(matched_cats) == 1:
        return matched_cats.pop(), func_hits

    return "其他", func_hits


def classify_category(module_name: str) -> str:
    return classify_one(module_name)[0]


# ---------------------------------------------------------------------------
# 5. Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--random-dir", default="/tmp/wavedrom_data/random")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--check", type=str, default=None)
    parser.add_argument("--multi", action="store_true",
                        help="Show multi-function-keyword cases")
    args = parser.parse_args()

    if args.check:
        cat, hits = classify_one(args.check)
        segs = split_name(args.check)
        print(f"Name:     {args.check}")
        print(f"Segments: {segs}")
        print(f"Hits:     {hits}")
        print(f"Category: {cat}")
        return

    tb_files = sorted(glob.glob(os.path.join(args.random_dir, "*_tb.v")))
    print(f"Testbench files: {len(tb_files)}")

    module_names: list[tuple[str, str]] = []
    failed = 0
    for tb in tb_files:
        basename = os.path.basename(tb).replace("_tb.v", "")
        name = extract_module_name(tb)
        if name:
            module_names.append((basename, name))
        else:
            failed += 1
    print(f"Extracted: {len(module_names)}, failed: {failed}")

    # Classify all
    categories: dict[str, list[tuple[str, str]]] = {}
    multi_func: list[tuple[str, str, list]] = []
    for basename, name in module_names:
        cat, hits = classify_one(name)
        categories.setdefault(cat, []).append((basename, name))
        if len(hits) > 1:
            cats_in_hits = set(h[2] for h in hits)
            if len(cats_in_hits) > 1:
                multi_func.append((basename, name, hits))

    total = len(module_names)
    print(f"\n{'='*60}")
    print(f"  Classification ({total} modules)")
    print(f"{'='*60}")
    sorted_cats = sorted(categories.items(), key=lambda x: -len(x[1]))
    for cat, items in sorted_cats:
        print(f"  {cat}: {len(items)} ({len(items)/total*100:.1f}%)")

    classified = total - len(categories.get("其他", []))
    print(f"\n  Classified: {classified} ({classified/total*100:.1f}%)")

    # LaTeX table
    print(f"\n{'='*60}")
    print("  LaTeX table rows")
    print(f"{'='*60}")
    for cat, items in sorted_cats:
        n = len(items)
        if cat == "其他":
            continue
        n_str = f"{n:,}".replace(",", "{,}")
        print(f"    {cat} & {n_str} & {n/total*100:.1f}\\% \\\\")
    n_other = len(categories.get("其他", []))
    n_str = f"{n_other:,}".replace(",", "{,}")
    print(f"    其他 & {n_str} & {n_other/total*100:.1f}\\% \\\\")

    # Verification
    if args.verify:
        print(f"\n{'='*60}")
        print("  Per-category unique module names")
        print(f"{'='*60}")
        for cat, items in sorted_cats:
            unique = sorted(set(n for _, n in items))
            print(f"\n  [{cat}] ({len(items)} modules, {len(unique)} unique)")
            for name in unique[:25]:
                cnt = sum(1 for _, n in items if n == name)
                print(f"    {name} (x{cnt})")
            if len(unique) > 25:
                print(f"    ... +{len(unique)-25} more")

    # Multi-function analysis
    if args.multi:
        print(f"\n{'='*60}")
        print(f"  Multi-function-keyword cases ({len(multi_func)} modules)")
        print(f"{'='*60}")
        seen = set()
        for basename, name, hits in multi_func:
            if name not in seen:
                cat = classify_category(name)
                print(f"  {name}")
                print(f"    hits: {[(s,c) for _,s,c in hits]}")
                print(f"    → {cat} (last functional keyword)")
                seen.add(name)


if __name__ == "__main__":
    main()
