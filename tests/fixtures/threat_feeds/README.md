Feed payload samples for the parser tests (tests/test_threat_feeds.py).

* `feodo_ipblocklist.json` / `.txt`: captured from feodotracker.abuse.ch on
  2026-11-18 (trimmed); abuse.ch data is free to use (see its terms).
* The others are hand-written in each provider's documented response format
  (URLhaus and ThreatFox APIs, which need an abuse.ch Auth-Key; AlienVault
  OTX pulses; MISP attribute search; STIX 2.1 bundle; CSV), using
  documentation addresses (RFC 5737 / 3849) and example domains.
