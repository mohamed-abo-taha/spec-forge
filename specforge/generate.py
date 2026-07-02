"""Build the artefact tree from an analysis + a request.

The LLM only writes prose. IDs, parent links and source refs are assembled
here in code, so traceability doesn't depend on which model was used.
"""
from __future__ import annotations

from .llm import LLMClient, MockLLM
from .models import (
    AcceptanceCriterion,
    AnalysisResult,
    Artefacts,
    Specification,
    TestScenario,
    UserStory,
)


def generate_artefacts(
    analysis: AnalysisResult,
    request: str,
    llm: LLMClient | None = None,
    max_stories: int = 3,
    max_criteria: int = 3,
) -> Artefacts:
    llm = llm or MockLLM()
    artefacts = Artefacts(request=request)

    # ---- specification (source_refs chosen deterministically from real code) ----
    spec_data = llm.spec(request, analysis)
    source_refs = [u.qualname for u in analysis.ranked_units[:5]]
    spec = Specification(
        id="SPEC-001",
        title=str(spec_data.get("title", f"Specification: {request}")),
        summary=str(spec_data.get("summary", "")),
        business_rules=[str(r) for r in spec_data.get("business_rules", [])],
        source_refs=source_refs,
    )
    artefacts.specifications.append(spec)

    # ---- user stories ----
    story_defs = llm.stories(spec.title, spec.business_rules)[:max_stories]
    us_n = ac_n = ts_n = 0
    for sd in story_defs:
        us_n += 1
        story = UserStory(
            id=f"US-{us_n:03d}",
            spec_id=spec.id,
            role=str(sd.get("role", "user")),
            want=str(sd.get("want", "the capability")),
            benefit=str(sd.get("benefit", "value is delivered")),
        )
        artefacts.user_stories.append(story)

        # ---- acceptance criteria per story ----
        for cd in llm.criteria(story.text)[:max_criteria]:
            ac_n += 1
            criterion = AcceptanceCriterion(
                id=f"AC-{ac_n:03d}",
                story_id=story.id,
                given=str(cd.get("given", "")),
                when=str(cd.get("when", "")),
                then=str(cd.get("then", "")),
            )
            artefacts.acceptance_criteria.append(criterion)

            # ---- test scenarios per criterion ----
            for td in llm.tests(criterion.text):
                ts_n += 1
                artefacts.test_scenarios.append(
                    TestScenario(
                        id=f"TS-{ts_n:03d}",
                        criterion_id=criterion.id,
                        title=str(td.get("title", "Scenario")),
                        steps=[str(s) for s in td.get("steps", [])],
                        expected=str(td.get("expected", "")),
                    )
                )

    return artefacts
