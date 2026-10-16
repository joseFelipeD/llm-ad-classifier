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

    def test_bool_or_negative_token_counts_are_rejected(self):
        for usage in ({"prompt_tokens": True, "completion_tokens": 5},
                      {"prompt_tokens": 10, "completion_tokens": -1},
                      {"prompt_tokens": "10", "completion_tokens": 5}):
            client, _ = make_client(FakeUrlopen(ok_response("ok", usage=usage)))
            client.complete([])
            self.assertEqual(client.meter.total_tokens, 0, usage)
            self.assertFalse(client.meter.exact, usage)

    def test_invalid_reasoning_detail_is_ignored(self):
        usage = {"prompt_tokens": 10, "completion_tokens": 5, "completion_tokens_details": {"reasoning_tokens": 9}}
        client, _ = make_client(FakeUrlopen(ok_response("ok", usage=usage)))
        client.complete([])
        self.assertEqual((client.meter.output_tokens, client.meter.reasoning_tokens), (5, 0))

    def test_usage_in_error_body_is_counted(self):
        body = json.dumps({"error": {"message": "json_validate_failed"},
                           "usage": {"prompt_tokens": 50, "completion_tokens": 30}}).encode()
        client, _ = make_client(FakeUrlopen(http_error(400, body=body)))
        with self.assertRaises(ApiError):
            client.complete([])
        self.assertEqual(client.meter.total_tokens, 80)
        self.assertTrue(client.meter.exact)

    def test_error_without_usage_makes_count_inexact(self):
        client, _ = make_client(FakeUrlopen(http_error(400)))
        with self.assertRaises(ApiError):
            client.complete([])
        self.assertFalse(client.meter.exact)

    def test_rejections_without_usage_keep_count_exact(self):
        client, _ = make_client(FakeUrlopen(http_error(429, retry_after=1), ok_response("ok")))
        client.complete([])
        self.assertTrue(client.meter.exact)
        client, _ = make_client(FakeUrlopen(http_error(401)))
        with self.assertRaises(ApiError):
            client.complete([])
        self.assertTrue(client.meter.exact)

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


def response_with_headers(remaining=None, reset=None, usage=None):
    resp = ok_response("ok", usage=usage or {"prompt_tokens": 900, "completion_tokens": 100})
    resp.headers = Message()
    if remaining is not None:
        resp.headers["x-ratelimit-remaining-tokens"] = str(remaining)
    if reset is not None:
        resp.headers["x-ratelimit-reset-tokens"] = reset
    return resp


class PacingBudgetLogTest(unittest.TestCase):
    def make(self, n_responses, **kw):
        clock = FakeClock()
        usage = {"prompt_tokens": 900, "completion_tokens": 400}  # 1300 por chamada
        fake = FakeUrlopen(*[ok_response("ok", usage=usage) for _ in range(n_responses)])
        client = GroqClient("sk-test", "m", urlopen=fake, sleep=clock.sleep, clock=clock, **kw)
        return client, clock, fake

    def test_tpm_pacing_waits_for_window(self):
        client, clock, _ = self.make(5, tpm_limit=4000, safety_margin=0)
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

    def test_safety_margin_makes_local_pacing_more_conservative(self):
        client, clock, _ = self.make(3, tpm_limit=4000, safety_margin=0.2)
        for _ in range(3):
            client.complete([])
        # 2600 usados + 1560 estimados (1300 * 1.2) > 4000: espera antes da 3ª
        self.assertEqual(len(clock.sleeps), 1)

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


class ServerHeadersTest(unittest.TestCase):
    def run_two(self, first, second=None, advance=0.0, **kw):
        clock = FakeClock()
        fake = FakeUrlopen(first, second or response_with_headers())
        client = GroqClient("sk-test", "m", urlopen=fake, sleep=clock.sleep, clock=clock, **kw)
        client.complete([])            # 1000 tokens -> próxima estimada em 1200
        clock.now += advance
        client.complete([])
        return clock.sleeps

    def test_low_remaining_waits_for_reset(self):
        self.assertEqual(self.run_two(response_with_headers(remaining=206, reset="7.5s")), [8.0])

    def test_enough_remaining_does_not_wait(self):
        self.assertEqual(self.run_two(response_with_headers(remaining=5000, reset="7.5s")), [])

    def test_margin_counts_against_remaining(self):
        # 1100 restantes cobririam os 1000 da chamada anterior, mas não os 1200 estimados
        self.assertEqual(self.run_two(response_with_headers(remaining=1100, reset="2s")), [2.5])

    def test_stale_server_state_is_ignored(self):
        self.assertEqual(self.run_two(response_with_headers(remaining=10, reset="3s"), advance=5), [])

    def test_invalid_or_missing_headers_are_ignored(self):
        for remaining, reset in [("abc", "2s"), (-5, "2s"), (10, "soon"), (10, "nans"), (10, None), (None, "2s")]:
            self.assertEqual(self.run_two(response_with_headers(remaining=remaining, reset=reset)), [],
                             (remaining, reset))

    def test_wait_is_capped(self):
        sleeps = self.run_two(response_with_headers(remaining=0, reset="5m"), max_backoff=60)
        self.assertEqual(sleeps, [60])

    def test_most_restrictive_applies(self):
        # local: 1000 + 1200 <= 4000 não espera; servidor: 50 restantes -> espera o reset
        sleeps = self.run_two(response_with_headers(remaining=50, reset="1.5s"), tpm_limit=4000)
        self.assertEqual(sleeps, [2.0])

    def test_headers_from_429_are_used_and_retry_after_kept(self):
        err = http_error(429, retry_after=3)
        err.headers["x-ratelimit-remaining-tokens"] = "0"
        err.headers["x-ratelimit-reset-tokens"] = "10s"
        clock = FakeClock()
        fake = FakeUrlopen(response_with_headers(), err, response_with_headers())
        client = GroqClient("sk-test", "m", urlopen=fake, sleep=clock.sleep, clock=clock)
        client.complete([])
        client.complete([])
        # retry-after (3 s) do 429, depois o reset informado (10 - 3 + 0.5)
        self.assertEqual(clock.sleeps, [3.0, 7.5])

    def test_parse_duration(self):
        from classifier.client import _parse_duration
        self.assertAlmostEqual(_parse_duration("8.07s"), 8.07)
        self.assertAlmostEqual(_parse_duration("1m26.4s"), 86.4)
        self.assertAlmostEqual(_parse_duration("250ms"), 0.25)
        self.assertAlmostEqual(_parse_duration("1h"), 3600)
        for bad in ("", "  ", "abc", "5", "5x", "-1s", None, 3):
            self.assertIsNone(_parse_duration(bad), bad)


if __name__ == "__main__":
    unittest.main()
