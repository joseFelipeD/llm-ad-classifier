"""Cliente falso e utilitários compartilhados pelos testes de pipeline e CLI."""
import json
import re

from classifier.client import Completion, UsageMeter
from classifier.dataset import Item


def texts_in(messages):
    return [json.loads(t) for t in re.findall(r"^\d+\. (.*)$", messages[1]["content"], re.M)]


def as_json(labels):
    return json.dumps({"labels": [{"i": i, "label": l} for i, l in enumerate(labels, 1) if l]})


class FakeClient:
    """`respond(texts, call_number)` devolve conteúdo (str) ou lança ApiError."""

    def __init__(self, respond, meter=None):
        self.respond = respond
        self.calls = []
        self.meter = meter or UsageMeter()

    def complete(self, messages, **kw):
        texts = texts_in(messages)
        self.calls.append(texts)
        self.meter.record({"prompt_tokens": 10, "completion_tokens": 1})
        return Completion(self.respond(texts, len(self.calls)))


def items(*texts):
    return [Item(f"id{i}", t) for i, t in enumerate(texts, 1)]
