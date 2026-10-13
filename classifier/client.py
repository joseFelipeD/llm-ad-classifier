"""Cliente mínimo (stdlib) para o endpoint chat/completions do Groq.

Retentativas: 429 (respeita `retry-after`), 408, 5xx, timeout e erro de rede/leitura,
com backoff exponencial limitado. Fatais (não adianta repetir): 401/403 (credencial)
e 404 (modelo/endpoint inexistente). Outros 4xx (ex.: 400 de validação de JSON) voltam
como erro não fatal para o pipeline decidir.
"""
import http.client
import json
import logging
import math
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

log = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://api.groq.com/openai/v1"
_RETRY_STATUS = {408, 429, 500, 502, 503, 504}
_FATAL_STATUS = {401, 403, 404}


class ApiError(Exception):
    def __init__(self, message, *, status=None, retryable=False, fatal=False):
        super().__init__(message)
        self.status = status
        self.retryable = retryable
        self.fatal = fatal


@dataclass
class Completion:
    content: object
    finish_reason: object = None


class UsageMeter:
    """Soma o `usage` de TODAS as respostas da API, inclusive as de retentativas.

    Nada é estimado: respostas sem `usage` e falhas de transporte (em que o servidor
    pode ter processado o pedido) são apenas contadas, e tornam a soma não exata.
    """

    def __init__(self):
        self.input_tokens = 0
        self.output_tokens = 0
        self.http_attempts = 0
        self.responses_without_usage = 0
        self.transport_errors = 0

    def record(self, usage):
        if isinstance(usage, dict) and isinstance(usage.get("prompt_tokens"), int) \
                and isinstance(usage.get("completion_tokens"), int):
            self.input_tokens += usage["prompt_tokens"]
            self.output_tokens += usage["completion_tokens"]
        else:
            self.responses_without_usage += 1

    @property
    def exact(self):
        return self.responses_without_usage == 0 and self.transport_errors == 0


class GroqClient:
    def __init__(self, api_key, model, *, meter=None, base_url=DEFAULT_BASE_URL, timeout=60.0,
                 max_retries=4, backoff=2.0, max_backoff=60.0,
                 urlopen=urllib.request.urlopen, sleep=time.sleep):
        self.api_key = api_key
        self.model = model
        self.meter = meter or UsageMeter()
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.timeout = timeout
        self.max_retries = max_retries
        self.backoff = backoff
        self.max_backoff = max_backoff
        self._urlopen = urlopen
        self._sleep = sleep

    def complete(self, messages, *, response_format=None, max_completion_tokens=None,
                 reasoning_effort=None):
        payload = {"model": self.model, "messages": messages}
        if response_format:
            payload["response_format"] = response_format
        if max_completion_tokens:
            payload["max_completion_tokens"] = max_completion_tokens
        if reasoning_effort:
            payload["reasoning_effort"] = reasoning_effort
            payload["include_reasoning"] = False  # não devolve o texto do raciocínio
        body = json.dumps(payload).encode("utf-8")

        for attempt in range(self.max_retries + 1):
            try:
                return self._send(body)
            except _Retry as r:
                log.warning("tentativa %d/%d falhou: %s", attempt + 1, self.max_retries + 1, r.reason)
                if r.retry_after is not None and r.retry_after > self.max_backoff:
                    # Ex.: cota diária esgotada; esperar 60 s e repetir não resolve.
                    raise ApiError(f"{r.reason}; retry-after={r.retry_after:.0f}s excede o limite de espera",
                                   status=r.status, retryable=True) from None
                if attempt == self.max_retries:
                    raise ApiError(f"esgotadas {self.max_retries + 1} tentativas: {r.reason}",
                                   status=r.status, retryable=True) from None
                wait = r.retry_after if r.retry_after is not None else self.backoff * 2 ** attempt
                self._sleep(min(wait, self.max_backoff))

    def _send(self, body):
        request = urllib.request.Request(self.url, data=body, method="POST", headers={
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "User-Agent": "classificador-anuncios/1.0",
        })
        self.meter.http_attempts += 1
        try:
            with self._urlopen(request, timeout=self.timeout) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as e:
            detail = self._redact(_error_detail(e))
            if e.code in _FATAL_STATUS:
                raise ApiError(f"HTTP {e.code}: {detail}", status=e.code, fatal=True) from None
            if e.code in _RETRY_STATUS:
                raise _Retry(f"HTTP {e.code}: {detail}", e.code, _retry_after(e)) from None
            raise ApiError(f"HTTP {e.code}: {detail}", status=e.code) from None
        except (OSError, http.client.HTTPException) as e:
            # URLError, timeout, conexão resetada, SSL, IncompleteRead...
            self.meter.transport_errors += 1
            raise _Retry(f"rede/timeout: {type(e).__name__}: {e}", None, None) from None

        try:
            data = json.loads(raw)
        except ValueError:
            data = None
        self.meter.record(data.get("usage") if isinstance(data, dict) else None)
        try:
            choice = data["choices"][0]
            content = choice["message"].get("content")
        except (KeyError, IndexError, TypeError, AttributeError):
            raise ApiError("resposta HTTP 200 sem o formato chat/completions esperado") from None
        return Completion(content, choice.get("finish_reason"))

    def _redact(self, text):
        return text.replace(self.api_key, "***") if self.api_key else text


class _Retry(Exception):
    def __init__(self, reason, status, retry_after):
        super().__init__(reason)
        self.reason = reason
        self.status = status
        self.retry_after = retry_after


def _retry_after(http_error):
    """Segundos do header `retry-after`, ou None se ausente/ilegível/não finito."""
    value = http_error.headers.get("retry-after") if http_error.headers else None
    try:
        seconds = float(value)
    except (TypeError, ValueError):
        return None
    return max(seconds, 0.0) if math.isfinite(seconds) else None


def _error_detail(http_error):
    try:
        body = http_error.read().decode("utf-8", "replace")
        return json.loads(body).get("error", {}).get("message", body)[:300]
    except Exception:
        return str(http_error.reason)[:300]
