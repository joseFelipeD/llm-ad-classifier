import http.client
import io
import json
import socket
import unittest
import urllib.error
from email.message import Message

from classifier.client import ApiError, GroqClient


def ok_response(content, usage=None, finish_reason="stop"):
    body = {"choices": [{"message": {"content": content}, "finish_reason": finish_reason}]}
    if usage is not False:
        body["usage"] = usage or {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120}
    return io.BytesIO(json.dumps(body).encode())


def http_error(code, retry_after=None, body=b'{"error": {"message": "boom"}}'):
    headers = Message()
    if retry_after is not None:
        headers["retry-after"] = str(retry_after)
    return urllib.error.HTTPError("https://x", code, "err", headers, io.BytesIO(body))


class FakeUrlopen:
    """Devolve/lança os itens de `script` em ordem e guarda as requisições."""

    def __init__(self, *script):
        self.script = list(script)
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        step = self.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


def make_client(urlopen, **kw):
    sleeps = []
    client = GroqClient("sk-test", "model-x", urlopen=urlopen, sleep=sleeps.append, **kw)
    return client, sleeps


class GroqClientTest(unittest.TestCase):
    def test_success_records_usage_and_payload(self):
        fake = FakeUrlopen(ok_response("hi"))
        client, _ = make_client(fake)
        c = client.complete([{"role": "user", "content": "x"}], response_format={"type": "json_object"},
                            max_completion_tokens=50, reasoning_effort="low")
        self.assertEqual(c.content, "hi")
        self.assertEqual((client.meter.input_tokens, client.meter.output_tokens), (100, 20))
        payload = json.loads(fake.requests[0].data)
        self.assertEqual(payload["model"], "model-x")
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertFalse(payload["include_reasoning"])
        self.assertEqual(fake.requests[0].get_header("Authorization"), "Bearer sk-test")

    def test_no_reasoning_params_when_disabled(self):
        fake = FakeUrlopen(ok_response("hi"))
        client, _ = make_client(fake)
        client.complete([], reasoning_effort=None)
        payload = json.loads(fake.requests[0].data)
        self.assertNotIn("reasoning_effort", payload)
        self.assertNotIn("include_reasoning", payload)

    def test_429_respects_retry_after_then_succeeds(self):
        fake = FakeUrlopen(http_error(429, retry_after=7), ok_response("ok"))
        client, sleeps = make_client(fake)
        self.assertEqual(client.complete([]).content, "ok")
        self.assertEqual(sleeps, [7.0])
        self.assertEqual(client.meter.http_attempts, 2)

    def test_5xx_and_timeouts_use_exponential_backoff(self):
        fake = FakeUrlopen(http_error(503), socket.timeout("t"), urllib.error.URLError("dns"), ok_response("ok"))
        client, sleeps = make_client(fake, backoff=1.0, max_backoff=3.0)
        self.assertEqual(client.complete([]).content, "ok")
        self.assertEqual(sleeps, [1.0, 2.0, 3.0])  # 4.0 limitado a max_backoff

    def test_retries_exhausted_raise_retryable(self):
        fake = FakeUrlopen(*[http_error(500)] * 3)
        client, _ = make_client(fake, max_retries=2)
        with self.assertRaises(ApiError) as ctx:
            client.complete([])
        self.assertTrue(ctx.exception.retryable)
        self.assertFalse(ctx.exception.fatal)
        self.assertEqual(len(fake.requests), 3)

    def test_auth_error_is_fatal_without_retry(self):
        fake = FakeUrlopen(http_error(401))
        client, sleeps = make_client(fake)
        with self.assertRaises(ApiError) as ctx:
            client.complete([])
        self.assertTrue(ctx.exception.fatal)
        self.assertEqual(sleeps, [])

    def test_400_is_not_retried_and_not_fatal(self):
        fake = FakeUrlopen(http_error(400, body=b'{"error": {"message": "json_validate_failed"}}'))
        client, _ = make_client(fake)
        with self.assertRaises(ApiError) as ctx:
            client.complete([])
        self.assertFalse(ctx.exception.retryable or ctx.exception.fatal)
        self.assertIn("json_validate_failed", str(ctx.exception))

    def test_unexpected_200_body(self):
        fake = FakeUrlopen(io.BytesIO(b"<html>oops</html>"))
        client, _ = make_client(fake)
        with self.assertRaises(ApiError):
            client.complete([])
        self.assertEqual(client.meter.responses_without_usage, 1)

    def test_missing_usage_is_counted_not_invented(self):
        client, _ = make_client(FakeUrlopen(ok_response("ok", usage=False)))
        client.complete([])
        self.assertEqual((client.meter.input_tokens, client.meter.output_tokens), (0, 0))
        self.assertEqual(client.meter.responses_without_usage, 1)

    def test_incomplete_read_is_retried_and_counted(self):
        class Broken(io.BytesIO):
            def read(self, *a):
                raise http.client.IncompleteRead(b"{")
        client, _ = make_client(FakeUrlopen(Broken(), ok_response("ok")))
        self.assertEqual(client.complete([]).content, "ok")
        self.assertEqual(client.meter.transport_errors, 1)
        self.assertFalse(client.meter.exact)

    def test_nan_retry_after_falls_back_to_backoff(self):
        client, sleeps = make_client(FakeUrlopen(http_error(429, retry_after="nan"), ok_response("ok")), backoff=1.0)
        client.complete([])
        self.assertEqual(sleeps, [1.0])

    def test_huge_retry_after_gives_up_immediately(self):
        fake = FakeUrlopen(http_error(429, retry_after=3600))
        client, sleeps = make_client(fake, max_backoff=60)
        with self.assertRaises(ApiError) as ctx:
            client.complete([])
        self.assertTrue(ctx.exception.retryable)
        self.assertEqual((sleeps, len(fake.requests)), ([], 1))

    def test_404_model_not_found_is_fatal(self):
        client, _ = make_client(FakeUrlopen(http_error(404)))
        with self.assertRaises(ApiError) as ctx:
            client.complete([])
        self.assertTrue(ctx.exception.fatal)

    def test_usage_recorded_even_if_choices_malformed(self):
        body = io.BytesIO(json.dumps({"choices": [], "usage": {"prompt_tokens": 5, "completion_tokens": 2}}).encode())
        client, _ = make_client(FakeUrlopen(body))
        with self.assertRaises(ApiError):
            client.complete([])
        self.assertEqual((client.meter.input_tokens, client.meter.output_tokens), (5, 2))

    def test_api_key_is_redacted_from_error_detail(self):
        err = http_error(400, body=b'{"error": {"message": "bad key sk-test here"}}')
        client, _ = make_client(FakeUrlopen(err))
        with self.assertRaises(ApiError) as ctx:
            client.complete([])
        self.assertNotIn("sk-test", str(ctx.exception))


