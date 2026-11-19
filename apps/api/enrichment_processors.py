"""
Enrichment processors applied at ingest (Phase 3), configured by the
operator with files they download or export:

* GeoIP / ASN: DB-IP Lite CSV range files (https://db-ip.com/db/lite.php,
  CC BY 4.0): GEOIP_CITY_CSV ("ip_start,ip_end,continent,country,region,city",
  also accepts the country-only file) and GEOIP_ASN_CSV
  ("ip_start,ip_end,asn,as_org"). Lookups are a binary search over sorted
  ranges. Memory: roughly 100 bytes per range (city-lite is ~3M ranges,
  country-lite ~500k).
* Assets and users: ASSETS_CSV keyed by `host`, USERS_CSV keyed by `user`
  (header row; other columns become the stamped attributes).
* Reverse DNS: REVERSE_DNS=on, external addresses only, cached; off by
  default because a lookup can block ingest for up to its timeout.
"""

from __future__ import annotations

import bisect
import csv
import ipaddress
import os
import socket
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Tuple

import structlog

from threat_feeds import _is_internal

logger = structlog.get_logger(__name__)


class _Ranges:
    """Sorted, non-overlapping IP ranges -> data, per IP version."""

    def __init__(self):
        self._starts: Dict[int, List[int]] = {4: [], 6: []}
        self._ends: Dict[int, List[int]] = {4: [], 6: []}
        self._data: Dict[int, List[Tuple]] = {4: [], 6: []}

    def add_all(self, rows: List[Tuple[Any, Any, Tuple]]) -> None:
        parsed = []
        for start, end, data in rows:
            try:
                a, b = ipaddress.ip_address(start), ipaddress.ip_address(end)
            except ValueError:
                continue
            if a.version == b.version:
                parsed.append((a.version, int(a), int(b), data))
        parsed.sort(key=lambda r: (r[0], r[1]))
        for version, a, b, data in parsed:
            self._starts[version].append(a)
            self._ends[version].append(b)
            self._data[version].append(data)

    def __len__(self) -> int:
        return len(self._starts[4]) + len(self._starts[6])

    def find(self, address: ipaddress._BaseAddress) -> Optional[Tuple]:
        starts = self._starts[address.version]
        i = bisect.bisect_right(starts, int(address)) - 1
        if i >= 0 and int(address) <= self._ends[address.version][i]:
            return self._data[address.version][i]
        return None


def _read_rows(path: Path) -> List[List[str]]:
    with open(path, newline="", encoding="utf-8") as handle:
        return [row for row in csv.reader(handle) if row and not row[0].startswith("#")]


class GeoIP:
    def __init__(self, city: Optional[_Ranges] = None, asn: Optional[_Ranges] = None):
        self.city = city or _Ranges()
        self.asn = asn or _Ranges()

    @classmethod
    def from_files(cls, city: Optional[Path] = None, asn: Optional[Path] = None) -> "GeoIP":
        geo = cls()
        if city:
            rows = []
            for row in _read_rows(Path(city)):
                if len(row) >= 6:
                    rows.append((row[0], row[1], (row[2], row[3], row[4], row[5])))
                elif len(row) >= 3:  # country-lite: ip_start,ip_end,country
                    rows.append((row[0], row[1], ("", row[2], "", "")))
            geo.city.add_all(rows)
        if asn:
            geo.asn.add_all([(r[0], r[1], (int(r[2]) if r[2].isdigit() else r[2], r[3] if len(r) > 3 else ""))
                             for r in _read_rows(Path(asn)) if len(r) >= 3])
        return geo

    def size(self) -> Tuple[int, int]:
        return len(self.city), len(self.asn)

    def lookup(self, ip: Any) -> Optional[Dict[str, Any]]:
        try:
            address = ipaddress.ip_address(str(ip).strip())
        except ValueError:
            return None
        if _is_internal(str(address)):
            return None
        result: Dict[str, Any] = {}
        city = self.city.find(address)
        if city:
            result.update({k: v for k, v in zip(("continent", "country", "region", "city"), city) if v})
        asn = self.asn.find(address)
        if asn:
            result.update({"asn": asn[0], "as_org": asn[1]})
        return result or None


class AssetLookup:
    """Rows of a CSV keyed (case-insensitively) by one column."""

    def __init__(self, rows: Dict[str, Dict[str, str]]):
        self.rows = rows

    @classmethod
    def from_csv(cls, path: Path, key: str) -> "AssetLookup":
        rows: Dict[str, Dict[str, str]] = {}
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                value = (row.pop(key, "") or "").strip().lower()
                if value:
                    rows[value] = {k: v for k, v in row.items() if k and v not in (None, "")}
        return cls(rows)

    def lookup(self, value: Any) -> Optional[Dict[str, str]]:
        if value in (None, ""):
            return None
        return self.rows.get(str(value).strip().lower())


class ReverseDNS:
    def __init__(self, resolver: Optional[Callable[[str], Optional[str]]] = None, max_cache: int = 10_000,
                 timeout: float = 0.5):
        self.resolver = resolver or self._resolve
        self.timeout = timeout
        self.max_cache = max_cache
        self._cache: "OrderedDict[str, Optional[str]]" = OrderedDict()

    def _resolve(self, ip: str) -> Optional[str]:
        previous = socket.getdefaulttimeout()
        socket.setdefaulttimeout(self.timeout)
        try:
            return socket.gethostbyaddr(ip)[0]
        except OSError:
            return None
        finally:
            socket.setdefaulttimeout(previous)

    def lookup(self, ip: Any) -> Optional[str]:
        text = str(ip).strip()
        try:
            if _is_internal(text):
                return None
        except ValueError:
            return None
        if text in self._cache:
            self._cache.move_to_end(text)
            return self._cache[text]
        name = self.resolver(text)
        self._cache[text] = name
        if len(self._cache) > self.max_cache:
            self._cache.popitem(last=False)
        return name


@dataclass
class Enrichers:
    geo: Optional[GeoIP] = None
    assets: Optional[AssetLookup] = None
    users: Optional[AssetLookup] = None
    rdns: Optional[ReverseDNS] = None

    def __bool__(self) -> bool:
        return any((self.geo, self.assets, self.users, self.rdns))

    @classmethod
    def from_env(cls, env: Mapping[str, str] = os.environ) -> "Enrichers":
        enrichers = cls()
        try:
            if env.get("GEOIP_CITY_CSV") or env.get("GEOIP_ASN_CSV"):
                enrichers.geo = GeoIP.from_files(city=env.get("GEOIP_CITY_CSV") or None,
                                                 asn=env.get("GEOIP_ASN_CSV") or None)
                logger.info("GeoIP loaded", ranges=enrichers.geo.size())
            if env.get("ASSETS_CSV"):
                enrichers.assets = AssetLookup.from_csv(Path(env["ASSETS_CSV"]), key="host")
            if env.get("USERS_CSV"):
                enrichers.users = AssetLookup.from_csv(Path(env["USERS_CSV"]), key="user")
            if env.get("REVERSE_DNS", "off").lower() in ("on", "true", "1"):
                enrichers.rdns = ReverseDNS()
        except (OSError, ValueError) as e:
            logger.error(f"Enrichment files could not be loaded: {e}")
        return enrichers


_enrichers: Optional[Enrichers] = None


def get_enrichers() -> Enrichers:
    global _enrichers
    if _enrichers is None:
        _enrichers = Enrichers.from_env()
    return _enrichers
