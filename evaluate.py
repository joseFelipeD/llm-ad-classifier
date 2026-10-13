#!/usr/bin/env python3
"""Avalia predições contra um gabarito.

Uso:
    python evaluate.py gold.jsonl predictions.jsonl [usage.json]

gold.jsonl:        {"id": ..., "text": ..., "label": ...}
predictions.jsonl: {"id": ..., "label": ...}
usage.json:        {"items": N, "input_tokens": N, "output_tokens": N, ...}

Sem dependências externas.
"""
import json
import sys
from collections import Counter, defaultdict

LABELS = [
    "finance", "automotive", "health", "travel", "technology",
    "food_beverage", "fashion", "entertainment", "other",
]
ACC_TARGET = 0.85
TOKEN_BUDGET = 400


def load_jsonl(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as e:
                sys.exit(f"{path}:{n}: JSON inválido ({e})")
    return rows


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    gold = {r["id"]: r for r in load_jsonl(sys.argv[1])}
    preds = load_jsonl(sys.argv[2])

    pred_by_id = {}
    problems = []
    for p in preds:
        pid = p.get("id")
        if pid in pred_by_id:
            problems.append(f"id duplicado: {pid}")
        pred_by_id[pid] = p.get("label")

    missing = [i for i in gold if i not in pred_by_id]
    extra = [i for i in pred_by_id if i not in gold]
    invalid = {i: l for i, l in pred_by_id.items() if l not in LABELS}

    correct = 0
    confusion = defaultdict(Counter)
    tp, fp, fn = Counter(), Counter(), Counter()
    for gid, g in gold.items():
        y = g["label"]
        yhat = pred_by_id.get(gid)  # None se faltando -> conta como erro
        confusion[y][yhat] += 1
        if yhat == y:
            correct += 1
            tp[y] += 1
        else:
            fn[y] += 1
            if yhat is not None:
                fp[yhat] += 1

    n = len(gold)
    acc = correct / n if n else 0.0
    present = [l for l in LABELS if any(g["label"] == l for g in gold.values())]
    f1s = []
    for l in present:
        p = tp[l] / (tp[l] + fp[l]) if tp[l] + fp[l] else 0.0
        r = tp[l] / (tp[l] + fn[l]) if tp[l] + fn[l] else 0.0
        f1s.append(2 * p * r / (p + r) if p + r else 0.0)
    macro_f1 = sum(f1s) / len(f1s) if f1s else 0.0

    print(f"itens no gabarito : {n}")
    print(f"predições         : {len(preds)}  (faltando {len(missing)}, extras {len(extra)}, labels inválidos {len(invalid)})")
    print(f"acurácia          : {acc:.1%}  {'OK' if acc >= ACC_TARGET else 'ABAIXO'} (alvo {ACC_TARGET:.0%})")
    print(f"macro-F1          : {macro_f1:.3f}")
    print()
    print("por classe (gold -> predito):")
    for l in present:
        row = confusion[l]
        tot = sum(row.values())
        hits = row[l]
        errs = ", ".join(f"{k or 'MISSING'}={v}" for k, v in row.most_common() if k != l)
        print(f"  {l:14s} {hits:3d}/{tot:<3d}  {errs}")

    if problems or invalid:
        print()
        for p in problems:
            print(f"  ! {p}")
        for i, l in list(invalid.items())[:10]:
            print(f"  ! label inválido em {i}: {l!r}")

    if len(sys.argv) > 3:
        with open(sys.argv[3], encoding="utf-8") as f:
            u = json.load(f)
        items = u.get("items") or n
        total = (u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
        avg = total / items if items else 0
        reported = u.get("avg_tokens_per_item")
        print()
        print(f"tokens            : {total} em {items} itens -> média {avg:.0f}/item  "
              f"{'OK' if avg <= TOKEN_BUDGET else 'ACIMA'} (orçamento {TOKEN_BUDGET})")
        if reported is not None and abs(reported - avg) > 1:
            print(f"  ! avg_tokens_per_item reportado ({reported}) difere do calculado ({avg:.0f})")
        print(f"modelo            : {u.get('model', '?')}")


if __name__ == "__main__":
    main()
