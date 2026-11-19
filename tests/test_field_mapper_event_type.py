"""
The message-pattern guess for event_type never overrides the caller's own.

Ingestion keeps caller fields in `attrs`. A log sent with
attrs.event_type="authentication" and the message "login failed" was given a
top-level event_type="login_failed" guessed from the message, which shadowed
the caller's value: the brute-force rule (event_type: authentication) then
missed the event.
"""

from field_mapper import FieldMapper


def test_guess_does_not_shadow_event_type_in_attrs():
    result = FieldMapper().normalize_log_entry(
        {"msg": "login failed", "attrs": {"event_type": "authentication", "result": "failed"}})
    assert "event_type" not in result.mapped_fields


def test_guess_still_applies_when_the_caller_sent_none():
    result = FieldMapper().normalize_log_entry({"msg": "login failed", "attrs": {}})
    assert result.mapped_fields["event_type"] == "login_failed"
