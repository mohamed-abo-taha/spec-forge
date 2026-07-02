import os
import unittest

from specforge.analyze import analyze_path
from specforge.generate import generate_artefacts
from specforge.llm import MockLLM
from specforge.models import (
    AcceptanceCriterion,
    Artefacts,
    Specification,
    UserStory,
)
from specforge.validate import validate

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_app")


class TestValidate(unittest.TestCase):
    def setUp(self):
        self.analysis = analyze_path(SAMPLE)

    def test_clean_artefacts_pass(self):
        artefacts = generate_artefacts(self.analysis, "Add usage-based invoicing", MockLLM())
        report = validate(artefacts, self.analysis)
        self.assertTrue(report.passed, [i.message for i in report.issues])
        self.assertGreaterEqual(report.score, 80)

    def test_detects_hallucinated_source_ref(self):
        artefacts = generate_artefacts(self.analysis, "x", MockLLM())
        artefacts.specifications[0].source_refs.append("this_function_does_not_exist")
        report = validate(artefacts, self.analysis)
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "hallucination" for i in report.issues))

    def test_detects_missing_acceptance_criteria(self):
        artefacts = Artefacts(request="x")
        artefacts.specifications.append(
            Specification(id="SPEC-001", title="t", summary="s",
                          business_rules=["must authenticate"], source_refs=[])
        )
        artefacts.user_stories.append(
            UserStory(id="US-001", spec_id="SPEC-001", role="r", want="w", benefit="b")
        )
        report = validate(artefacts, self.analysis)
        self.assertFalse(report.passed)
        self.assertTrue(any(i.category == "completeness" for i in report.issues))

    def test_detects_security_gap_when_endpoints_present(self):
        artefacts = Artefacts(request="x")
        artefacts.specifications.append(
            Specification(id="SPEC-001", title="t", summary="s",
                          business_rules=["compute totals"], source_refs=[])
        )
        artefacts.user_stories.append(UserStory(id="US-001", spec_id="SPEC-001", role="r", want="w", benefit="b"))
        artefacts.acceptance_criteria.append(
            AcceptanceCriterion(id="AC-001", story_id="US-001", given="g", when="w", then="totals are correct")
        )
        report = validate(artefacts, self.analysis)
        self.assertTrue(any(i.category == "security" for i in report.issues))

    def test_detects_broken_traceability(self):
        artefacts = Artefacts(request="x")
        artefacts.user_stories.append(UserStory(id="US-001", spec_id="SPEC-999", role="r", want="w", benefit="b"))
        report = validate(artefacts, self.analysis)
        self.assertTrue(any(i.category == "traceability" for i in report.issues))


if __name__ == "__main__":
    unittest.main()
