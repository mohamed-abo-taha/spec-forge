"""Dataclasses for code units and generated artefacts.

Each artefact has a stable ID and a reference to its parent, so the chain
spec -> story -> criterion -> test stays traceable.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any


# --------------------------------------------------------------------- code analysis
@dataclass
class CodeUnit:
    """A single unit of the analyzed codebase (function, method, class, endpoint)."""

    qualname: str
    kind: str  # "function" | "method" | "class" | "endpoint"
    file: str
    lineno: int
    signature: str = ""
    docstring: str = ""
    http: str = ""  # for endpoints, e.g. "GET /billing/invoices"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisResult:
    """The outcome of scanning a codebase."""

    root: str
    units: list[CodeUnit] = field(default_factory=list)
    file_count: int = 0

    @property
    def endpoints(self) -> list[CodeUnit]:
        return [u for u in self.units if u.kind == "endpoint"]

    @property
    def ranked_units(self) -> list[CodeUnit]:
        """Units ordered by how useful they are to reference, private helpers dropped.

        Endpoints and public functions come first; names with a leading underscore
        (framework plumbing, private helpers) are excluded unless nothing else exists.
        """
        order = {"endpoint": 0, "function": 1, "class": 2, "method": 3}
        public = [
            u for u in self.units
            if not any(part.startswith("_") for part in u.qualname.split("."))
        ]
        chosen = public or self.units
        return sorted(chosen, key=lambda u: (order.get(u.kind, 9), u.lineno))

    @property
    def symbols(self) -> set[str]:
        """Every identifier the codebase legitimately exposes (for hallucination checks)."""
        names: set[str] = set()
        for u in self.units:
            names.add(u.qualname)
            names.add(u.qualname.split(".")[-1])
        return names

    @property
    def summary(self) -> str:
        kinds: dict[str, int] = {}
        for u in self.units:
            kinds[u.kind] = kinds.get(u.kind, 0) + 1
        parts = [f"{n} {k}{'s' if n != 1 else ''}" for k, n in sorted(kinds.items())]
        return f"{self.file_count} file(s): " + ", ".join(parts) if parts else f"{self.file_count} file(s), no units found"

    def to_dict(self) -> dict[str, Any]:
        return {
            "root": self.root,
            "file_count": self.file_count,
            "summary": self.summary,
            "units": [u.to_dict() for u in self.units],
        }


# --------------------------------------------------------------------- artefacts
@dataclass
class Specification:
    id: str
    title: str
    summary: str
    business_rules: list[str] = field(default_factory=list)
    source_refs: list[str] = field(default_factory=list)  # CodeUnit.qualname values


@dataclass
class UserStory:
    id: str
    spec_id: str
    role: str
    want: str
    benefit: str

    @property
    def text(self) -> str:
        return f"As a {self.role}, I want {self.want} so that {self.benefit}."


@dataclass
class AcceptanceCriterion:
    id: str
    story_id: str
    given: str
    when: str
    then: str

    @property
    def text(self) -> str:
        return f"Given {self.given}, when {self.when}, then {self.then}."


@dataclass
class TestScenario:
    id: str
    criterion_id: str
    title: str
    steps: list[str] = field(default_factory=list)
    expected: str = ""


@dataclass
class ValidationIssue:
    severity: str  # "high" | "medium" | "low"
    category: str  # "completeness" | "traceability" | "security" | "hallucination"
    message: str
    artefact_id: str = ""


@dataclass
class Artefacts:
    """The full generated bundle plus a record of what request/codebase produced it."""

    request: str
    specifications: list[Specification] = field(default_factory=list)
    user_stories: list[UserStory] = field(default_factory=list)
    acceptance_criteria: list[AcceptanceCriterion] = field(default_factory=list)
    test_scenarios: list[TestScenario] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "request": self.request,
            "specifications": [asdict(s) for s in self.specifications],
            "user_stories": [asdict(s) for s in self.user_stories],
            "acceptance_criteria": [asdict(c) for c in self.acceptance_criteria],
            "test_scenarios": [asdict(t) for t in self.test_scenarios],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Artefacts":
        return cls(
            request=data.get("request", ""),
            specifications=[Specification(**s) for s in data.get("specifications", [])],
            user_stories=[UserStory(**s) for s in data.get("user_stories", [])],
            acceptance_criteria=[AcceptanceCriterion(**c) for c in data.get("acceptance_criteria", [])],
            test_scenarios=[TestScenario(**t) for t in data.get("test_scenarios", [])],
        )

    def free_text(self) -> str:
        """All natural-language fields concatenated — used by validation scans."""
        chunks: list[str] = [self.request]
        for s in self.specifications:
            chunks += [s.title, s.summary, *s.business_rules]
        for u in self.user_stories:
            chunks.append(u.text)
        for c in self.acceptance_criteria:
            chunks.append(c.text)
        for t in self.test_scenarios:
            chunks += [t.title, *t.steps, t.expected]
        return "\n".join(chunks)
