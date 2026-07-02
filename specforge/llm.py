"""LLM backends.

MockLLM is deterministic and offline (tests/CI). OllamaLLM talks to a local
Ollama server over urllib, no SDK. To add a provider, subclass LLMClient and
implement the four methods — everything else is backend-independent.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any

from .models import AnalysisResult


class LLMClient:
    """Interface every backend implements."""

    name = "base"

    def spec(self, request: str, analysis: AnalysisResult) -> dict[str, Any]:
        raise NotImplementedError

    def stories(self, spec_title: str, business_rules: list[str]) -> list[dict[str, str]]:
        raise NotImplementedError

    def criteria(self, story_text: str) -> list[dict[str, str]]:
        raise NotImplementedError

    def tests(self, criterion_text: str) -> list[dict[str, Any]]:
        raise NotImplementedError


# --------------------------------------------------------------------- mock backend
class MockLLM(LLMClient):
    """Deterministic backend. Output reflects the inputs so demos look real, and
    it never reaches the network — ideal for tests, CI, and reproducible examples."""

    name = "mock"

    def spec(self, request: str, analysis: AnalysisResult) -> dict[str, Any]:
        top = analysis.ranked_units[:3]
        rules = [
            f"The system must preserve the observable behaviour of `{u.qualname}` ({u.kind})."
            for u in top
        ]
        if analysis.endpoints:
            rules.append(
                "All API endpoints must enforce authentication, authorization, and input "
                "validation before processing a request."
            )
        rules.append(
            "Every change must be delivered as a thin, independently testable slice with "
            "traceability back to this specification."
        )
        clean = request.strip().rstrip(".")
        return {
            "title": f"Specification: {clean}",
            "summary": (
                f"This specification captures the intent \"{clean}\" against the analyzed "
                f"codebase ({analysis.summary})."
            ),
            "business_rules": rules,
        }

    def stories(self, spec_title: str, business_rules: list[str]) -> list[dict[str, str]]:
        return [
            {
                "role": "platform engineer",
                "want": "the existing business logic captured as a reviewable specification",
                "benefit": "I can extend the system without regressing current behaviour",
            },
            {
                "role": "product owner",
                "want": "each requirement broken into acceptance criteria and tests",
                "benefit": "delivery stays traceable from intent to implementation",
            },
        ]

    def criteria(self, story_text: str) -> list[dict[str, str]]:
        return [
            {
                "given": "a documented specification and the current codebase",
                "when": "the described capability is implemented as a thin slice",
                "then": "all existing tests pass and new behaviour is covered by tests",
            },
            {
                "given": "an API request that fails validation",
                "when": "the endpoint processes it",
                "then": "the request is rejected with a clear error and no side effects",
            },
        ]

    def tests(self, criterion_text: str) -> list[dict[str, Any]]:
        return [
            {
                "title": "Happy-path behaviour is preserved",
                "steps": [
                    "Arrange the system in a known-good state",
                    "Exercise the capability described by the criterion",
                    "Assert the observable outcome matches the specification",
                ],
                "expected": "The outcome matches the specification and no regression is introduced.",
            }
        ]


# --------------------------------------------------------------------- ollama backend
_SYSTEM = (
    "You are an AI-SDLC assistant. Return ONLY valid JSON, no prose, no markdown fences. "
    "Be precise and grounded in the provided code context; never invent symbols."
)


def _extract_json(text: str) -> Any:
    """Best-effort JSON extraction from a model response."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # grab the first {...} or [...] block
        for opener, closer in (("[", "]"), ("{", "}")):
            i, j = text.find(opener), text.rfind(closer)
            if 0 <= i < j:
                try:
                    return json.loads(text[i : j + 1])
                except json.JSONDecodeError:
                    pass
    raise ValueError("model did not return parseable JSON")


class OllamaLLM(LLMClient):
    """Talk to a local Ollama server. No third-party package required."""

    name = "ollama"

    def __init__(self, model: str = "llama3.2:3b", host: str = "http://127.0.0.1:11434", timeout: int = 120):
        self.model = model
        self.host = host.rstrip("/")
        self.timeout = timeout

    def _generate(self, prompt: str) -> str:
        payload = json.dumps(
            {"model": self.model, "prompt": prompt, "system": _SYSTEM, "stream": False}
        ).encode("utf-8")
        req = urllib.request.Request(
            f"{self.host}/api/generate", data=payload, headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            return body.get("response", "")
        except (urllib.error.URLError, TimeoutError) as exc:  # pragma: no cover - network
            raise RuntimeError(
                f"Could not reach Ollama at {self.host}. Is it running? ({exc})"
            ) from exc

    def _json(self, prompt: str, fallback: Any) -> Any:
        try:
            return _extract_json(self._generate(prompt))
        except (ValueError, RuntimeError):
            return fallback

    def spec(self, request: str, analysis: AnalysisResult) -> dict[str, Any]:
        units = "\n".join(
            f"- {u.qualname} [{u.kind}] {u.http}".rstrip() for u in analysis.units[:40]
        )
        prompt = (
            f"REQUEST: {request}\n\nCODE UNITS:\n{units}\n\n"
            "Produce a specification as JSON with keys: title (string), summary (string), "
            "business_rules (array of strings). Ground every rule in the code units above."
        )
        fallback = MockLLM().spec(request, analysis)
        data = self._json(prompt, fallback)
        return data if isinstance(data, dict) else fallback

    def stories(self, spec_title: str, business_rules: list[str]) -> list[dict[str, str]]:
        prompt = (
            f"SPEC: {spec_title}\nRULES:\n" + "\n".join(f"- {r}" for r in business_rules) + "\n\n"
            "Return a JSON array of user stories, each with keys role, want, benefit."
        )
        data = self._json(prompt, MockLLM().stories(spec_title, business_rules))
        return data if isinstance(data, list) else MockLLM().stories(spec_title, business_rules)

    def criteria(self, story_text: str) -> list[dict[str, str]]:
        prompt = (
            f"USER STORY: {story_text}\n\n"
            "Return a JSON array of acceptance criteria, each with keys given, when, then."
        )
        data = self._json(prompt, MockLLM().criteria(story_text))
        return data if isinstance(data, list) else MockLLM().criteria(story_text)

    def tests(self, criterion_text: str) -> list[dict[str, Any]]:
        prompt = (
            f"ACCEPTANCE CRITERION: {criterion_text}\n\n"
            "Return a JSON array of test scenarios, each with keys title, steps (array), expected."
        )
        data = self._json(prompt, MockLLM().tests(criterion_text))
        return data if isinstance(data, list) else MockLLM().tests(criterion_text)


def get_llm(name: str = "mock", model: str | None = None) -> LLMClient:
    name = (name or "mock").lower()
    if name == "mock":
        return MockLLM()
    if name == "ollama":
        return OllamaLLM(model=model or "llama3.2:3b")
    raise ValueError(f"unknown LLM backend: {name!r} (choose 'mock' or 'ollama')")
