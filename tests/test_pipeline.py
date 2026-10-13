import unittest
from collections import Counter

from classifier.client import ApiError, Completion
from classifier.pipeline import Settings, classify_items
from fakes import FakeClient, as_json, items


class PipelineTest(unittest.TestCase):
    def test_happy_path_in_batches(self):
        client = FakeClient(lambda texts, n: as_json(["finance"] * len(texts)))
        r = classify_items(items(*"abcde"), client, Settings(batch_size=2))
        self.assertEqual(len(r.labels), 5)
        self.assertEqual([len(c) for c in client.calls], [2, 2, 1])
        self.assertEqual(r.failures, {})

    def test_only_blank_text_skips_api_html_goes_to_llm(self):
        client = FakeClient(lambda texts, n: as_json(["other"] * len(texts)))
        r = classify_items(items("", "  \t", "<a href='#'>&nbsp;</a>"), client)
        self.assertEqual(r.without_api, 2)
        self.assertEqual(client.calls, [["<a href='#'>&nbsp;</a>"]])
        self.assertEqual(r.labels, {"id1": "other", "id2": "other", "id3": "other"})

    def test_partial_answer_retries_only_missing(self):
        def respond(texts, n):
            return as_json(["travel", None, "health"]) if n == 1 else as_json(["fashion"])
        client = FakeClient(respond)
        r = classify_items(items("a", "b", "c"), client)
        self.assertEqual(client.calls, [["a", "b", "c"], ["b"]])
        self.assertEqual(r.labels, {"id1": "travel", "id2": "fashion", "id3": "health"})

    def test_garbage_splits_batch_then_isolates_bad_item(self):
        def respond(texts, n):
            if "bad" in texts:
                return "not json at all"
            return as_json(["technology"] * len(texts))
        client = FakeClient(respond)
        r = classify_items(items("a", "bad", "c", "d"), client, Settings(item_attempts=2))
        self.assertEqual(set(r.labels), {"id1", "id3", "id4"})
        self.assertEqual(list(r.failures), ["id2"])
        self.assertIn("JSON malformado", r.failures["id2"])
        self.assertEqual(Counter(tuple(c) for c in client.calls)[("bad",)], 2)  # 2 tentativas isoladas

    def test_invalid_label_never_becomes_other(self):
        client = FakeClient(lambda texts, n: as_json(["sports"] * len(texts)))
        r = classify_items(items("a"), client, Settings(item_attempts=3))
        self.assertEqual(r.labels, {})
        self.assertIn("label inválido", r.failures["id1"])
        self.assertEqual(len(client.calls), 3)

    def test_api_down_marks_batch_failed_without_extra_calls(self):
        def respond(texts, n):
            raise ApiError("esgotadas", status=503, retryable=True)
        client = FakeClient(respond)
        r = classify_items(items("a", "b", "c"), client, Settings(batch_size=2))
        self.assertEqual(set(r.failures), {"id1", "id2", "id3"})
        self.assertEqual(len(client.calls), 2)  # um por lote, sem dividir

    def test_non_retryable_400_is_split_like_bad_output(self):
        def respond(texts, n):
            if len(texts) > 1:
                raise ApiError("HTTP 400: json_validate_failed", status=400)
            return as_json(["finance"])
        r = classify_items(items("a", "b"), FakeClient(respond))
        self.assertEqual(len(r.labels), 2)

    def test_consecutive_errors_trip_circuit_breaker(self):
        def respond(texts, n):
            raise ApiError("HTTP 400: response_format não suportado", status=400)
        client = FakeClient(respond)
        with self.assertRaises(ApiError) as ctx:
            classify_items(items(*"abcdefgh"), client, Settings(max_consecutive_errors=4))
        self.assertTrue(ctx.exception.fatal)
        self.assertEqual(len(client.calls), 4)

    def test_success_resets_error_counter(self):
        def respond(texts, n):
            if n % 2:
                raise ApiError("esgotadas", status=503, retryable=True)
            return as_json(["finance"] * len(texts))
        r = classify_items(items(*"abcdef"), FakeClient(respond), Settings(batch_size=1, max_consecutive_errors=2))
        self.assertEqual((len(r.failures), len(r.labels)), (3, 3))

    def test_truncated_response_is_reported(self):
        class Truncated(FakeClient):
            def complete(self, messages, **kw):
                super().complete(messages, **kw)
                return Completion('{"labels": [{"i": 1, "label": "fin', "length")
        r = classify_items(items("a"), Truncated(lambda texts, n: ""))
        self.assertIn("finish_reason=length", r.failures["id1"])

    def test_fatal_error_propagates(self):
        def respond(texts, n):
            raise ApiError("HTTP 401", status=401, fatal=True)
        with self.assertRaises(ApiError):
            classify_items(items("a"), FakeClient(respond))


if __name__ == "__main__":
    unittest.main()
