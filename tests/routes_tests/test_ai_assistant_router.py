#!/usr/bin/env python3
"""
AI assistant routes (Phase 8) against the live stack.

The stack runs with the shipped config/ai.yml: AI off and no providers. These
check, over HTTP, that AI stays off for a tenant whatever the tenant sets,
that /v1/ai/ask then returns the rule-based answer and sends nothing to a
model (no audit rows), and that the settings and audit routes are tenant
scoped. (Turning AI off per tenant while the deployment has it on is
covered in tests/test_ai_api.py, with a fake provider.)
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'apps', 'api')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from base_test import BaseTestSuite  # noqa: E402


class AIAssistantRouterTestSuite(BaseTestSuite):
    def __init__(self):
        super().__init__("AIAssistantRouter")

    def _tenant(self, tenant_id=None):
        return {"X-Customer-ID": tenant_id or self.test_tenant_id}

    async def test_ai_is_off_by_default(self):
        r = await self.make_authenticated_request("GET", "/v1/ai/status", headers=self._tenant())
        body = r.json() if r.status_code == 200 else {}
        ok = (r.status_code == 200 and body.get("active") is False and body.get("global_enabled") is False
              and body.get("reason_code") == "global_off" and body.get("providers") == [])
        self.test_results["ai_is_off_by_default"] = "PASS" if ok else f"FAIL: {r.status_code} {r.text[:300]}"

    async def test_ask_falls_back_to_rule_based_and_sends_nothing(self):
        r = await self.make_authenticated_request("POST", "/v1/ai/ask", headers=self._tenant(),
                                                  json={"question": "how many errors in the last hour?"})
        body = r.json() if r.status_code == 200 else {}
        audit = await self.make_authenticated_request("GET", "/v1/ai/audit", headers=self._tenant())
        entries = audit.json().get("entries") if audit.status_code == 200 else None
        ok = (r.status_code == 200 and body.get("mode") == "rule_based" and body.get("reason_code") == "global_off"
              and body.get("provider") is None and isinstance(body.get("text"), str) and entries == [])
        self.test_results["ask_falls_back_to_rule_based_and_sends_nothing"] = (
            "PASS" if ok else f"FAIL: ask {r.status_code} {r.text[:200]} audit {audit.status_code} {entries}")

    async def test_a_tenant_cannot_switch_ai_on_when_the_deployment_has_it_off(self):
        r = await self.make_authenticated_request("PUT", "/v1/ai/settings", headers=self._tenant(),
                                                  json={"enabled": True, "provider": "claude"})
        off = await self.make_authenticated_request("PUT", "/v1/ai/settings", headers=self._tenant(),
                                                    json={"enabled": False, "redact_fields": ["attrs.email"]})
        status = await self.make_authenticated_request("GET", "/v1/ai/status", headers=self._tenant())
        ok = (r.status_code == 400 and "unknown provider" in r.text and off.status_code == 200
              and off.json()["settings"]["redact_fields"] == ["attrs.email"]
              and status.json().get("active") is False)
        self.test_results["a_tenant_cannot_switch_ai_on_when_the_deployment_has_it_off"] = (
            "PASS" if ok else f"FAIL: {r.status_code} {r.text[:200]} / {off.status_code} {off.text[:200]}")

    async def test_questions_are_validated(self):
        empty = await self.make_authenticated_request("POST", "/v1/ai/ask", headers=self._tenant(),
                                                      json={"question": ""})
        long = await self.make_authenticated_request("POST", "/v1/ai/ask", headers=self._tenant(),
                                                     json={"question": "x" * 5000})
        ok = empty.status_code == 422 and long.status_code == 422
        self.test_results["questions_are_validated"] = (
            "PASS" if ok else f"FAIL: {empty.status_code} / {long.status_code}")

    async def test_other_tenants_ai_routes_are_refused(self):
        other = "00000000-0000-4000-8000-000000000001"
        codes = []
        for method, path in (("GET", "/v1/ai/status"), ("GET", "/v1/ai/audit"), ("GET", "/v1/ai/settings"),
                             ("POST", "/v1/ai/ask")):
            kwargs = {"json": {"question": "q"}} if method == "POST" else {}
            r = await self.make_authenticated_request(method, path, headers=self._tenant(other), **kwargs)
            codes.append(r.status_code)
        ok = all(code == 403 for code in codes)
        self.test_results["other_tenants_ai_routes_are_refused"] = "PASS" if ok else f"FAIL: {codes}"

    async def run_all_tests(self):
        print(f"\n🚀 Starting AI Assistant Router Test Suite (Test ID: {self.test_id})")
        try:
            await self.create_test_user_and_tenant(['tenant_admin'])
            await self.setup_auth()
            # /v1/ai/ask needs the plan feature ai_assistant.query, as /v1/ai/query does
            from dao.subscription_dao import SubscriptionDAO

            await SubscriptionDAO().create_subscription({
                "tenant_id": self.test_tenant_id, "subscribed_features": ["ai_assistant.*"],
                "subscription_tier": "enterprise", "billing_cycle": "monthly"})
        except Exception as e:
            print(f"❌ Failed to set up the test environment: {e}")
            return
        for method in (self.test_ai_is_off_by_default,
                       self.test_ask_falls_back_to_rule_based_and_sends_nothing,
                       self.test_a_tenant_cannot_switch_ai_on_when_the_deployment_has_it_off,
                       self.test_questions_are_validated,
                       self.test_other_tenants_ai_routes_are_refused):
            try:
                await method()
            except Exception as e:
                self.test_results[method.__name__[5:]] = f"ERROR: {e}"
        await self.cleanup_test_data()
        self.print_test_summary()


if __name__ == "__main__":
    asyncio.run(AIAssistantRouterTestSuite().run_all_tests())
