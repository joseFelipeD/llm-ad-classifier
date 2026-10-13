#!/usr/bin/env python3
"""E0: smoke test com NO MÁXIMO UMA requisição HTTP à API.

Usa o caminho real (prompt, cliente, parser, pipeline, usage.json), mas com
max_retries=0 e um invólucro que recusa uma segunda chamada (o pipeline reenviaria
itens em resposta parcial). Guarda a resposta bruta da API (sem a chave) para
inspecionar `usage` e os headers de rate limit.

Uso:
    python scripts/smoke_test.py splits/fewshot_k3.jsonl --n 20 --out runs/e0
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import classify  # noqa: E402
from classifier.client import ApiError, GroqClient, UsageMeter  # noqa: E402
from classifier.dataset import load_items  # noqa: E402
from classifier.pipeline import Settings, classify_items  # noqa: E402


class OneCallClient:
    """Repassa a primeira chamada; qualquer outra vira erro fatal (sem rede)."""

    def __init__(self, client):
        self.client = client
        self.calls = 0

    def complete(self, *args, **kwargs):
        self.calls += 1
        if self.calls > 1:
            raise ApiError("E0 limitado a 1 chamada: o pipeline pediu uma segunda", fatal=True)
        return self.client.complete(*args, **kwargs)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("input")
    p.add_argument("--n", type=int, default=20)
    p.add_argument("--out", default="runs/e0")
    p.add_argument("--model", default="openai/gpt-oss-20b")
    p.add_argument("--format", default="json")
    p.add_argument("--reasoning-effort", default="low")
    args = p.parse_args()

    items = load_items(args.input)[:args.n]
    classify.load_dotenv()
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        sys.exit("GROQ_API_KEY não definida")

    captured = {}

    def capturing_urlopen(request, timeout):
        try:
            resp = urllib.request.urlopen(request, timeout=timeout)
        except urllib.error.HTTPError as e:
            captured["status"] = e.code
            captured["headers"] = _rate_headers(e.headers)
            raise
        with resp:
            raw = resp.read()
            captured["status"] = resp.status
            captured["headers"] = _rate_headers(resp.headers)
        captured["body"] = json.loads(raw)
        return io.BytesIO(raw)

    meter = UsageMeter()
    client = OneCallClient(GroqClient(api_key, args.model, meter=meter, max_retries=0, urlopen=capturing_urlopen))
    settings = Settings(fmt=args.format, batch_size=args.n, reasoning_effort=args.reasoning_effort)

    out = Path(args.out)
    out.parent.mkdir(exist_ok=True)
    try:
        result = classify_items(items, client, settings)
    except ApiError as e:
        print(f"abortado: {e}", file=sys.stderr)
        result = None
    usage = classify.build_usage(meter, len(items), args.model, settings, result, 0)

    (out.parent / f"{out.name}_usage.json").write_text(json.dumps(usage, indent=2) + "\n", encoding="utf-8")
    (out.parent / f"{out.name}_response.json").write_text(
        json.dumps(captured, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with open(out.parent / f"{out.name}_gold.jsonl", "w", encoding="utf-8", newline="\n") as f:
        src = {json.loads(l)["id"]: l for l in open(args.input, encoding="utf-8") if l.strip()}
        for it in items:
            f.write(src[it.id].rstrip("\n") + "\n")
    if result is not None:
        with open(out.parent / f"{out.name}.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for it in items:
                if it.id in result.labels:
                    f.write(json.dumps({"id": it.id, "label": result.labels[it.id]}) + "\n")
        for item_id, reason in result.failures.items():
            print(f"falha: {item_id}: {reason}", file=sys.stderr)
    print(json.dumps({"requisicoes_http": meter.http_attempts, "chamadas_pipeline": client.calls,
                      "status": captured.get("status")}, ensure_ascii=False))


def _rate_headers(headers):
    if not headers:
        return {}
    keep = ("x-ratelimit-", "retry-after", "x-request-id")
    return {k: v for k, v in headers.items() if k.lower().startswith(keep)}


if __name__ == "__main__":
    main()
