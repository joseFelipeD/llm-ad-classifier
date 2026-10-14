#!/usr/bin/env python3
"""Classifica títulos de anúncios via LLM.

Uso:
    python classify.py data/test_unlabeled.jsonl --usage usage.json > predictions.jsonl

stdout recebe somente JSONL {"id", "label"}; logs e erros vão para stderr.
A chave vem de GROQ_API_KEY (ambiente ou arquivo .env, nunca impresso).

Códigos de saída:
    0  todos os itens classificados
    1  execução incompleta: algum item ficou sem label; stdout fica VAZIO
       (falhas no stderr/--failures, predições obtidas em --partial)
    2  erro de entrada/configuração, erro fatal da API (ex.: 401) ou falhas seguidas
"""
import argparse
import hashlib
import json
import logging
import os
import sys
import time

from classifier.client import GroqClient, UsageMeter
from classifier.dataset import InputError, load_examples, load_items
from classifier.pipeline import Settings, classify_items
from classifier.prompt import FORMATS, build_messages

DEFAULT_MODEL = "openai/gpt-oss-20b"
log = logging.getLogger("classify")


def parse_args(argv):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("input", help="JSONL com {id, text} (campos extras são ignorados)")
    p.add_argument("--model", default=os.environ.get("GROQ_MODEL", DEFAULT_MODEL))
    p.add_argument("--format", choices=FORMATS, default="json",
                   help="json = JSON Schema estrito; lines = texto '<n>|<label>'")
    p.add_argument("--batch-size", type=int, default=20)
    p.add_argument("--examples", help="JSONL {id, text, label} usado como few-shot")
    p.add_argument("--reasoning-effort", default="low",
                   help="low|medium|high para gpt-oss; 'none' para não enviar o parâmetro")
    p.add_argument("--max-completion-tokens", type=int, default=2048)
    p.add_argument("--timeout", type=float, default=60.0)
    p.add_argument("--max-retries", type=int, default=4)
    p.add_argument("--usage", help="grava o consumo real de tokens neste arquivo JSON")
    p.add_argument("--failures", help="grava os itens sem label neste arquivo JSONL")
    p.add_argument("--partial", help="em execução incompleta, grava aqui as predições obtidas")
    p.add_argument("--call-log", help="grava um registro JSONL por requisição HTTP (inclusive falhas)")
    p.add_argument("--tpm-limit", type=int, default=6000,
                   help="tokens por minuto a não ultrapassar (plano gratuito do Groq: 8000); 0 desliga")
    p.add_argument("--max-total-tokens", type=int,
                   help="teto operacional: não faz chamadas que levariam o total acima disto")
    return p.parse_args(argv)


def load_dotenv(path=".env"):
    """Carrega KEY=VALUE de .env sem sobrescrever variáveis já definidas."""
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8-sig") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip("'\""))


def build_usage(meter, n_items, model, settings, result, n_examples, **extra):
    """Conteúdo de usage.json; `result` None significa execução abortada."""
    total = meter.input_tokens + meter.output_tokens
    return {
        "items": n_items,
        "input_tokens": meter.input_tokens,
        "output_tokens": meter.output_tokens,
        "avg_tokens_per_item": round(total / n_items, 1) if n_items else 0,
        "model": model,
        "complete": result is not None and not result.failures,
        "aborted": result is None,
        "items_failed": len(result.failures) if result else None,
        "items_without_api_call": result.without_api if result else None,
        # false se alguma resposta veio sem `usage` ou houve falha de transporte
        # (o servidor pode ter cobrado tokens que não conhecemos).
        "usage_exact": meter.exact,
        "http_attempts": meter.http_attempts,
        "responses_without_usage": meter.responses_without_usage,
        "transport_errors": meter.transport_errors,
        "reasoning_tokens_included_in_output": meter.reasoning_tokens,
        "responses_with_problems": len(result.problems) if result else None,
        "output_format": settings.fmt,
        "batch_size": settings.batch_size,
        "reasoning_effort": settings.reasoning_effort,
        "max_completion_tokens": settings.max_completion_tokens,
        "few_shot_examples": n_examples,
        **extra,
    }


