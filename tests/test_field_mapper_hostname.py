"""
A host name is not a DNS query. The normalizer mapped `hostname` onto the DNS
`query` field, so every event with a host name carried query=<host> and DNS
rules on `query` could match host names.
"""

from field_mapper import FieldMapper


def test_a_hostname_is_not_a_dns_query():
    result = FieldMapper().normalize_log_entry({"msg": "user logged in", "hostname": "web-01"})
    assert result.mapped_fields.get("query") != "web-01"
    assert result.mapped_fields.get("hostname") == "web-01"


def test_a_real_dns_query_still_maps():
    result = FieldMapper().normalize_log_entry({"msg": "dns lookup", "dns_query": "evil.example"})
    assert result.mapped_fields.get("query") == "evil.example"
