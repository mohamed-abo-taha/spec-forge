"""Small billing service used as the demo codebase.

Never imported or executed — SpecForge only reads it with ast, so no web
framework is needed. The decorators just mimic a Flask/FastAPI app enough for
endpoint detection.
"""


class _Router:
    def route(self, *a, **k):
        def deco(fn):
            return fn
        return deco

    def get(self, *a, **k):
        return self.route(*a, **k)

    def post(self, *a, **k):
        return self.route(*a, **k)


app = _Router()


class InvoiceRepository:
    """Persistence for customer invoices."""

    def get_invoice(self, invoice_id: str):
        """Return a single invoice by its identifier."""

    def list_invoices(self, customer_id: str):
        """List all invoices belonging to a customer."""


def calculate_charges(usage_records, tariff):
    """Compute the billable amount for a set of usage records under a tariff."""
    return sum(r["units"] * tariff.get(r["type"], 0.0) for r in usage_records)


def apply_discount(amount, plan):
    """Apply a plan-specific discount to a gross amount."""
    return amount * (1 - plan.get("discount", 0.0))


@app.get("/billing/invoices/<invoice_id>")
def get_invoice_endpoint(invoice_id):
    """HTTP endpoint: fetch a single invoice."""


@app.post("/billing/invoices")
def create_invoice_endpoint():
    """HTTP endpoint: create a new invoice from usage records."""
