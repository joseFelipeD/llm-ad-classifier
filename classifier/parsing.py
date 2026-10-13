"""Interpretação da resposta do modelo.

Nunca completa lacunas: devolve só os itens com label válido e explícito; tudo o
mais fica de fora e é o pipeline que decide se tenta de novo ou registra falha.
"""
import json
import re
from dataclasses import dataclass, field

from .labels import is_valid_label

_LINE_RE = re.compile(r"^\s*(\d+)\s*[|:]\s*([A-Za-z_]+)\s*$")
_FENCE_RE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")


@dataclass
class ParseResult:
    labels: dict = field(default_factory=dict)    # índice (1..n) -> label
    problems: list = field(default_factory=list)


def parse_response(content, fmt, n):
    if not isinstance(content, str) or not content.strip():
        return ParseResult(problems=["resposta vazia"])
    if fmt == "lines":
        pairs, problems = _pairs_from_lines(content)
    else:
        pairs, problems = _pairs_from_json(content)
    return _validate(pairs, n, problems)


def _pairs_from_json(content):
    text = _FENCE_RE.sub("", content.strip())
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Texto extra em volta do objeto: tenta o trecho entre a primeira { e a última }.
        start, end = text.find("{"), text.rfind("}")
        try:
            data = json.loads(text[start:end + 1]) if 0 <= start < end else None
        except json.JSONDecodeError:
            data = None
        if data is None:
            return [], ["JSON malformado"]
    entries = data.get("labels") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return [], ["JSON sem lista 'labels'"]
    pairs, problems = [], []
    for e in entries:
        if isinstance(e, dict) and "i" in e and "label" in e:
            pairs.append((e["i"], e["label"]))
        else:
            problems.append(f"entrada malformada: {e!r}"[:120])
    return pairs, problems


def _pairs_from_lines(content):
    pairs, ignored = [], 0
    for line in content.splitlines():
        m = _LINE_RE.match(line)
        if m:
            pairs.append((int(m.group(1)), m.group(2)))
        elif line.strip():
            ignored += 1
    return pairs, [f"{ignored} linha(s) fora do formato ignorada(s)"] if ignored else []


def _validate(pairs, n, problems):
    labels, conflicted = {}, set()
    for idx, label in pairs:
        if isinstance(idx, bool) or not isinstance(idx, int) or not 1 <= idx <= n:
            problems.append(f"índice inválido: {idx!r}")
            continue
        label = label.strip().lower() if isinstance(label, str) else label
        if not is_valid_label(label):
            problems.append(f"label inválido no item {idx}: {label!r}")
            continue
        if idx in labels and labels[idx] != label:
            conflicted.add(idx)
        labels[idx] = label
    for idx in conflicted:
        # Duas respostas diferentes para o mesmo item: nenhuma é confiável.
        problems.append(f"labels conflitantes no item {idx}")
        del labels[idx]
    return ParseResult(labels, problems)
