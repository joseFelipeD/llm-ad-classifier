"""Leitura e validação dos arquivos JSONL de entrada.

Problemas de entrada (JSON inválido, id ausente/duplicado, texto ausente) abortam
antes de qualquer chamada de API: não faz sentido gastar tokens com um arquivo que
não pode gerar uma saída válida.
"""
import json
from dataclasses import dataclass

from .labels import is_valid_label


class InputError(Exception):
    pass


@dataclass(frozen=True)
class Item:
    id: str
    text: str


def parse_items(lines, source="<input>"):
    """Valida linhas JSONL e devolve [Item]. Ignora campos extras (ex.: `label`)."""
    items, errors, seen = [], [], set()
    for n, raw in enumerate(lines, 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as e:
            errors.append(f"{source}:{n}: JSON inválido ({e.msg})")
            continue
        if not isinstance(row, dict):
            errors.append(f"{source}:{n}: linha não é um objeto JSON")
            continue
        item_id, text = row.get("id"), row.get("text")
        if not isinstance(item_id, str) or not item_id.strip():
            errors.append(f"{source}:{n}: id ausente ou inválido")
            continue
        if item_id in seen:
            errors.append(f"{source}:{n}: id duplicado {item_id!r}")
            continue
        if not isinstance(text, str):
            errors.append(f"{source}:{n}: campo text ausente ou não é string ({item_id})")
            continue
        seen.add(item_id)
        items.append(Item(item_id, text))
    if errors:
        shown = "\n".join(errors[:10])
        more = f"\n... e mais {len(errors) - 10}" if len(errors) > 10 else ""
        raise InputError(f"{len(errors)} problema(s) na entrada:\n{shown}{more}")
    return items


def load_items(path):
    with open(path, encoding="utf-8-sig") as f:
        return parse_items(f, source=str(path))


def load_examples(path):
    """Exemplos few-shot: [(texto, label)], exigindo label válido."""
    with open(path, encoding="utf-8-sig") as f:
        lines = f.readlines()
    items = parse_items(lines, source=str(path))
    rows = [json.loads(line) for line in lines if line.strip()]
    examples = []
    for item, row in zip(items, rows):
        label = row.get("label")
        if not is_valid_label(label):
            raise InputError(f"{path}: label inválido em {item.id}: {label!r}")
        examples.append((item.text, label))
    return examples
