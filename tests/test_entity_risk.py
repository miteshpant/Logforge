"""
Entity risk scoring (Phase 11): severity with decay, diminishing repeats of
one rule, ATT&CK tactic progression, intel and anomalies, mapped to 0-100,
with the factors that explain it.
"""

from datetime import datetime, timedelta, timezone

from entity_risk import HALF_LIFE, attribute, decay, rank, score

NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


def alert(rule, severity, hours_ago, techniques=(), entities=None, **extra):
    return {"id": f"{rule}-{hours_ago}", "rule_id": rule, "title": rule.replace("_", " "), "severity": severity,
            "ts": (NOW - timedelta(hours=hours_ago)).isoformat(), "mitre_techniques": list(techniques),
            "entities": entities or {}, **extra}


def test_decay_halves_every_half_life():
    assert decay(NOW, NOW) == 1.0
    assert abs(decay(NOW - HALF_LIFE, NOW) - 0.5) < 1e-9


def test_one_noisy_rule_weighs_at_most_twice_its_first_alert():
    noisy = score(("ip", "scanner"), [alert("port_scan", "high", 1) for _ in range(300)], NOW)
    assert noisy.raw < 2 * 35 and noisy.factors[0].label.endswith("300 times")


def test_an_attack_chain_outranks_a_noisy_scanner():
    chain = [alert("ssh_brute_force_success", "high", 5, ["T1110"]),
             alert("new_local_admin", "critical", 4, ["T1136.001"]),
             alert("lsass_dump", "critical", 3, ["T1003.001"]),
             alert("data_exfil", "high", 1, ["T1048"])]
    victim = score(("user", "bob"), chain, NOW)
    scanner = score(("ip", "scanner"), [alert("port_scan", "high", h % 48, ["T1046"]) for h in range(300)], NOW)
    assert victim.score > scanner.score
    progression = next(f for f in victim.factors if f.kind == "progression")
    assert "from early to late stages" in progression.label and victim.tactics[0] == "credential-access"
    assert 0 <= scanner.score <= 100 and 0 <= victim.score <= 100


def test_old_alerts_count_for_little_and_the_window_bounds_them():
    old = score(("host", "a"), [alert("x", "critical", 24 * 10)], NOW)
    new = score(("host", "b"), [alert("x", "critical", 1)], NOW)
    gone = score(("host", "c"), [alert("x", "critical", 24 * 20)], NOW)
    assert old.raw < new.raw / 5 and gone.raw == 0 and gone.alerts == 0


def test_intel_and_anomalies_add_with_their_explanation():
    risk = score(("ip", "1.2.3.4"), [], NOW, intel=[{"confidence": 90, "source": "abuse-feed", "ts": NOW.isoformat()}],
                 anomalies=[{"label": "login at an unusual hour", "severity": "medium", "ts": NOW.isoformat()}])
    assert round(risk.raw, 1) == 37.0 and {f.kind for f in risk.factors} == {"intel", "anomaly"}
    public = risk.to_public()
    assert public["factors"][0]["kind"] == "intel" and public["factors"][0]["points"] == 27.0


def test_alerts_are_attributed_to_every_entity_they_name_and_ranked():
    alerts = [alert("ssh_brute_force_success", "high", 2, ["T1110"],
                    entities={"src_ip": ["45.1.2.3"], "user": ["root"], "hostname": ["bastion-01"]},
                    threat={"max_confidence": 80, "sources": ["abuse-feed"]}),
              alert("sudo_root", "medium", 30, entities={"user": ["deploy"]})]
    by = attribute(alerts)
    assert set(by) == {("ip", "45.1.2.3"), ("user", "root"), ("host", "bastion-01"), ("user", "deploy")}
    ranked = rank(alerts, NOW)
    assert ranked[0].entity_type == "ip" and ranked[0].value == "45.1.2.3"  # the intel hit puts it first
    assert ranked[-1].value == "deploy"


def test_rules_firing_across_the_tenant_count_less():
    churn = [alert("dns_rare_tld", "medium", 2, entities={"user": [f"u{i}"]}) for i in range(64)]
    target = [alert("new_local_admin", "medium", 2, entities={"user": ["bob"]})]
    ranked = {r.value: r for r in rank(churn + target, NOW, limit=100)}
    assert ranked["bob"].raw > 5 * ranked["u1"].raw
    assert "common across the tenant (x0.14)" in ranked["u1"].factors[0].label


def test_linked_entities_share_their_groups_progression():
    linked = {"src_ip": ["45.1.2.3"], "user": ["root"], "hostname": ["web-1"]}
    alerts = [alert("ssh_brute_force_success", "high", 5, ["T1110"], entities=linked),
              alert("new_local_admin", "critical", 4, ["T1136.001"], entities={"user": ["root"], "hostname": ["web-1"]}),
              alert("lateral_rdp", "high", 3, ["T1021.001"], entities={"user": ["root"], "hostname": ["web-1"]})]
    ranked = {r.value: r for r in rank(alerts, NOW)}
    ip = ranked["45.1.2.3"]
    progression = next(f for f in ip.factors if f.kind == "progression")
    assert ip.tactics == ["credential-access", "persistence", "lateral-movement"]
    assert "with linked entities" in progression.label and "user root" in progression.label


def test_an_address_matched_by_many_alerts_is_one_intel_hit():
    hit = {"max_confidence": 90, "sources": ["abuse-feed"]}
    alerts = [alert(f"r{i}", "low", i, entities={"src_ip": ["45.1.2.3"]}, threat=hit) for i in range(10)]
    risk = next(r for r in rank(alerts, NOW) if r.value == "45.1.2.3")
    intel = [f for f in risk.factors if f.kind == "intel"]
    assert len(intel) == 1 and "on 10 alerts" in intel[0].label and intel[0].points <= 30
