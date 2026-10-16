import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import classify
from classifier.client import ApiError
from fakes import FakeClient, as_json

ROOT = Path(__file__).resolve().parent.parent


class CliTest(unittest.TestCase):
    def run_cli(self, rows, respond, extra=()):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.jsonl"
            src.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            usage_path, fail_path = Path(tmp) / "usage.json", Path(tmp) / "fail.jsonl"
            out = io.StringIO()
            factory = lambda key, model, meter, **kw: FakeClient(respond, meter)
            with mock.patch.dict(os.environ, {"GROQ_API_KEY": "sk-test"}):
                code = classify.main([str(src), "--usage", str(usage_path), "--failures", str(fail_path), *extra],
                                     client_factory=factory, stdout=out)
            usage = json.loads(usage_path.read_text()) if usage_path.exists() else None
            failures = fail_path.read_text() if fail_path.exists() else ""
            return code, out.getvalue(), usage, failures

    def test_complete_run(self):
        rows = [{"id": "x1", "text": "a", "label": "finance"}, {"id": "x2", "text": ""}]
        code, out, usage, _ = self.run_cli(rows, lambda t, n: as_json(["travel"] * len(t)))
        self.assertEqual(code, 0)
        lines = [json.loads(l) for l in out.splitlines()]
        self.assertEqual(lines, [{"id": "x1", "label": "travel"}, {"id": "x2", "label": "other"}])
        self.assertEqual(usage["items"], 2)
        self.assertEqual((usage["input_tokens"], usage["output_tokens"]), (10, 1))
        self.assertEqual(usage["avg_tokens_per_item"], 5.5)
        self.assertTrue(usage["complete"])
        self.assertEqual(usage["responses_with_problems"], 0)
        self.assertEqual(len(usage["system_prompt_sha256"]), 16)
        self.assertIn("elapsed_seconds", usage)

    def test_label_field_of_input_is_not_sent_to_model(self):
        seen = []
        def respond(texts, n):
            seen.extend(texts)
            return as_json(["finance"] * len(texts))
        self.run_cli([{"id": "x1", "text": "Cartão", "label": "health"}], respond)
        self.assertEqual(seen, ["Cartão"])

    def test_incomplete_run_exit_1_empty_stdout_partial_file(self):
        rows = [{"id": "x1", "text": "a"}, {"id": "x2", "text": "b"}]
        respond = lambda t, n: as_json(["finance" if x == "a" else "bogus" for x in t])
        with tempfile.TemporaryDirectory() as tmp:
            partial = Path(tmp) / "partial.jsonl"
            code, out, usage, failures = self.run_cli(rows, respond, extra=["--partial", str(partial)])
            self.assertEqual([json.loads(l) for l in partial.read_text().splitlines()],
                             [{"id": "x1", "label": "finance"}])
        self.assertEqual((code, out), (1, ""))
        self.assertFalse(usage["complete"])
        self.assertEqual(usage["items_failed"], 1)
        self.assertIn('"x2"', failures)

    def test_unexpected_exception_exit_2_and_usage_written(self):
        def respond(t, n):
            raise RuntimeError("bug")
        code, out, usage, _ = self.run_cli([{"id": "x1", "text": "a"}], respond)
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(usage["aborted"])

    def test_output_order_follows_input_after_retries(self):
        rows = [{"id": f"x{i}", "text": t} for i, t in enumerate(["a", "", "b", "c"])]
        def respond(texts, n):  # a 1ª chamada omite "b", que é reenviado sozinho
            return as_json([None if (x == "b" and n == 1) else "travel" for x in texts])
        code, out, _, _ = self.run_cli(rows, respond)
        self.assertEqual(code, 0)
        self.assertEqual([json.loads(l)["id"] for l in out.splitlines()], ["x0", "x1", "x2", "x3"])

    def test_fatal_api_error_exit_2(self):
        def respond(t, n):
            raise ApiError("HTTP 401", status=401, fatal=True)
        code, out, usage, _ = self.run_cli([{"id": "x1", "text": "a"}], respond)
        self.assertEqual((code, out), (2, ""))
        self.assertTrue(usage["aborted"])

    def test_invalid_input_exit_2_before_api(self):
        called = []
        code, out, _, _ = self.run_cli([{"id": "x1", "text": "a"}, {"id": "x1", "text": "b"}],
                                       lambda t, n: called.append(t))
        self.assertEqual((code, out, called), (2, "", []))

    def test_missing_key_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "in.jsonl"
            src.write_text('{"id": "x", "text": "a"}\n', encoding="utf-8")
            cwd = os.getcwd()
            os.chdir(tmp)  # sem .env no diretório
            try:
                with mock.patch.dict(os.environ, {}, clear=True):
                    self.assertEqual(classify.main([str(src)], stdout=io.StringIO()), 2)
            finally:
                os.chdir(cwd)

    def test_invalid_numeric_arguments_rejected(self):
        for args in (["--batch-size", "0"], ["--batch-size", "x"], ["--max-retries", "-1"],
                     ["--timeout", "0"], ["--timeout", "nan"], ["--tpm-limit", "-5"],
                     ["--max-total-tokens", "0"], ["--max-completion-tokens", "-1"]):
            with self.assertRaises(SystemExit) as ctx, mock.patch("sys.stderr", io.StringIO()):
                classify.main(["in.jsonl", *args], stdout=io.StringIO())
            self.assertEqual(ctx.exception.code, 2, args)


class CliSubprocessTest(unittest.TestCase):
    """Executa `python classify.py` de verdade (sem rede: falha antes de chamar a API)."""

    def run_script(self, *args, cwd):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GROQ_")}
        return subprocess.run([sys.executable, str(ROOT / "classify.py"), *args], cwd=cwd, env=env,
                              capture_output=True, timeout=60)

    def test_missing_key_stdout_empty_error_on_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:  # sem .env no diretório
            Path(tmp, "in.jsonl").write_text('{"id": "x", "text": "Cartão"}\n', encoding="utf-8")
            proc = self.run_script("in.jsonl", cwd=tmp)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, b"")
        self.assertIn("GROQ_API_KEY", proc.stderr.decode("utf-8"))  # stderr em UTF-8

    def test_invalid_input_and_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "dup.jsonl").write_text('{"id": "a", "text": "x"}\n{"id": "a", "text": "y"}\n',
                                              encoding="utf-8")
            dup = self.run_script("dup.jsonl", cwd=tmp)
            bad_arg = self.run_script("dup.jsonl", "--batch-size", "0", cwd=tmp)
        self.assertEqual((dup.returncode, dup.stdout), (2, b""))
        self.assertIn("id duplicado", dup.stderr.decode("utf-8"))
        self.assertEqual((bad_arg.returncode, bad_arg.stdout), (2, b""))


if __name__ == "__main__":
    unittest.main()
