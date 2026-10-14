"""Classificação em lotes com recuperação de respostas parciais.

Política de falhas (nenhuma vira rótulo silenciosamente):
- Texto vazio ou só espaços -> `other` por regra explícita do README, sem API.
  Qualquer outro texto (inclusive HTML ou lorem ipsum) vai para o LLM.
- Resposta com itens faltando, label inválido ou JSON quebrado -> os itens sem
  label válido são reenviados (lote dividido ao meio se nada foi aproveitado);
  um item isolado tem `item_attempts` tentativas.
- API indisponível depois das retentativas do cliente -> itens do lote viram falha.
- Erro fatal (401/403/404) -> interrompe tudo.
- `max_consecutive_errors` chamadas seguidas com erro de API (sem nenhuma resposta
  aproveitável no meio) -> interrompe tudo, em vez de repetir a falha lote a lote
  (ex.: modelo sem suporte a json_schema, API fora do ar).
Itens que falham ficam em `failures`, sem label.
"""
import logging
from dataclasses import dataclass, field

from .client import ApiError
from .parsing import parse_response
from .prompt import build_messages, response_format

log = logging.getLogger(__name__)


@dataclass
class Settings:
    fmt: str = "json"
    batch_size: int = 20
    examples: tuple = ()
    max_completion_tokens: int = 2048
    reasoning_effort: object = "low"
    item_attempts: int = 2
    max_consecutive_errors: int = 4


@dataclass
class Result:
    labels: dict = field(default_factory=dict)     # id -> label
    failures: dict = field(default_factory=dict)   # id -> motivo
    without_api: int = 0
    consecutive_errors: int = 0
    problems: list = field(default_factory=list)   # um motivo por resposta/erro que deixou itens sem label


def classify_items(items, client, settings=None):
    settings = settings or Settings()
    if settings.batch_size < 1:
        raise ValueError("batch_size deve ser >= 1")
    result = Result()
    pending = []
    for item in items:
        if item.text.strip():
            pending.append(item)
        else:
            result.labels[item.id] = "other"
            result.without_api += 1
    for start in range(0, len(pending), settings.batch_size):
        batch = pending[start:start + settings.batch_size]
        _classify_batch(batch, client, settings, result, attempt=1)
        log.info("progresso: %d/%d itens enviados", min(start + settings.batch_size, len(pending)), len(pending))
    return result


def _classify_batch(batch, client, settings, result, attempt):
    try:
        completion = client.complete(
            build_messages([it.text for it in batch], settings.fmt, settings.examples),
            response_format=response_format(settings.fmt),
            max_completion_tokens=settings.max_completion_tokens,
            reasoning_effort=settings.reasoning_effort,
        )
    except ApiError as e:
        if e.fatal:
            raise
        result.consecutive_errors += 1
        if result.consecutive_errors >= settings.max_consecutive_errors:
            raise ApiError(f"{result.consecutive_errors} chamadas seguidas falharam; último erro: {e}",
                           status=e.status, fatal=True) from e
        if e.retryable:
            # O cliente já esgotou as retentativas: não insistir multiplicando chamadas.
            for it in batch:
                result.failures[it.id] = f"API indisponível: {e}"
            return
        got, reason = {}, str(e)
    else:
        result.consecutive_errors = 0
        parsed = parse_response(completion.content, settings.fmt, len(batch))
        got = parsed.labels
        reason = "; ".join(parsed.problems) or "item ausente na resposta"
        if completion.finish_reason == "length":
            reason = "resposta cortada (finish_reason=length); " + reason

    for idx, it in enumerate(batch, 1):
        if idx in got:
            result.labels[it.id] = got[idx]
    missing = [it for idx, it in enumerate(batch, 1) if idx not in got]
    if not missing:
        return
    result.problems.append(f"lote de {len(batch)}, {len(missing)} sem label: {reason}")
    log.warning("lote de %d: %d sem label válido (%s)", len(batch), len(missing), reason)

    if len(missing) < len(batch):
        _classify_batch(missing, client, settings, result, attempt=1)
    elif len(batch) > 1:
        half = len(batch) // 2
        _classify_batch(batch[:half], client, settings, result, attempt=1)
        _classify_batch(batch[half:], client, settings, result, attempt=1)
    elif attempt < settings.item_attempts:
        _classify_batch(batch, client, settings, result, attempt + 1)
    else:
        result.failures[batch[0].id] = reason
