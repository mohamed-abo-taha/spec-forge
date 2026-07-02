"""Deterministic validation of generated artefacts.

Checks completeness, traceability, hallucinated symbols and missing security
requirements. On purpose this is plain code, not another LLM call — the point
is an explainable gate, not a second opinion.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .models import AnalysisResult, Artefacts, ValidationIssue

_SECURITY_TERMS = re.compile(
    r"\b(auth\w*|authoriz\w*|authenticat\w*|token|credential|password|encrypt\w*|"
    r"validat\w*|permission|access control|rate.?limit|pii|gdpr)\b",
    re.IGNORECASE,
)
_BACKTICKED = re.compile(r"`([A-Za-z_][\w\.]*)`")

_WEIGHT = {"high": 25, "medium": 10, "low": 3}


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    coverage: float = 0.0  # fraction of code units referenced by a spec

    @property
    def score(self) -> int:
        penalty = sum(_WEIGHT.get(i.severity, 5) for i in self.issues)
        return max(0, 100 - penalty)

    @property
    def passed(self) -> bool:
        return not any(i.severity == "high" for i in self.issues)

    def counts(self) -> dict[str, int]:
        out = {"high": 0, "medium": 0, "low": 0}
        for i in self.issues:
            out[i.severity] = out.get(i.severity, 0) + 1
        return out

    def to_dict(self) -> dict:
        return {
            "score": self.score,
            "passed": self.passed,
            "coverage": round(self.coverage, 3),
            "counts": self.counts(),
            "issues": [i.__dict__ for i in self.issues],
        }


def validate(artefacts: Artefacts, analysis: AnalysisResult) -> ValidationReport:
    report = ValidationReport()
    issues = report.issues

    spec_ids = {s.id for s in artefacts.specifications}
    story_ids = {s.id for s in artefacts.user_stories}
    crit_ids = {c.id for c in artefacts.acceptance_criteria}
    symbols = analysis.symbols

    # ---- completeness: every level of the chain must be populated ----
    if not artefacts.specifications:
        issues.append(ValidationIssue("high", "completeness", "No specification was produced."))
    for spec in artefacts.specifications:
        if not any(u.spec_id == spec.id for u in artefacts.user_stories):
            issues.append(
                ValidationIssue("high", "completeness", f"Specification {spec.id} has no user stories.", spec.id)
            )
        if not spec.business_rules:
            issues.append(
                ValidationIssue("medium", "completeness", f"Specification {spec.id} lists no business rules.", spec.id)
            )
    for story in artefacts.user_stories:
        if not any(c.story_id == story.id for c in artefacts.acceptance_criteria):
            issues.append(
                ValidationIssue("high", "completeness", f"User story {story.id} has no acceptance criteria.", story.id)
            )
    for crit in artefacts.acceptance_criteria:
        if not any(t.criterion_id == crit.id for t in artefacts.test_scenarios):
            issues.append(
                ValidationIssue("medium", "completeness", f"Acceptance criterion {crit.id} has no test scenario.", crit.id)
            )

    # ---- traceability: every reference must point to something that exists ----
    for story in artefacts.user_stories:
        if story.spec_id not in spec_ids:
            issues.append(
                ValidationIssue("high", "traceability", f"User story {story.id} references unknown spec {story.spec_id}.", story.id)
            )
    for crit in artefacts.acceptance_criteria:
        if crit.story_id not in story_ids:
            issues.append(
                ValidationIssue("high", "traceability", f"Criterion {crit.id} references unknown story {crit.story_id}.", crit.id)
            )
    for test in artefacts.test_scenarios:
        if test.criterion_id not in crit_ids:
            issues.append(
                ValidationIssue("high", "traceability", f"Test {test.id} references unknown criterion {test.criterion_id}.", test.id)
            )
    for spec in artefacts.specifications:
        for ref in spec.source_refs:
            if ref not in symbols:
                issues.append(
                    ValidationIssue("high", "hallucination", f"Specification {spec.id} references source `{ref}` that does not exist in the codebase.", spec.id)
                )

    # ---- hallucination: any backticked identifier must be a real symbol ----
    known_words = {"id", "api", "json", "http", "url", "given", "when", "then", "sdlc"}
    for match in _BACKTICKED.finditer(artefacts.free_text()):
        ident = match.group(1)
        base = ident.split(".")[-1]
        if ident in symbols or base in symbols:
            continue
        if base.lower() in known_words or "." not in ident and base.islower() and len(base) < 4:
            continue
        if base[:1].islower() and "." not in ident and base.isalpha():
            # ordinary lower-case word in prose, not a code reference
            continue
        issues.append(
            ValidationIssue("medium", "hallucination", f"Referenced identifier `{ident}` was not found in the analyzed codebase.")
        )

    # ---- security: endpoints demand explicit security requirements ----
    if analysis.endpoints and not _SECURITY_TERMS.search(artefacts.free_text()):
        issues.append(
            ValidationIssue(
                "high",
                "security",
                f"The codebase exposes {len(analysis.endpoints)} endpoint(s) but no artefact "
                "mentions authentication, authorization, validation, or other security controls.",
            )
        )

    # ---- coverage metric ----
    referenced: set[str] = set()
    for spec in artefacts.specifications:
        referenced.update(spec.source_refs)
    total = len({u.qualname for u in analysis.units}) or 1
    report.coverage = len(referenced & {u.qualname for u in analysis.units}) / total

    return report


def report_markdown(artefacts: Artefacts, report: ValidationReport) -> str:
    lines = ["# SpecForge validation report", ""]
    status = "PASSED" if report.passed else "FAILED"
    lines += [
        f"**Status:** {status}  ",
        f"**Score:** {report.score}/100  ",
        f"**Source coverage:** {report.coverage:.0%}  ",
        f"**Issues:** {report.counts()['high']} high · {report.counts()['medium']} medium · {report.counts()['low']} low",
        "",
    ]
    if report.issues:
        lines += ["## Issues", "", "| Severity | Category | Artefact | Message |", "|---|---|---|---|"]
        for i in report.issues:
            lines.append(f"| {i.severity} | {i.category} | {i.artefact_id or '—'} | {i.message} |")
    else:
        lines.append("No issues found. Every artefact is complete, traceable, and grounded in the codebase.")
    lines += ["", "## Traceability", ""]
    for spec in artefacts.specifications:
        lines.append(f"- **{spec.id}** {spec.title}  ↳ source: {', '.join(f'`{r}`' for r in spec.source_refs) or '—'}")
        for story in [u for u in artefacts.user_stories if u.spec_id == spec.id]:
            lines.append(f"  - **{story.id}** {story.text}")
            for crit in [c for c in artefacts.acceptance_criteria if c.story_id == story.id]:
                tests = [t.id for t in artefacts.test_scenarios if t.criterion_id == crit.id]
                lines.append(f"    - **{crit.id}** {crit.text}  →  tests: {', '.join(tests) or '—'}")
    lines.append("")
    return "\n".join(lines)
