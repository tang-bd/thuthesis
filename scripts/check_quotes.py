"""Check all .tex files under data/ for quote issues.

Detects two kinds of problems:
  1. ASCII double quotes (U+0022) — should be Unicode "" (U+201C/U+201D)
  2. Mismatched curly quotes — e.g. "" instead of "" (wrong left/right pairing)

Skips verbatim/lstlisting and \\texttt{} regions where ASCII quotes are expected.

Usage:
    python scripts/check_quotes.py          # check only
    python scripts/check_quotes.py --fix    # auto-fix paired ASCII quotes to Unicode ""
"""
import sys
import os
import re

TEX_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
FIX_MODE = '--fix' in sys.argv

SKIP_ENVS = re.compile(
    r'\\begin\{(?:verbatim|lstlisting|minted)\}.*?\\end\{(?:verbatim|lstlisting|minted)\}',
    re.DOTALL,
)
SKIP_TEXTTT = re.compile(r'\\texttt\{[^}]*\}')

LEFT = '“'
RIGHT = '”'


def mask_code_regions(content):
    """Replace code regions with same-length placeholder so positions stay valid."""
    masked = content
    for pat in [SKIP_ENVS, SKIP_TEXTTT]:
        masked = pat.sub(lambda m: ' ' * len(m.group()), masked)
    return masked


def find_ascii_quotes(content, masked):
    hits = []
    for i, ch in enumerate(masked):
        if ch == '\x22':
            line_num = content[:i].count('\n') + 1
            col = i - content.rfind('\n', 0, i) - 1
            start = max(0, i - 6)
            end = min(len(content), i + 8)
            ctx = content[start:end].replace('\n', ' ')
            hits.append((line_num, col, ctx))
    return hits


def find_mismatched_curly_quotes(content, masked):
    hits = []
    expect_left = True
    for i, ch in enumerate(masked):
        if ch not in (LEFT, RIGHT):
            continue
        line_num = content[:i].count('\n') + 1
        start = max(0, i - 8)
        end = min(len(content), i + 9)
        ctx = content[start:end].replace('\n', ' ')

        if expect_left and ch == RIGHT:
            hits.append((line_num, i, f'expected left “ but got right ”: ...{ctx}...'))
        elif not expect_left and ch == LEFT:
            hits.append((line_num, i, f'expected right ” but got left “: ...{ctx}...'))

        expect_left = (ch == RIGHT)

    if not expect_left:
        hits.append((0, 0, 'unmatched left “ without closing right ”'))
    return hits


def fix_ascii_quotes(content, masked):
    """Replace paired ASCII " with Unicode left/right quotes, only in non-code regions."""
    result = list(content)
    in_quote = False
    for i, ch in enumerate(masked):
        if ch == '\x22':
            if not in_quote:
                result[i] = LEFT
                in_quote = True
            else:
                result[i] = RIGHT
                in_quote = False
    return ''.join(result)


found_any = False
for fname in sorted(os.listdir(TEX_DIR)):
    if not fname.endswith('.tex'):
        continue
    path = os.path.join(TEX_DIR, fname)
    with open(path, encoding='utf-8') as f:
        content = f.read()
    masked = mask_code_regions(content)

    ascii_hits = find_ascii_quotes(content, masked)
    curly_hits = find_mismatched_curly_quotes(content, masked)

    if ascii_hits:
        found_any = True
        for line_num, col, ctx in ascii_hits:
            print(f'  {fname}:{line_num}:{col}  ASCII quote  ...{ctx}...')
        if FIX_MODE:
            content = fix_ascii_quotes(content, masked)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'  -> FIXED {fname} ({len(ascii_hits)} ASCII quotes)')

    if curly_hits:
        found_any = True
        for line_num, pos, msg in curly_hits:
            print(f'  {fname}:{line_num}  mismatched curly quote: {msg}')

if not found_any:
    print('OK: no quote issues found.')
else:
    if not FIX_MODE:
        print(f'\nRun with --fix to auto-replace ASCII quotes.')
    sys.exit(1)