class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


class PacingBudgetLogTest(unittest.TestCase):
    def make(self, n_responses, **kw):
        clock = FakeClock()
        usage = {"prompt_tokens": 900, "completion_tokens": 400}  # 1300 por chamada
        fake = FakeUrlopen(*[ok_response("ok", usage=usage) for _ in range(n_responses)])
        client = GroqClient("sk-test", "m", urlopen=fake, sleep=clock.sleep, clock=clock, **kw)
        return client, clock, fake

    def test_tpm_pacing_waits_for_window(self):
        client, clock, _ = self.make(5, tpm_limit=4000)
        for _ in range(5):
            client.complete([])
        # 3 chamadas (3900) cabem no minuto; a 4ª esperaria 5200 > 4000
        self.assertEqual(len(clock.sleeps), 1)
        self.assertAlmostEqual(clock.sleeps[0], 60.5)
        self.assertEqual(client.meter.total_tokens, 6500)

    def test_no_pacing_when_disabled(self):
        client, clock, _ = self.make(5)
        for _ in range(5):
            client.complete([])
        self.assertEqual(clock.sleeps, [])

    def test_token_budget_stops_before_exceeding(self):
        client, _, fake = self.make(5, token_budget=3000)
        client.complete([])
        client.complete([])            # 2600 usados
        with self.assertRaises(ApiError) as ctx:
            client.complete([])        # 2600 + 1300 estimado > 3000
        self.assertTrue(ctx.exception.fatal)
        self.assertEqual(len(fake.requests), 2)

    def test_call_log_records_success_and_failure(self):
        body = {"choices": [{"message": {"content": "ok"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 9, "completion_tokens": 5,
                          "completion_tokens_details": {"reasoning_tokens": 3}}}
        fake = FakeUrlopen(http_error(429, retry_after=1), io.BytesIO(json.dumps(body).encode()))
        client, _ = make_client(fake)
        client.complete([])
        calls = client.meter.calls
        self.assertEqual([c["status"] for c in calls], [429, 200])
        self.assertEqual(calls[0]["retry_after"], "1")
        self.assertEqual((calls[1]["prompt_tokens"], calls[1]["reasoning_tokens"]), (9, 3))
        self.assertEqual(client.meter.reasoning_tokens, 3)
        self.assertEqual(client.meter.output_tokens, 5)  # reasoning não somado de novo


if __name__ == "__main__":
    unittest.main()
