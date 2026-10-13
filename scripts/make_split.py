#!/usr/bin/env python3
"""Gera partições derivadas de data/train.jsonl (o original não é alterado).

Uso:
    python scripts/make_split.py [--train data/train.jsonl] [--out splits] [--seed 42]

Por classe (estratificado, embaralhado com seed fixa):
    holdout.jsonl      20% (5/classe = 40)  -> tocado só na medição final
    dev.jsonl          80% (20/classe = 160)
    fewshot_k3.jsonl   3/classe do dev (24) -> pool de exemplos
    fewshot_k1.jsonl   1/classe do dev (8), subconjunto do k3
    dev_eval.jsonl     dev menos o pool k3 (136) -> comparação de variantes de prompt
"""
import argparse
import json
import random
from collections import defaultdict
from pathlib import Path


def stratified_split(rows, seed=42, holdout_frac=0.2, pool_per_class=3):
    by_label = defaultdict(list)
    for r in sorted(rows, key=lambda r: r["id"]):
        by_label[r["label"]].append(r)
    rng = random.Random(seed)
    parts = {"holdout": [], "dev": [], "fewshot_k3": [], "fewshot_k1": [], "dev_eval": []}
    for label in sorted(by_label):
        group = by_label[label][:]
        rng.shuffle(group)
        n_hold = round(len(group) * holdout_frac)
        hold, dev = group[:n_hold], group[n_hold:]
        parts["holdout"] += hold
        parts["dev"] += dev
        parts["fewshot_k3"] += dev[:pool_per_class]
        parts["fewshot_k1"] += dev[:1]
        parts["dev_eval"] += dev[pool_per_class:]
    for name in parts:
        parts[name].sort(key=lambda r: r["id"])
    return parts


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--train", default="data/train.jsonl")
    p.add_argument("--out", default="splits")
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()
    with open(args.train, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f if line.strip()]
    out = Path(args.out)
    out.mkdir(exist_ok=True)
    for name, part in stratified_split(rows, seed=args.seed).items():
        with open(out / f"{name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for r in part:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        print(f"{name}: {len(part)}")


if __name__ == "__main__":
    main()
