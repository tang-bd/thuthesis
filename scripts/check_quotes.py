"""Check all .tex files under data/ for ASCII double quotes (U+0022).

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


def mask_code_regions(content):
    """Replace code regions with same-length placeholder so positions stay valid."""
    masked = content
    for pat in [SKIP_ENVS, SKIP_TEXTTT]:
        masked = pat.sub(lambda m: ' ' * len(m.group()), masked)
    return masked


def find_ascii_quotes(path):
    with open(path, encoding='utf-8') as f:
        content = f.read()
    masked = mask_code_regions(content)
    hits = []
    for i, ch in enumerate(masked):
        if ch == '\x22':
            line_num = content[:i].count('\n') + 1
            col = i - content.rfind('\n', 0, i) - 1
            start = max(0, i - 6)
            end = min(len(content), i + 8)
            ctx = content[start:end].replace('\n', ' ')
            hits.append((line_num, col, ctx))
    return content, masked, hits


def fix_ascii_quotes(content, masked):
    """Replace paired ASCII " with Unicode left/right quotes, only in non-code regions."""
    result = list(content)
    in_quote = False
    for i, ch in enumerate(masked):
        if ch == '\x22':
            if not in_quote:
                result[i] = '“'
                in_quote = True
            else:
                result[i] = '”'
                in_quote = False
    return ''.join(result)


found_any = False
for fname in sorted(os.listdir(TEX_DIR)):
    if not fname.endswith('.tex'):
        continue
    path = os.path.join(TEX_DIR, fname)
    content, masked, hits = find_ascii_quotes(path)
    if hits:
        found_any = True
        for line_num, col, ctx in hits:
            print(f'  {fname}:{line_num}:{col}  ...{ctx}...')
        if FIX_MODE:
            fixed = fix_ascii_quotes(content, masked)
            with open(path, 'w', encoding='utf-8') as f:
                f.write(fixed)
            print(f'  -> FIXED {fname} ({len(hits)} quotes)')

if not found_any:
    print('OK: no ASCII double quotes found.')
else:
    if not FIX_MODE:
        print(f'\nRun with --fix to auto-replace.')
    sys.exit(1)
