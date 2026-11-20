"""Platform admin: the tier feature matrix and bills as PDF."""

import platform_admin
from services.subscription_service import SubscriptionService


def test_the_matrix_resolves_wildcards():
    bundles = {"starter": ["queries.basic"], "smb": ["queries.*"], "enterprise": ["*"]}
    catalogue = {"queries": ["queries.basic", "queries.advanced"], "security": ["security.rules"]}
    has = SubscriptionService.has_feature_access.__get__(SubscriptionService.__new__(SubscriptionService))
    m = platform_admin.feature_matrix(bundles, catalogue, has)
    rows = {f["name"]: f["tiers"] for c in m["categories"] for f in c["features"]}
    assert rows["queries.basic"] == {"starter": True, "smb": True, "enterprise": True}
    assert rows["queries.advanced"] == {"starter": False, "smb": True, "enterprise": True}
    assert rows["security.rules"] == {"starter": False, "smb": False, "enterprise": True}


def test_a_bill_renders_as_a_pdf():
    import reports

    bill = {"id": "a827eb5f-75ad-49ad", "tenant_id": "t1", "billing_period": "2026-02", "subscription_tier": "enterprise",
            "base_fee": 299.0, "usage_charges": 12.5, "tier_discount": 10, "promo_discount": 0, "subtotal": 311.5,
            "total_amount": 301.5, "currency": "USD", "status": "generated", "due_date": "2026-03-20T00:00:00",
            "generated_at": "2026-03-01T00:00:00", "usage_breakdown": '[{"feature": "ingestion", "quantity": 5, "unit_price": 2.5, "amount": 12.5}]'}
    report = platform_admin.bill_report(bill, "Acme")
    assert report["period"] == {"start": "2026-02-01", "end": "2026-02-28", "days": 28}
    assert ["Total", "301.50 USD"] in report["sections"][1]["rows"]
    assert report["sections"][2]["rows"] == [["ingestion", 5, 2.5, "12.50 USD"]]
    assert reports.to_pdf(report).startswith(b"%PDF")
