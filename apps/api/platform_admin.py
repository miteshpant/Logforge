"""
Platform admin views: the feature matrix of the subscription tiers and bills
as PDF documents. Tier bundles are defined in code
(services/subscription_service.py) and the catalogue of features in
routers/subscription_api.py, so the matrix is read-only.
"""

from __future__ import annotations

import calendar
import json
from datetime import datetime, timezone
from typing import Any, Dict, List


def feature_matrix(bundles: Dict[str, List[str]], catalogue: Dict[str, List[str]], has_access) -> Dict[str, Any]:
    """{tiers, categories: [{name, features: [{name, tiers: {tier: bool}}]}]}, wildcards resolved."""
    tiers = list(bundles)
    categories = []
    for name, features in catalogue.items():
        categories.append({"name": name, "features": [
            {"name": f, "tiers": {t: bool(has_access(bundles[t], f)) for t in tiers}} for f in features]})
    return {"tiers": tiers, "bundles": bundles, "categories": categories}


def _amount(value: Any, currency: str) -> str:
    return f"{float(value or 0):,.2f} {currency}"


def bill_report(bill: Dict[str, Any], tenant_name: str) -> Dict[str, Any]:
    """A bill in the report shape reports.to_pdf renders."""
    year, month = (int(p) for p in str(bill["billing_period"]).split("-"))
    last = calendar.monthrange(year, month)[1]
    currency = bill.get("currency") or "USD"
    usage = bill.get("usage_breakdown") or []
    if isinstance(usage, str):
        usage = json.loads(usage or "[]")
    generated = bill.get("generated_at")
    generated = generated.isoformat() if hasattr(generated, "isoformat") else str(generated or "")
    return {
        "title": f"Invoice {bill['id'][:8]}", "tenant": tenant_name or bill["tenant_id"],
        "period": {"start": f"{year}-{month:02d}-01", "end": f"{year}-{month:02d}-{last}", "days": last},
        "generated_at": generated or datetime.now(timezone.utc).isoformat(),
        "sections": [
            {"title": "Summary", "kind": "kv", "rows": [
                ["Bill", bill["id"]], ["Tenant", bill["tenant_id"]], ["Plan", bill.get("subscription_tier", "")],
                ["Status", bill.get("status", "")], ["Due", str(bill.get("due_date") or "")[:10]],
            ]},
            {"title": "Charges", "kind": "kv", "rows": [
                ["Base fee", _amount(bill.get("base_fee"), currency)],
                ["Usage", _amount(bill.get("usage_charges"), currency)],
                ["Subtotal", _amount(bill.get("subtotal"), currency)],
                ["Discounts", _amount(-(float(bill.get("tier_discount") or 0) + float(bill.get("promo_discount") or 0)),
                                      currency)],
                ["Total", _amount(bill.get("total_amount"), currency)],
            ]},
            {"title": "Usage", "kind": "table", "columns": ["Item", "Quantity", "Unit price", "Amount"],
             "rows": [[u.get("feature") or u.get("name") or u.get("description", ""), u.get("quantity", ""),
                       u.get("unit_price", u.get("rate", "")), _amount(u.get("amount", u.get("cost", 0)), currency)]
                      for u in usage if isinstance(u, dict)]},
        ],
    }
