import os
import unittest

from specforge.analyze import analyze_path

SAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples", "sample_app")


class TestAnalyze(unittest.TestCase):
    def setUp(self):
        self.result = analyze_path(SAMPLE)

    def test_finds_units(self):
        names = {u.qualname for u in self.result.units}
        self.assertIn("calculate_charges", names)
        self.assertIn("apply_discount", names)

    def test_detects_class_and_methods(self):
        names = {u.qualname for u in self.result.units}
        self.assertIn("InvoiceRepository", names)
        self.assertIn("InvoiceRepository.get_invoice", names)

    def test_detects_endpoints_with_http(self):
        endpoints = self.result.endpoints
        self.assertTrue(endpoints, "expected at least one endpoint")
        https = {u.http for u in endpoints}
        self.assertIn("GET /billing/invoices/<invoice_id>", https)
        self.assertIn("POST /billing/invoices", https)

    def test_symbols_include_short_names(self):
        self.assertIn("calculate_charges", self.result.symbols)

    def test_file_count(self):
        self.assertEqual(self.result.file_count, 1)


if __name__ == "__main__":
    unittest.main()
