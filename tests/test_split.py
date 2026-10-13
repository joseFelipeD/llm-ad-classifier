import importlib.util
import json
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class SplitTest(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("make_split", ROOT / "scripts" / "make_split.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        with open(ROOT / "data" / "train.jsonl", encoding="utf-8") as f:
            self.rows = [json.loads(l) for l in f if l.strip()]

    def test_sizes_stratified_disjoint_deterministic(self):
        parts = self.mod.stratified_split(self.rows, seed=42)
        sizes = {k: len(v) for k, v in parts.items()}
        self.assertEqual(sizes, {"holdout": 40, "dev": 160, "fewshot_k3": 24, "fewshot_k1": 8, "dev_eval": 136})
        ids = lambda name: {r["id"] for r in parts[name]}
        self.assertFalse(ids("holdout") & ids("dev"))
        self.assertEqual(ids("holdout") | ids("dev"), {r["id"] for r in self.rows})
        self.assertTrue(ids("fewshot_k1") <= ids("fewshot_k3") <= ids("dev"))
        self.assertFalse(ids("fewshot_k3") & ids("dev_eval"))
        self.assertEqual(set(Counter(r["label"] for r in parts["holdout"]).values()), {5})
        self.assertEqual(parts, self.mod.stratified_split(self.rows, seed=42))


if __name__ == "__main__":
    unittest.main()