def write_jsonl(stream, rows):
    for row in rows:
        stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def main(argv=None, client_factory=GroqClient, stdout=None):
    stdout = stdout or sys.stdout
    args = parse_args(argv)
    try:
        items = load_items(args.input)
        examples = tuple(load_examples(args.examples)) if args.examples else ()
    except (OSError, InputError) as e:
        log.error("%s", e)
        return 2
    if args.batch_size < 1:
        log.error("--batch-size deve ser >= 1")
        return 2

    load_dotenv()
    api_key = os.environ.get("GROQ_API_KEY", "").strip()
    if not api_key:
        log.error("GROQ_API_KEY não definida (ambiente ou .env)")
        return 2

    effort = None if args.reasoning_effort.lower() == "none" else args.reasoning_effort
    settings = Settings(fmt=args.format, batch_size=args.batch_size, examples=examples,
                        max_completion_tokens=args.max_completion_tokens, reasoning_effort=effort)
    meter = UsageMeter()
    client = client_factory(api_key, args.model, meter=meter, timeout=args.timeout,
                            max_retries=args.max_retries, tpm_limit=args.tpm_limit or None,
                            token_budget=args.max_total_tokens)
    system_prompt = build_messages([], settings.fmt, examples)[0]["content"]
    log.info("%d itens, modelo %s, formato %s, lote %d, %d exemplos",
             len(items), args.model, args.format, args.batch_size, len(examples))

    started = time.monotonic()
    try:
        result = classify_items(items, client, settings)
    except Exception as e:  # ApiError fatal ou qualquer erro inesperado: preserva o usage
        log.error("execução abortada: %s: %s", type(e).__name__, e)
        result = None
    # usage e log de chamadas antes do stdout: os tokens gastos ficam registrados de qualquer forma.
    _write_usage(args.usage, build_usage(
        meter, len(items), args.model, settings, result, len(examples),
        elapsed_seconds=round(time.monotonic() - started, 1),
        system_prompt_sha256=hashlib.sha256(system_prompt.encode("utf-8")).hexdigest()[:16]))
    if args.call_log:
        with open(args.call_log, "w", encoding="utf-8", newline="\n") as f:
            write_jsonl(f, meter.calls)
    if result is None:
        return 2
    predictions = [{"id": it.id, "label": result.labels[it.id]} for it in items if it.id in result.labels]
    total = meter.input_tokens + meter.output_tokens
    log.info("tokens: %d entrada + %d saída = %d (média %.1f/item), %d requisições HTTP%s",
             meter.input_tokens, meter.output_tokens, total, total / len(items) if items else 0,
             meter.http_attempts, "" if meter.exact else " (contagem NÃO exata)")

    if result.failures:
        if args.failures:
            with open(args.failures, "w", encoding="utf-8", newline="\n") as f:
                write_jsonl(f, ({"id": i, "error": r} for i, r in result.failures.items()))
        if args.partial:
            with open(args.partial, "w", encoding="utf-8", newline="\n") as f:
                write_jsonl(f, predictions)
        for item_id, reason in result.failures.items():
            log.error("sem label: %s (%s)", item_id, reason)
        # stdout fica vazio: um `> predictions.jsonl` incompleto não pode parecer entregável.
        log.error("EXECUÇÃO INCOMPLETA: %d de %d itens sem label; nada escrito no stdout%s",
                  len(result.failures), len(items),
                  f" (parciais em {args.partial})" if args.partial else "")
        return 1

    write_jsonl(stdout, predictions)  # mantém a ordem da entrada
    stdout.flush()
    return 0


def _write_usage(path, usage):
    if path:
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(usage, f, indent=2)
            f.write("\n")


if __name__ == "__main__":
    # No Windows o padrão é cp1252 e CRLF; JSONL e logs saem sempre em UTF-8 com \n.
    sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    sys.stderr.reconfigure(encoding="utf-8")
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    sys.exit(main())
