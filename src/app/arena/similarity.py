"""Сравнение решений для антисписывания.

Код нормализуется: комментарии и пробелы убираются, имена переменных,
числа и строки заменяются заглушками, ключевые слова и встроенные имена
остаются. Похожесть — коэффициент Жаккара по последовательностям из
SHINGLE токенов. Совпадение от THRESHOLD — пометка «подозрительно».
"""

from __future__ import annotations

import builtins
import io
import keyword
import re
import tokenize

SHINGLE = 5
THRESHOLD = 0.9
MIN_TOKENS = 15

_PY_KEEP = (
    set(keyword.kwlist)
    | set(dir(builtins))
    | {
        'sys',
        'stdin',
        'stdout',
        'read',
        'readline',
        'split',
        'append',
        'pop',
        'heapq',
        'heappush',
        'heappop',
        'collections',
    }
)
_JS_KEYWORDS = set(
    'break case catch class const continue default delete do else export extends false finally for function '
    'if import in instanceof let new null return super switch this throw true try typeof var void while '
    'yield of async await '
    'console log require process stdin readFileSync split map Number parseInt Math push pop shift length'.split()
)
_JS_TOKEN = re.compile(
    r"[A-Za-z_$][\w$]*|\d+(?:\.\d+)?|'(?:\\.|[^'])*'|\"(?:\\.|[^\"])*\"|`(?:\\.|[^`])*`|===|!==|==|!=|<=|>=|=>|&&|\|\||\+\+|--|\S"
)
_JS_COMMENT = re.compile(r'//[^\n]*|/\*.*?\*/', re.S)


def tokens(language: str, code: str) -> list[str]:
    if language == 'python':
        out: list[str] = []
        try:
            for tok in tokenize.generate_tokens(io.StringIO(code).readline):
                if tok.type in (
                    tokenize.COMMENT,
                    tokenize.NL,
                    tokenize.NEWLINE,
                    tokenize.INDENT,
                    tokenize.DEDENT,
                    tokenize.ENDMARKER,
                ):
                    continue
                if tok.type == tokenize.NAME:
                    out.append(tok.string if tok.string in _PY_KEEP else 'ID')
                elif tok.type == tokenize.NUMBER:
                    out.append('NUM')
                elif tok.type == tokenize.STRING:
                    out.append('STR')
                else:
                    out.append(tok.string)
        except (tokenize.TokenError, IndentationError, SyntaxError):
            return code.split()
        return out
    out = []
    for t in _JS_TOKEN.findall(_JS_COMMENT.sub(' ', code)):
        if t[0].isalpha() or t[0] in '_$':
            out.append(t if t in _JS_KEYWORDS else 'ID')
        elif t[0].isdigit():
            out.append('NUM')
        elif t[0] in '\'"`':
            out.append('STR')
        else:
            out.append(t)
    return out


def fingerprint(language: str, code: str) -> set[tuple[str, ...]]:
    toks = tokens(language, code)
    if len(toks) < SHINGLE:
        return {tuple(toks)}
    return {tuple(toks[i : i + SHINGLE]) for i in range(len(toks) - SHINGLE + 1)}


def similarity(language: str, a: str, b: str) -> float:
    fa, fb = fingerprint(language, a), fingerprint(language, b)
    if not fa or not fb:
        return 0.0
    return len(fa & fb) / len(fa | fb)


def suspicious(language: str, a: str, b: str) -> bool:
    if min(len(tokens(language, a)), len(tokens(language, b))) < MIN_TOKENS:
        return False
    return similarity(language, a, b) >= THRESHOLD
