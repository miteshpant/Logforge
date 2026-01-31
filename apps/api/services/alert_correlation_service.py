"""
Alert Correlation Service - Smart Alert Correlation & Noise Reduction
Provides AI-driven alert grouping, fatigue scoring, dependency correlation,
duplicate detection, and trend analysis using real ClickHouse data.
"""

import structlog
import json
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

from database_layer import DatabaseLayer
from constants.database_constants import (
    ALERT_INSTANCES_TABLE,
    ALERT_RULES_TABLE,
    LOGS_NORMALIZED_TABLE,
)

logger = structlog.get_logger(__name__)

# Time range parsing map
TIME_RANGE_MAP = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
    "3d": timedelta(days=3),
    "7d": timedelta(days=7),
    "14d": timedelta(days=14),
    "30d": timedelta(days=30),
}


def _parse_time_range(time_range: str) -> timedelta:
    """Convert a time range string like '24h' or '7d' into a timedelta."""
    delta = TIME_RANGE_MAP.get(time_range)
    if delta is None:
        logger.warning(
            "Unrecognised time_range, falling back to 24h",
            time_range=time_range,
        )
        delta = timedelta(hours=24)
    return delta


class AlertCorrelationService:
    """Business logic for smart alert correlation and noise reduction."""

    def __init__(self):
        self.db = DatabaseLayer(
            "AlertCorrelationService", "alert-correlation-service-key"
        )

    # ------------------------------------------------------------------
    # 1. Correlated Alert Groups
    # ------------------------------------------------------------------

    async def get_correlated_alert_groups(
        self,
        customer_id: str,
        time_range: str = "24h",
        min_group_size: int = 2,
    ) -> Dict[str, Any]:
        """
        Query actual alert instances and group them by temporal proximity
        (fired within 5 minutes of each other) and shared rule / severity.

        For every group the method identifies the root alert (earliest),
        computes a correlation score, collects common services, and
        suggests a probable root cause.

        Args:
            customer_id: Tenant identifier for data isolation.
            time_range: Lookback window (e.g. '24h', '7d').
            min_group_size: Minimum alerts to form a group.

        Returns:
            Dict with ``groups``, ``total_alerts_analysed``, and
            ``total_groups`` keys.
        """
        try:
            delta = _parse_time_range(time_range)
            start_time = datetime.now(timezone.utc) - delta

            # Fetch alert instances joined with their rule metadata
            query = f"""
                SELECT
                    ai.id            AS alert_id,
                    ai.rule_id       AS rule_id,
                    ar.name          AS rule_name,
                    ar.severity      AS severity,
                    ar.rule_type     AS rule_type,
                    ai.status        AS status,
                    ai.triggered_at  AS triggered_at,
                    ai.trigger_data  AS trigger_data
                FROM {ALERT_INSTANCES_TABLE} ai
                LEFT JOIN {ALERT_RULES_TABLE} ar ON ai.rule_id = ar.id
                WHERE ai.customer_id = %(customer_id)s
                  AND ai.triggered_at >= %(start_time)s
                ORDER BY ai.triggered_at ASC
            """
            params = {"customer_id": customer_id, "start_time": start_time}

            alerts = await self.db.fetch_all(query, params)

            if not alerts:
                return {
                    "groups": [],
                    "total_alerts_analysed": 0,
                    "total_groups": 0,
                    "time_range": time_range,
                }

            # ---- Temporal + rule/severity grouping ----
            # Walk through alerts sorted by triggered_at and bucket those
            # that fire within a 5-minute window of each other AND share
            # either the same rule_name or severity.
            groups: List[List[Dict[str, Any]]] = []
            current_group: List[Dict[str, Any]] = [alerts[0]]

            for alert in alerts[1:]:
                prev = current_group[-1]
                prev_ts = prev["triggered_at"]
                curr_ts = alert["triggered_at"]

                # Compute seconds between consecutive alerts
                if isinstance(prev_ts, str):
                    prev_ts = datetime.fromisoformat(prev_ts)
                if isinstance(curr_ts, str):
                    curr_ts = datetime.fromisoformat(curr_ts)

                gap_seconds = abs((curr_ts - prev_ts).total_seconds())

                same_rule = alert.get("rule_name") == prev.get("rule_name")
                same_severity = alert.get("severity") == prev.get("severity")

                if gap_seconds <= 300 and (same_rule or same_severity):
                    current_group.append(alert)
                else:
                    groups.append(current_group)
                    current_group = [alert]

            groups.append(current_group)

            # ---- Build response objects for qualifying groups ----
            result_groups: List[Dict[str, Any]] = []
            for group in groups:
                if len(group) < min_group_size:
                    continue

                root_alert = group[0]
                severities = {a.get("severity", "medium") for a in group}
                rule_names = {a.get("rule_name", "unknown") for a in group}

                # Extract services from trigger_data where available
                services: set = set()
                for a in group:
                    td = a.get("trigger_data", "{}")
                    if isinstance(td, str):
                        try:
                            td = json.loads(td)
                        except (json.JSONDecodeError, TypeError):
                            td = {}
                    details = td.get("details", {}) if isinstance(td, dict) else {}
                    svc = details.get("service") or td.get("service")
                    if svc:
                        services.add(svc)

                # Correlation score: 0-100
                score = self._compute_correlation_score(group)

                # Deterministic group id
                ids_concat = "|".join(a["alert_id"] for a in group)
                group_id = hashlib.sha256(ids_concat.encode()).hexdigest()[:16]

                suggested_cause = self._suggest_root_cause(
                    root_alert, rule_names, severities, services
                )

                result_groups.append(
                    {
                        "group_id": group_id,
                        "root_alert": {
                            "alert_id": root_alert["alert_id"],
                            "rule_name": root_alert.get("rule_name", "unknown"),
                            "severity": root_alert.get("severity", "medium"),
                            "triggered_at": (
                                root_alert["triggered_at"].isoformat()
                                if isinstance(root_alert["triggered_at"], datetime)
                                else str(root_alert["triggered_at"])
                            ),
                        },
                        "member_alerts": [
                            {
                                "alert_id": a["alert_id"],
                                "rule_name": a.get("rule_name", "unknown"),
                                "severity": a.get("severity", "medium"),
                                "status": a.get("status", "triggered"),
                                "triggered_at": (
                                    a["triggered_at"].isoformat()
                                    if isinstance(a["triggered_at"], datetime)
                                    else str(a["triggered_at"])
                                ),
                            }
                            for a in group
                        ],
                        "group_size": len(group),
                        "correlation_score": score,
                        "common_severities": sorted(severities),
                        "common_rules": sorted(rule_names),
                        "common_services": sorted(services),
                        "suggested_root_cause": suggested_cause,
                    }
                )

            # Sort groups by score descending
            result_groups.sort(key=lambda g: g["correlation_score"], reverse=True)

            return {
                "groups": result_groups,
                "total_alerts_analysed": len(alerts),
                "total_groups": len(result_groups),
                "time_range": time_range,
            }

        except Exception as e:
            logger.error(
                "Failed to compute correlated alert groups",
                error=str(e),
                customer_id=customer_id,
            )
            raise

    # ------------------------------------------------------------------
    # 2. Alert Fatigue Score
    # ------------------------------------------------------------------

    async def calculate_fatigue_score(
        self, customer_id: str
    ) -> Dict[str, Any]:
        """
        Analyse real alert volumes over the past 24 h, 7 d, and 30 d to
        produce a fatigue score (0-100, higher = worse).

        Factors considered:
        - alerts per hour (24 h window)
        - duplicate rate (same rule_name repeating)
        - acknowledgment rate
        - average resolution time

        Args:
            customer_id: Tenant identifier.

        Returns:
            Dict with ``fatigue_score``, ``contributing_factors``, and
            ``recommendations``.
        """
        try:
            now = datetime.now(timezone.utc)
            t_24h = now - timedelta(hours=24)
            t_7d = now - timedelta(days=7)
            t_30d = now - timedelta(days=30)

            # 1. Alert volume across three windows
            volume_query = f"""
                SELECT
                    countIf(triggered_at >= %(t_24h)s) AS cnt_24h,
                    countIf(triggered_at >= %(t_7d)s)  AS cnt_7d,
                    countIf(triggered_at >= %(t_30d)s) AS cnt_30d
                FROM {ALERT_INSTANCES_TABLE}
                WHERE customer_id = %(customer_id)s
                  AND triggered_at >= %(t_30d)s
            """

            # 2. Duplicate rate: how many alerts share the same rule_id
            #    within 30 minutes of another instance of the same rule
            duplicate_query = f"""
                SELECT
                    COUNT(*) AS total_alerts,
                    COUNT(*) - COUNT(DISTINCT rule_id) AS potential_duplicates
                FROM {ALERT_INSTANCES_TABLE}
                WHERE customer_id = %(customer_id)s
                  AND triggered_at >= %(t_24h)s
            """

            # 3. Acknowledgment rate over 7 d
            ack_query = f"""
                SELECT
                    COUNT(*)                                          AS total,
                    countIf(status = 'acknowledged' OR status = 'resolved') AS handled
                FROM {ALERT_INSTANCES_TABLE}
                WHERE customer_id = %(customer_id)s
                  AND triggered_at >= %(t_7d)s
            """

            # 4. Average resolution time (seconds) for resolved alerts in 30 d
            resolution_query = f"""
                SELECT
                    avg(
                        dateDiff('second', triggered_at, resolved_at)
                    ) AS avg_resolution_seconds,
                    count() AS resolved_count
                FROM {ALERT_INSTANCES_TABLE}
                WHERE customer_id = %(customer_id)s
                  AND status = 'resolved'
                  AND resolved_at IS NOT NULL
                  AND triggered_at >= %(t_30d)s
            """

            params = {
                "customer_id": customer_id,
                "t_24h": t_24h,
                "t_7d": t_7d,
                "t_30d": t_30d,
            }

            volume_row = await self.db.fetch_one(volume_query, params)
            dup_row = await self.db.fetch_one(duplicate_query, params)
            ack_row = await self.db.fetch_one(ack_query, params)
            res_row = await self.db.fetch_one(resolution_query, params)

            cnt_24h = (volume_row or {}).get("cnt_24h", 0)
            cnt_7d = (volume_row or {}).get("cnt_7d", 0)
            cnt_30d = (volume_row or {}).get("cnt_30d", 0)
            alerts_per_hour = round(cnt_24h / 24.0, 2) if cnt_24h else 0.0

            total_24h = (dup_row or {}).get("total_alerts", 0)
            potential_dups = (dup_row or {}).get("potential_duplicates", 0)
            duplicate_rate = (
                round(potential_dups / total_24h * 100, 1)
                if total_24h > 0
                else 0.0
            )

            ack_total = (ack_row or {}).get("total", 0)
            ack_handled = (ack_row or {}).get("handled", 0)
            ack_rate = (
                round(ack_handled / ack_total * 100, 1)
                if ack_total > 0
                else 100.0
            )

            avg_resolution_sec = (res_row or {}).get("avg_resolution_seconds", 0) or 0
            avg_resolution_min = round(avg_resolution_sec / 60.0, 1)

            # ---- Compute composite fatigue score ----
            # Each factor contributes up to 25 points
            volume_score = min(25, alerts_per_hour * 2.5)
            dup_score = min(25, duplicate_rate * 0.5)
            ack_penalty = min(25, max(0, (100 - ack_rate) * 0.5))
            resolution_penalty = min(25, avg_resolution_min / 60.0 * 25)

            fatigue_score = round(
                volume_score + dup_score + ack_penalty + resolution_penalty
            )
            fatigue_score = max(0, min(100, fatigue_score))

            # ---- Recommendations ----
            recommendations: List[str] = []
            factors: List[Dict[str, Any]] = []

            factors.append(
                {
                    "factor": "alert_volume",
                    "alerts_per_hour": alerts_per_hour,
                    "total_24h": cnt_24h,
                    "total_7d": cnt_7d,
                    "total_30d": cnt_30d,
                    "score_contribution": round(volume_score, 1),
                }
            )
            if alerts_per_hour > 5:
                recommendations.append(
                    "Alert volume is high. Consider raising thresholds or "
                    "adding cooldown periods to noisy rules."
                )

            factors.append(
                {
                    "factor": "duplicate_rate",
                    "duplicate_rate_pct": duplicate_rate,
                    "potential_duplicates_24h": potential_dups,
                    "score_contribution": round(dup_score, 1),
                }
            )
            if duplicate_rate > 30:
                recommendations.append(
                    "High duplicate rate detected. Enable alert deduplication "
                    "or increase cooldown windows for frequently firing rules."
                )

            factors.append(
                {
                    "factor": "acknowledgment_rate",
                    "acknowledgment_rate_pct": ack_rate,
                    "total_handled_7d": ack_handled,
                    "total_alerts_7d": ack_total,
                    "score_contribution": round(ack_penalty, 1),
                }
            )
            if ack_rate < 50:
                recommendations.append(
                    "Most alerts are not being acknowledged. Review alert "
                    "relevance and assign clear ownership."
                )

            factors.append(
                {
                    "factor": "resolution_time",
                    "avg_resolution_minutes": avg_resolution_min,
                    "resolved_count_30d": (res_row or {}).get("resolved_count", 0),
                    "score_contribution": round(resolution_penalty, 1),
                }
            )
            if avg_resolution_min > 120:
                recommendations.append(
                    "Average resolution time exceeds 2 hours. Consider "
                    "runbook automation or escalation policies."
                )

            if not recommendations:
                recommendations.append(
                    "Alert fatigue levels are healthy. Keep monitoring."
                )

            return {
                "fatigue_score": fatigue_score,
                "rating": (
                    "critical" if fatigue_score >= 80
                    else "high" if fatigue_score >= 60
                    else "moderate" if fatigue_score >= 40
                    else "healthy"
                ),
                "contributing_factors": factors,
                "recommendations": recommendations,
            }

        except Exception as e:
            logger.error(
                "Failed to calculate fatigue score",
                error=str(e),
                customer_id=customer_id,
            )
            raise

    # ------------------------------------------------------------------
    # 3. Service Dependency Correlation
    # ------------------------------------------------------------------

    async def get_service_dependency_alerts(
        self, customer_id: str, time_range: str = "24h"
    ) -> Dict[str, Any]:
        """
        Group alerts by service and cross-reference with error patterns in
        ``logs_normalized_mt`` to identify services that error together,
        implying upstream/downstream relationships.

        Args:
            customer_id: Tenant identifier.
            time_range: Lookback window.

        Returns:
            Dict with ``service_groups``, ``cross_service_correlations``,
            and summary statistics.
        """
        try:
            delta = _parse_time_range(time_range)
            start_time = datetime.now(timezone.utc) - delta

            # 1. Alerts per service (extracted from trigger_data details)
            alert_svc_query = f"""
                SELECT
                    ar.name                             AS rule_name,
                    ar.severity                         AS severity,
                    ai.status                           AS status,
                    ai.triggered_at                     AS triggered_at,
                    ai.trigger_data                     AS trigger_data
                FROM {ALERT_INSTANCES_TABLE} ai
                LEFT JOIN {ALERT_RULES_TABLE} ar ON ai.rule_id = ar.id
                WHERE ai.customer_id = %(customer_id)s
                  AND ai.triggered_at >= %(start_time)s
                ORDER BY ai.triggered_at ASC
            """

            # 2. Error-level log counts per service in the same window
            log_error_query = f"""
                SELECT
                    service,
                    count()                         AS error_count,
                    min(ts)                         AS first_error,
                    max(ts)                         AS last_error
                FROM {LOGS_NORMALIZED_TABLE}
                WHERE customer_id = %(customer_id)s
                  AND ts >= %(start_time)s
                  AND level IN ('ERROR', 'error', 'FATAL', 'fatal', 'CRITICAL', 'critical')
                  AND service != ''
                GROUP BY service
                ORDER BY error_count DESC
            """

            params = {"customer_id": customer_id, "start_time": start_time}

            alert_rows = await self.db.fetch_all(alert_svc_query, params)
            log_error_rows = await self.db.fetch_all(log_error_query, params)

            # Build a map of service -> alert count from trigger_data
            service_alerts: Dict[str, List[Dict[str, Any]]] = {}
            for row in alert_rows:
                td = row.get("trigger_data", "{}")
                if isinstance(td, str):
                    try:
                        td = json.loads(td)
                    except (json.JSONDecodeError, TypeError):
                        td = {}
                details = td.get("details", {}) if isinstance(td, dict) else {}
                svc = details.get("service") or td.get("service") or "unknown"
                service_alerts.setdefault(svc, []).append(row)

            # Build a map of service -> error log count
            service_errors: Dict[str, Dict[str, Any]] = {}
            for row in log_error_rows:
                svc = row.get("service", "unknown")
                service_errors[svc] = {
                    "error_count": row.get("error_count", 0),
                    "first_error": (
                        row["first_error"].isoformat()
                        if isinstance(row.get("first_error"), datetime)
                        else str(row.get("first_error", ""))
                    ),
                    "last_error": (
                        row["last_error"].isoformat()
                        if isinstance(row.get("last_error"), datetime)
                        else str(row.get("last_error", ""))
                    ),
                }

            # Combine into service groups
            all_services = set(service_alerts.keys()) | set(service_errors.keys())
            all_services.discard("unknown")

            service_groups: List[Dict[str, Any]] = []
            for svc in sorted(all_services):
                alerts_for_svc = service_alerts.get(svc, [])
                errors_for_svc = service_errors.get(svc, {})
                service_groups.append(
                    {
                        "service": svc,
                        "alert_count": len(alerts_for_svc),
                        "error_log_count": errors_for_svc.get("error_count", 0),
                        "first_error": errors_for_svc.get("first_error"),
                        "last_error": errors_for_svc.get("last_error"),
                        "severities": sorted(
                            {a.get("severity", "medium") for a in alerts_for_svc}
                        ),
                    }
                )

            # Cross-service temporal correlations: services whose earliest
            # errors fall within 2 minutes of each other are likely related.
            correlations: List[Dict[str, Any]] = []
            svc_list = [s for s in service_groups if s.get("first_error")]
            for i, svc_a in enumerate(svc_list):
                for svc_b in svc_list[i + 1:]:
                    try:
                        ts_a = datetime.fromisoformat(svc_a["first_error"])
                        ts_b = datetime.fromisoformat(svc_b["first_error"])
                        gap = abs((ts_a - ts_b).total_seconds())
                        if gap <= 120:
                            # Determine probable direction
                            upstream = (
                                svc_a["service"]
                                if ts_a <= ts_b
                                else svc_b["service"]
                            )
                            downstream = (
                                svc_b["service"]
                                if ts_a <= ts_b
                                else svc_a["service"]
                            )
                            correlations.append(
                                {
                                    "upstream_service": upstream,
                                    "downstream_service": downstream,
                                    "time_gap_seconds": round(gap, 1),
                                    "correlation_confidence": round(
                                        max(0, 100 - gap) / 100, 2
                                    ),
                                }
                            )
                    except (ValueError, TypeError):
                        continue

            return {
                "service_groups": service_groups,
                "cross_service_correlations": correlations,
                "total_services": len(service_groups),
                "total_correlations": len(correlations),
                "time_range": time_range,
            }

        except Exception as e:
            logger.error(
                "Failed to compute service dependency alerts",
                error=str(e),
                customer_id=customer_id,
            )
            raise

    # ------------------------------------------------------------------
    # 4. Duplicate Detection
    # ------------------------------------------------------------------

    async def get_duplicate_alerts(
        self, customer_id: str, time_range: str = "24h"
    ) -> Dict[str, Any]:
        """
        Identify duplicate / near-duplicate alerts by finding instances of
        the same rule that fired within a short window (10 minutes).

        Args:
            customer_id: Tenant identifier.
            time_range: Lookback window.

        Returns:
            Dict with ``duplicate_groups``, per-group suppressible count,
            and aggregate ``noise_reduction_percent``.
        """
        try:
            delta = _parse_time_range(time_range)
            start_time = datetime.now(timezone.utc) - delta

            # Group by rule and count occurrences
            query = f"""
                SELECT
                    ai.rule_id                      AS rule_id,
                    ar.name                         AS rule_name,
                    ar.severity                     AS severity,
                    COUNT(*)                        AS total_count,
                    MIN(ai.triggered_at)            AS first_fired,
                    MAX(ai.triggered_at)            AS last_fired,
                    dateDiff(
                        'minute',
                        MIN(ai.triggered_at),
                        MAX(ai.triggered_at)
                    )                               AS span_minutes
                FROM {ALERT_INSTANCES_TABLE} ai
                LEFT JOIN {ALERT_RULES_TABLE} ar ON ai.rule_id = ar.id
                WHERE ai.customer_id = %(customer_id)s
                  AND ai.triggered_at >= %(start_time)s
                GROUP BY ai.rule_id, ar.name, ar.severity
                HAVING COUNT(*) > 1
                ORDER BY total_count DESC
            """

            params = {"customer_id": customer_id, "start_time": start_time}
            rows = await self.db.fetch_all(query, params)

            # Total alert count in the window for noise-reduction calculation
            total_query = f"""
                SELECT COUNT(*) AS total
                FROM {ALERT_INSTANCES_TABLE}
                WHERE customer_id = %(customer_id)s
                  AND triggered_at >= %(start_time)s
            """
            total_row = await self.db.fetch_one(total_query, params)
            total_alerts = (total_row or {}).get("total", 0)

            duplicate_groups: List[Dict[str, Any]] = []
            total_suppressible = 0

            for row in rows:
                count = row.get("total_count", 0)
                # All but the first instance could theoretically be suppressed
                suppressible = max(0, count - 1)
                total_suppressible += suppressible

                duplicate_groups.append(
                    {
                        "rule_id": row.get("rule_id", ""),
                        "rule_name": row.get("rule_name", "unknown"),
                        "severity": row.get("severity", "medium"),
                        "total_count": count,
                        "suppressible_count": suppressible,
                        "first_fired": (
                            row["first_fired"].isoformat()
                            if isinstance(row.get("first_fired"), datetime)
                            else str(row.get("first_fired", ""))
                        ),
                        "last_fired": (
                            row["last_fired"].isoformat()
                            if isinstance(row.get("last_fired"), datetime)
                            else str(row.get("last_fired", ""))
                        ),
                        "span_minutes": row.get("span_minutes", 0),
                    }
                )

            noise_reduction = (
                round(total_suppressible / total_alerts * 100, 1)
                if total_alerts > 0
                else 0.0
            )

            return {
                "duplicate_groups": duplicate_groups,
                "total_duplicate_groups": len(duplicate_groups),
                "total_alerts": total_alerts,
                "total_suppressible": total_suppressible,
                "noise_reduction_percent": noise_reduction,
                "time_range": time_range,
            }

        except Exception as e:
            logger.error(
                "Failed to detect duplicate alerts",
                error=str(e),
                customer_id=customer_id,
            )
            raise

    # ------------------------------------------------------------------
    # 5. Alert Trend Analysis
    # ------------------------------------------------------------------

    async def get_alert_trends(
        self,
        customer_id: str,
        time_range: str = "7d",
        granularity: str = "1h",
    ) -> Dict[str, Any]:
        """
        Compute time-series alert counts broken down by severity and status,
        and determine whether the overall volume is trending up, down, or
        stable.

        Args:
            customer_id: Tenant identifier.
            time_range: Lookback window.
            granularity: Bucket size ('1h', '6h', '1d').

        Returns:
            Dict with ``time_series``, ``trend``, and ``summary``.
        """
        try:
            delta = _parse_time_range(time_range)
            start_time = datetime.now(timezone.utc) - delta

            # Map granularity to ClickHouse toStartOf* function
            granularity_map = {
                "1h": "toStartOfHour(ai.triggered_at)",
                "6h": "toStartOfInterval(ai.triggered_at, INTERVAL 6 HOUR)",
                "1d": "toStartOfDay(ai.triggered_at)",
            }
            bucket_expr = granularity_map.get(
                granularity,
                "toStartOfHour(ai.triggered_at)",
            )

            query = f"""
                SELECT
                    {bucket_expr}                                 AS bucket,
                    ar.severity                                   AS severity,
                    ai.status                                     AS status,
                    COUNT(*)                                      AS alert_count
                FROM {ALERT_INSTANCES_TABLE} ai
                LEFT JOIN {ALERT_RULES_TABLE} ar ON ai.rule_id = ar.id
                WHERE ai.customer_id = %(customer_id)s
                  AND ai.triggered_at >= %(start_time)s
                GROUP BY bucket, ar.severity, ai.status
                ORDER BY bucket ASC
            """
            params = {"customer_id": customer_id, "start_time": start_time}
            rows = await self.db.fetch_all(query, params)

            # Pivot into a time_series list
            buckets: Dict[str, Dict[str, Any]] = {}
            for row in rows:
                ts = row.get("bucket")
                ts_str = (
                    ts.isoformat()
                    if isinstance(ts, datetime)
                    else str(ts)
                )

                if ts_str not in buckets:
                    buckets[ts_str] = {
                        "timestamp": ts_str,
                        "total": 0,
                        "by_severity": {},
                        "by_status": {},
                    }

                cnt = row.get("alert_count", 0)
                sev = row.get("severity", "medium")
                st = row.get("status", "triggered")

                buckets[ts_str]["total"] += cnt
                buckets[ts_str]["by_severity"][sev] = (
                    buckets[ts_str]["by_severity"].get(sev, 0) + cnt
                )
                buckets[ts_str]["by_status"][st] = (
                    buckets[ts_str]["by_status"].get(st, 0) + cnt
                )

            time_series = sorted(
                buckets.values(), key=lambda b: b["timestamp"]
            )

            # Trend calculation: compare first half average to second half
            totals = [b["total"] for b in time_series]
            trend = "stable"
            trend_pct = 0.0
            if len(totals) >= 2:
                mid = len(totals) // 2
                first_half_avg = sum(totals[:mid]) / max(mid, 1)
                second_half_avg = sum(totals[mid:]) / max(len(totals) - mid, 1)
                if first_half_avg > 0:
                    trend_pct = round(
                        (second_half_avg - first_half_avg)
                        / first_half_avg
                        * 100,
                        1,
                    )
                elif second_half_avg > 0:
                    trend_pct = 100.0

                if trend_pct > 15:
                    trend = "increasing"
                elif trend_pct < -15:
                    trend = "decreasing"
                else:
                    trend = "stable"

            total_alerts = sum(totals) if totals else 0
            peak_bucket = max(time_series, key=lambda b: b["total"]) if time_series else None

            return {
                "time_series": time_series,
                "trend": {
                    "direction": trend,
                    "change_percent": trend_pct,
                },
                "summary": {
                    "total_alerts": total_alerts,
                    "total_buckets": len(time_series),
                    "peak_bucket": peak_bucket["timestamp"] if peak_bucket else None,
                    "peak_count": peak_bucket["total"] if peak_bucket else 0,
                },
                "time_range": time_range,
                "granularity": granularity,
            }

        except Exception as e:
            logger.error(
                "Failed to compute alert trends",
                error=str(e),
                customer_id=customer_id,
            )
            raise

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_correlation_score(group: List[Dict[str, Any]]) -> int:
        """
        Compute a 0-100 correlation score for an alert group.

        Factors:
        - Group size (more alerts = higher correlation)
        - Rule homogeneity (same rule = stronger signal)
        - Severity homogeneity (same severity = stronger signal)
        - Temporal density (tighter clustering = stronger signal)
        """
        size = len(group)
        rule_names = {a.get("rule_name") for a in group}
        severities = {a.get("severity") for a in group}

        # Size contribution (up to 30 pts)
        size_score = min(30, size * 5)

        # Rule homogeneity (up to 30 pts)
        rule_score = 30 if len(rule_names) == 1 else max(0, 30 - len(rule_names) * 5)

        # Severity homogeneity (up to 20 pts)
        sev_score = 20 if len(severities) == 1 else max(0, 20 - len(severities) * 5)

        # Temporal density (up to 20 pts)
        timestamps = []
        for a in group:
            ts = a.get("triggered_at")
            if isinstance(ts, str):
                try:
                    ts = datetime.fromisoformat(ts)
                except ValueError:
                    continue
            if isinstance(ts, datetime):
                timestamps.append(ts)

        density_score = 0
        if len(timestamps) >= 2:
            span = (max(timestamps) - min(timestamps)).total_seconds()
            # Tighter span = higher score
            if span <= 60:
                density_score = 20
            elif span <= 180:
                density_score = 15
            elif span <= 300:
                density_score = 10
            else:
                density_score = 5

        total = size_score + rule_score + sev_score + density_score
        return max(0, min(100, total))

    @staticmethod
    def _suggest_root_cause(
        root_alert: Dict[str, Any],
        rule_names: set,
        severities: set,
        services: set,
    ) -> str:
        """Generate a human-readable root-cause suggestion."""
        parts: List[str] = []

        if len(rule_names) == 1:
            name = next(iter(rule_names))
            parts.append(
                f"Repeated firing of rule '{name}' indicates a "
                "persistent underlying condition."
            )
        else:
            parts.append(
                f"Multiple rules ({', '.join(sorted(rule_names))}) "
                "firing together suggests a systemic issue."
            )

        if "critical" in severities or "high" in severities:
            parts.append(
                "High-severity alerts are present; prioritise investigation."
            )

        if services:
            parts.append(
                f"Affected services: {', '.join(sorted(services))}."
            )

        return " ".join(parts) if parts else "Unable to determine root cause."
