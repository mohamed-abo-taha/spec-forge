import os
import unittest

from specforge.analyze import analyze_path
from specforge.generate import generate_artefacts
from specforge.llm import MockLLM
from specforge.models import Artefacts

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_app")


class TestGenerate(unittest.TestCase):
    def setUp(self):
        self.analysis = analyze_path(SAMPLE)
        self.artefacts = generate_artefacts(self.analysis, "Add usage-based invoicing", MockLLM())

    def test_produces_full_chain(self):
        self.assertTrue(self.artefacts.specifications)
        self.assertTrue(self.artefacts.user_stories)
        self.assertTrue(self.artefacts.acceptance_criteria)
        self.assertTrue(self.artefacts.test_scenarios)

    def test_ids_are_unique_and_formatted(self):
        ids = [s.id for s in self.artefacts.user_stories]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(i.startswith("US-") for i in ids))

    def test_traceability_links_resolve(self):
        spec_ids = {s.id for s in self.artefacts.specifications}
        story_ids = {s.id for s in self.artefacts.user_stories}
        crit_ids = {c.id for c in self.artefacts.acceptance_criteria}
        self.assertTrue(all(u.spec_id in spec_ids for u in self.artefacts.user_stories))
        self.assertTrue(all(c.story_id in story_ids for c in self.artefacts.acceptance_criteria))
        self.assertTrue(all(t.criterion_id in crit_ids for t in self.artefacts.test_scenarios))

    def test_source_refs_are_real(self):
        symbols = self.analysis.symbols
        for spec in self.artefacts.specifications:
            for ref in spec.source_refs:
                self.assertIn(ref, symbols)

    def test_json_round_trip(self):
        data = self.artefacts.to_dict()
        restored = Artefacts.from_dict(data)
        self.assertEqual(restored.to_dict(), data)


if __name__ == "__main__":
    unittest.main()
