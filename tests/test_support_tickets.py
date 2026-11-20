"""Support tickets: tenant members ask, platform admins answer."""

from datetime import datetime, timedelta, timezone

import pytest

import support_tickets as st

T0 = datetime(2026, 11, 20, 12, tzinfo=timezone.utc)


def test_a_ticket_opens_with_the_first_message():
    t = st.open_ticket("acme", "  Ingest is slow ", "Batches take 5 s since Monday.", "high", "dana@acme.example", "u1", T0)
    assert (t.subject, t.status, t.priority) == ("Ingest is slow", "open", "high")
    assert t.messages == [{"author": "dana@acme.example", "from": "customer",
                           "text": "Batches take 5 s since Monday.", "at": T0.isoformat()}]


@pytest.mark.parametrize("subject,text,priority", [("hi", "x", "normal"), ("Valid subject", "  ", "normal"),
                                                   ("Valid subject", "x", "critical"), ("x" * 201, "x", "low")])
def test_invalid_tickets_are_refused(subject, text, priority):
    with pytest.raises(st.TicketError):
        st.open_ticket("acme", subject, text, priority, "a", "u", T0)


def test_replies_move_the_status():
    t = st.open_ticket("acme", "Question", "How do I rotate keys?", "normal", "dana", "u1", T0)
    t = st.reply(t, "Settings, API keys, Rotate.", "admin@example.com", True, T0 + timedelta(minutes=5))
    assert t.status == "answered" and t.messages[-1]["from"] == "support"
    t = st.reply(t, "Thanks, and for SCIM tokens?", "dana", False, T0 + timedelta(minutes=9))
    assert t.status == "open" and len(t.messages) == 3 and t.updated_at == T0 + timedelta(minutes=9)
    t = st.update(t, status="closed")
    with pytest.raises(st.TicketError, match="closed"):
        st.reply(t, "one more thing", "dana", False)
    assert st.reply(t, "Reopening to add a note.", "admin", True).status == "answered"
    with pytest.raises(st.TicketError):
        st.update(t, status="lost")
