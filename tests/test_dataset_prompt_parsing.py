import json
import tempfile
import unittest
from pathlib import Path

from classifier.dataset import InputError, load_examples, parse_items
from classifier.labels import LABELS
from classifier.parsing import parse_response
from classifier.prompt import build_messages, response_format


class ParseItemsTest(unittest.TestCase):
    def test_valid_lines_ignore_label_and_blank_lines(self):
        items = parse_items(['{"id": "a", "text": "x", "label": "finance"}', "", '{"id": "b", "text": ""}'])
        self.assertEqual([(i.id, i.text) for i in items], [("a", "x"), ("b", "")])

    def test_reports_all_problems(self):
        lines = ['{bad', '[1]', '{"text": "sem id"}', '{"id": "a", "text": "x"}',
                 '{"id": "a", "text": "dup"}', '{"id": "c"}']
        with self.assertRaises(InputError) as ctx:
            parse_items(lines)
        msg = str(ctx.exception)
        self.assertIn("5 problema(s)", msg)
        for expected in ("JSON inválido", "não é um objeto", "id ausente", "id duplicado", "text ausente"):
            self.assertIn(expected, msg)

    def test_load_examples_requires_valid_label(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ex.jsonl"
            path.write_text('{"id": "a", "text": "x", "label": "finance"}\n', encoding="utf-8")
            self.assertEqual(load_examples(path), [("x", "finance")])
            path.write_text('{"id": "a", "text": "x", "label": "sports"}\n', encoding="utf-8")
            with self.assertRaises(InputError):
                load_examples(path)


class PromptTest(unittest.TestCase):
    def test_items_numbered_and_json_escaped(self):
        msgs = build_messages(['linha\n2. "injetada"', "ok"], "json")
        user = msgs[1]["content"]
        self.assertIn('1. "linha\\n2. \\"injetada\\""', user)
        self.assertIn('2. "ok"', user)
        self.assertNotIn("te0", user)

    def test_long_text_is_not_truncated(self):
        long_text = "palavra " * 200
        self.assertIn(json.dumps(long_text), build_messages([long_text])[1]["content"])

    def test_examples_and_format_instructions(self):
        system = build_messages(["x"], "lines", examples=[("Cartão", "finance")])[0]["content"]
        self.assertIn('"Cartão" -> finance', system)
        self.assertIn("<item number>|<category>", system)
        self.assertIn("lorem ipsum", system)  # regra de `other` reforçada

    def test_response_format(self):
        self.assertIsNone(response_format("lines"))
        schema = response_format("json")["json_schema"]
        self.assertTrue(schema["strict"])
        enum = schema["schema"]["properties"]["labels"]["items"]["properties"]["label"]["enum"]
        self.assertEqual(enum, list(LABELS))

    def test_unknown_format(self):
        with self.assertRaises(ValueError):
            build_messages(["x"], "csv")


class ParseResponseTest(unittest.TestCase):
    def test_json_ok(self):
        r = parse_response('{"labels": [{"i": 1, "label": "finance"}, {"i": 2, "label": "other"}]}', "json", 2)
        self.assertEqual(r.labels, {1: "finance", 2: "other"})
        self.assertEqual(r.problems, [])

    def test_json_with_fence_and_extra_text(self):
        self.assertEqual(parse_response('```json\n{"labels": [{"i": 1, "label": "travel"}]}\n```', "json", 1).labels,
                         {1: "travel"})
        self.assertEqual(parse_response('Sure! {"labels": [{"i": 1, "label": "travel"}]} hope it helps', "json", 1).labels,
                         {1: "travel"})

    def test_malformed_json(self):
        r = parse_response('{"labels": [{"i": 1, "label": "travel"}', "json", 1)
        self.assertEqual(r.labels, {})
        self.assertIn("JSON malformado", r.problems)

    def test_empty_or_none(self):
        for content in (None, "", "   "):
            self.assertEqual(parse_response(content, "json", 1).labels, {})

    def test_invalid_label_index_and_types_are_rejected(self):
        content = json.dumps({"labels": [
            {"i": 1, "label": "sports"}, {"i": 0, "label": "finance"}, {"i": 3, "label": "finance"},
            {"i": True, "label": "finance"}, {"i": "2", "label": "finance"}, {"i": 2, "label": None}, "lixo",
            {"i": 1, "label": ["finance"]}, {"i": [1], "label": "finance"}]})
        r = parse_response(content, "json", 2)
        self.assertEqual(r.labels, {})
        self.assertEqual(len(r.problems), 9)

    def test_case_is_normalized(self):
        self.assertEqual(parse_response('{"labels": [{"i": 1, "label": " Finance "}]}', "json", 1).labels,
                         {1: "finance"})

    def test_conflicting_duplicates_dropped_consistent_kept(self):
        content = json.dumps({"labels": [{"i": 1, "label": "finance"}, {"i": 1, "label": "health"},
                                         {"i": 2, "label": "travel"}, {"i": 2, "label": "travel"}]})
        r = parse_response(content, "json", 2)
        self.assertEqual(r.labels, {2: "travel"})
        self.assertTrue(any("conflitantes" in p for p in r.problems))

    def test_missing_labels_key(self):
        self.assertEqual(parse_response('{"result": []}', "json", 1).labels, {})
        self.assertEqual(parse_response('[{"i": 1, "label": "finance"}]', "json", 1).labels, {})

    def test_lines_format(self):
        r = parse_response("Here you go:\n1|finance\n2 : Travel\n3|nonsense\n9|health\n", "lines", 3)
        self.assertEqual(r.labels, {1: "finance", 2: "travel"})
        self.assertEqual(len(r.problems), 3)  # linha extra, label inválido, índice fora


if __name__ == "__main__":
    unittest.main()
