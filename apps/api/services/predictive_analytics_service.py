"""
Predictive Analytics Service - AI-Powered Forecasting and Capacity Planning

Provides production-grade predictive analytics backed by REAL ClickHouse queries:
- Trend forecasting with linear regression on historical time-series data
- Capacity planning with growth rate projection
- SLA breach prediction using per-service error rate trend analysis
- What-if scenario modeling against actual baseline metrics

All methods enforce tenant isolation via customer_id filtering.
"""

import math
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple

from database_layer import DatabaseLayer
import structlog

logger = structlog.get_logger(__name__)


class PredictiveAnalyticsService:
    """Predictive analytics engine backed by real ClickHouse data."""

    def __init__(self):
        self.db = DatabaseLayer(
            "PredictiveAnalyticsService",
            "predictive-analytics-service-key"
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_duration_to_hours(duration: str) -> int:
        """Convert a duration string like '7d' or '24h' into hours."""
        duration = duration.strip().lower()
        if duration.endswith("d"):
            return int(duration[:-1]) * 24
        if duration.endswith("h"):
            return int(duration[:-1])
        # Default fallback: treat as days
        try:
            return int(duration) * 24
        except ValueError:
            return 7 * 24

    @staticmethod
    def _parse_duration_to_days(duration: str) -> int:
        """Convert a duration string like '30d' or '720h' into days."""
        duration = duration.strip().lower()
        if duration.endswith("d"):
            return int(duration[:-1])
        if duration.endswith("h"):
            return max(1, int(duration[:-1]) // 24)
        try:
            return int(duration)
        except ValueError:
            return 30

    @staticmethod
    def _format_dt(dt: datetime) -> str:
        """Format datetime for ClickHouse DateTime64(3, 'UTC') columns."""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

    @staticmethod
    def _linear_regression(
        points: List[Dict[str, Any]], x_key: str, y_key: str
    ) -> Tuple[float, float, float]:
        """Compute simple linear regression (slope, intercept, r_squared).

        Args:
            points: List of dicts containing the data points.
            x_key: Key for the independent variable (numeric index).
            y_key: Key for the dependent variable.

        Returns:
            (slope, intercept, r_squared)
        """
        n = len(points)
        if n < 2:
            return 0.0, (points[0][y_key] if points else 0.0), 0.0

        xs = [float(i) for i in range(n)]
        ys = [float(p[y_key]) for p in points]

        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        sum_x2 = sum(x * x for x in xs)

        denom = n * sum_x2 - sum_x * sum_x
        if denom == 0:
            return 0.0, sum_y / n, 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denom
        intercept = (sum_y - slope * sum_x) / n

        # R-squared
        mean_y = sum_y / n
        ss_tot = sum((y - mean_y) ** 2 for y in ys)
        ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

        return slope, intercept, max(0.0, min(1.0, r_squared))

    @staticmethod
    def _residual_std(
        points: List[Dict[str, Any]], y_key: str, slope: float, intercept: float
    ) -> float:
        """Standard deviation of residuals for confidence intervals."""
        n = len(points)
        if n < 3:
            return 0.0
        residuals = [
            float(p[y_key]) - (slope * i + intercept)
            for i, p in enumerate(points)
        ]
        mean_r = sum(residuals) / n
        variance = sum((r - mean_r) ** 2 for r in residuals) / (n - 2)
        return math.sqrt(max(0.0, variance))

    # ------------------------------------------------------------------
    # 1. Trend Forecasting
    # ------------------------------------------------------------------

    async def forecast_trends(
        self,
        customer_id: str,
        metric: str = "error_rate",
        time_range: str = "7d",
        forecast_horizon: str = "7d",
    ) -> Dict[str, Any]:
        """Forecast trends using linear regression on real hourly data.

        Supported metrics: error_rate, log_volume, service_count, warn_rate.

        Args:
            customer_id: Tenant identifier for data isolation.
            metric: The metric to forecast.
            time_range: Historical window to analyse (e.g. '7d', '30d').
            forecast_horizon: How far into the future to project.

        Returns:
            Dictionary containing historical points, projected points,
            regression statistics, and confidence intervals.
        """
        logger.info(
            "forecast_trends called",
            customer_id=customer_id,
            metric=metric,
            time_range=time_range,
            forecast_horizon=forecast_horizon,
        )

        history_hours = self._parse_duration_to_hours(time_range)
        forecast_hours = self._parse_duration_to_hours(forecast_horizon)

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=history_hours)

        # Build the metric expression for ClickHouse
        metric_expr_map = {
            "error_rate": "ROUND(countIf(level = 'ERROR') * 100.0 / count(*), 4)",
            "log_volume": "count(*)",
            "service_count": "uniq(service)",
            "warn_rate": "ROUND(countIf(level = 'WARN') * 100.0 / count(*), 4)",
        }
        metric_expr = metric_expr_map.get(metric)
        if metric_expr is None:
            logger.warning("Unknown metric requested, defaulting to error_rate", metric=metric)
            metric_expr = metric_expr_map["error_rate"]
            metric = "error_rate"

        query = f"""
        SELECT
            toStartOfHour(ts) AS bucket,
            {metric_expr} AS value
        FROM logs_normalized_mt
        WHERE customer_id = %(customer_id)s
          AND ts >= %(start)s
          AND ts <= %(end)s
        GROUP BY bucket
        ORDER BY bucket ASC
        """

        params = {
            "customer_id": customer_id,
            "start": self._format_dt(start),
            "end": self._format_dt(now),
        }

        try:
            rows = await self.db.fetch_all(query, params)
        except Exception as exc:
            logger.error("forecast_trends query failed", error=str(exc), customer_id=customer_id)
            rows = []

        if not rows:
            return {
                "metric": metric,
                "time_range": time_range,
                "forecast_horizon": forecast_horizon,
                "historical": [],
                "projected": [],
                "regression": {"slope": 0, "intercept": 0, "r_squared": 0},
                "message": "Insufficient data for forecasting",
            }

        # Convert rows into serialisable dicts
        historical = []
        for row in rows:
            bucket = row["bucket"]
            ts_str = bucket.isoformat() if isinstance(bucket, datetime) else str(bucket)
            historical.append({
                "timestamp": ts_str,
                "value": float(row["value"]),
            })

        # Linear regression
        slope, intercept, r_squared = self._linear_regression(historical, "timestamp", "value")
        residual_sd = self._residual_std(historical, "value", slope, intercept)

        # Project forward
        n_history = len(historical)
        forecast_steps = max(1, forecast_hours)
        projected = []
        for step in range(1, forecast_steps + 1):
            idx = n_history - 1 + step
            predicted = slope * idx + intercept
            # 95% confidence interval (approx 1.96 * std)
            margin = 1.96 * residual_sd
            future_ts = now + timedelta(hours=step)
            projected.append({
                "timestamp": future_ts.isoformat(),
                "value": round(max(0.0, predicted), 4),
                "lower_bound": round(max(0.0, predicted - margin), 4),
                "upper_bound": round(predicted + margin, 4),
            })

        return {
            "metric": metric,
            "time_range": time_range,
            "forecast_horizon": forecast_horizon,
            "historical": historical,
            "projected": projected,
            "regression": {
                "slope": round(slope, 6),
                "intercept": round(intercept, 4),
                "r_squared": round(r_squared, 4),
            },
            "data_points": n_history,
            "generated_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # 2. Capacity Planning
    # ------------------------------------------------------------------

    async def get_capacity_planning(
        self,
        customer_id: str,
        time_range: str = "30d",
    ) -> Dict[str, Any]:
        """Analyse data volume growth and project capacity limits.

        Queries actual daily log counts from logs_normalized_mt, fits a
        linear growth model, and estimates when configurable capacity
        thresholds will be reached.

        Args:
            customer_id: Tenant identifier.
            time_range: Historical window for growth analysis.

        Returns:
            Growth statistics, per-service breakdown, capacity projections.
        """
        logger.info(
            "get_capacity_planning called",
            customer_id=customer_id,
            time_range=time_range,
        )

        days = self._parse_duration_to_days(time_range)
        now = datetime.now(timezone.utc)
        start = now - timedelta(days=days)

        # Daily log volume
        daily_query = """
        SELECT
            toDate(ts) AS day,
            count(*) AS volume
        FROM logs_normalized_mt
        WHERE customer_id = %(customer_id)s
          AND ts >= %(start)s
          AND ts <= %(end)s
        GROUP BY day
        ORDER BY day ASC
        """
        params = {
            "customer_id": customer_id,
            "start": self._format_dt(start),
            "end": self._format_dt(now),
        }

        try:
            daily_rows = await self.db.fetch_all(daily_query, params)
        except Exception as exc:
            logger.error("capacity_planning daily query failed", error=str(exc))
            daily_rows = []

        # Per-service volume (top 20 by volume)
        service_query = """
        SELECT
            service,
            count(*) AS volume,
            uniq(toDate(ts)) AS active_days
        FROM logs_normalized_mt
        WHERE customer_id = %(customer_id)s
          AND ts >= %(start)s
          AND ts <= %(end)s
          AND service != ''
        GROUP BY service
        ORDER BY volume DESC
        LIMIT 20
        """

        try:
            service_rows = await self.db.fetch_all(service_query, params)
        except Exception as exc:
            logger.error("capacity_planning service query failed", error=str(exc))
            service_rows = []

        # Build daily volume list
        daily_volumes = []
        for row in daily_rows:
            day_val = row["day"]
            day_str = day_val.isoformat() if hasattr(day_val, "isoformat") else str(day_val)
            daily_volumes.append({
                "date": day_str,
                "volume": int(row["volume"]),
            })

        # Growth rate via linear regression on daily volumes
        if len(daily_volumes) >= 2:
            slope, intercept, r_squared = self._linear_regression(
                daily_volumes, "date", "volume"
            )
            current_daily = float(daily_volumes[-1]["volume"])
            avg_daily = sum(d["volume"] for d in daily_volumes) / len(daily_volumes)
            growth_rate_pct = (slope / avg_daily * 100) if avg_daily > 0 else 0.0
        else:
            slope, intercept, r_squared = 0.0, 0.0, 0.0
            current_daily = float(daily_volumes[0]["volume"]) if daily_volumes else 0
            avg_daily = current_daily
            growth_rate_pct = 0.0

        # Project days until capacity thresholds
        capacity_thresholds = [
            {"label": "10M logs/day", "limit": 10_000_000},
            {"label": "50M logs/day", "limit": 50_000_000},
            {"label": "100M logs/day", "limit": 100_000_000},
        ]
        projections = []
        for threshold in capacity_thresholds:
            limit = threshold["limit"]
            if slope > 0 and current_daily < limit:
                # Solve: slope * (n_history + days_until) + intercept = limit
                n_history = len(daily_volumes)
                days_until = max(0, (limit - (slope * (n_history - 1) + intercept)) / slope)
                est_date = now + timedelta(days=days_until)
                projections.append({
                    "threshold": threshold["label"],
                    "limit": limit,
                    "estimated_days_until": round(days_until),
                    "estimated_date": est_date.strftime("%Y-%m-%d"),
                })
            elif current_daily >= limit:
                projections.append({
                    "threshold": threshold["label"],
                    "limit": limit,
                    "estimated_days_until": 0,
                    "estimated_date": "already exceeded",
                })
            else:
                projections.append({
                    "threshold": threshold["label"],
                    "limit": limit,
                    "estimated_days_until": None,
                    "estimated_date": "not projected (flat or declining trend)",
                })

        # Per-service breakdown with daily growth
        top_services = []
        for svc in service_rows:
            active_days = max(1, int(svc.get("active_days", 1)))
            svc_daily_avg = int(svc["volume"]) / active_days
            top_services.append({
                "service": svc["service"],
                "total_volume": int(svc["volume"]),
                "daily_average": round(svc_daily_avg),
                "active_days": active_days,
            })

        return {
            "time_range": time_range,
            "analysis_days": days,
            "current_daily_volume": round(current_daily),
            "average_daily_volume": round(avg_daily),
            "growth_rate_per_day": round(slope, 2),
            "growth_rate_percent": round(growth_rate_pct, 2),
            "r_squared": round(r_squared, 4),
            "daily_volumes": daily_volumes,
            "capacity_projections": projections,
            "top_services": top_services,
            "generated_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # 3. SLA Breach Prediction
    # ------------------------------------------------------------------

    async def predict_sla_breaches(
        self,
        customer_id: str,
        time_range: str = "7d",
        sla_threshold: float = 0.01,
    ) -> Dict[str, Any]:
        """Predict which services risk breaching SLA error-rate thresholds.

        Queries hourly error rates per service, fits a linear trend, and
        checks whether the projected error rate will cross the SLA
        threshold within the next 24-72 hours.

        Args:
            customer_id: Tenant identifier.
            time_range: Historical window for trend analysis.
            sla_threshold: Error rate threshold expressed as a fraction
                           (e.g. 0.01 = 1% error rate).

        Returns:
            List of at-risk services with predicted breach time and confidence.
        """
        logger.info(
            "predict_sla_breaches called",
            customer_id=customer_id,
            time_range=time_range,
            sla_threshold=sla_threshold,
        )

        hours = self._parse_duration_to_hours(time_range)
        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=hours)

        # Convert fractional threshold to percentage for comparison
        sla_threshold_pct = sla_threshold * 100.0

        query = """
        SELECT
            service,
            toStartOfHour(ts) AS bucket,
            count(*) AS total,
            countIf(level = 'ERROR') AS errors,
            ROUND(countIf(level = 'ERROR') * 100.0 / count(*), 4) AS error_rate
        FROM logs_normalized_mt
        WHERE customer_id = %(customer_id)s
          AND ts >= %(start)s
          AND ts <= %(end)s
          AND service != ''
        GROUP BY service, bucket
        HAVING total >= 50
        ORDER BY service ASC, bucket ASC
        """

        params = {
            "customer_id": customer_id,
            "start": self._format_dt(start),
            "end": self._format_dt(now),
        }

        try:
            rows = await self.db.fetch_all(query, params)
        except Exception as exc:
            logger.error("sla_breach query failed", error=str(exc))
            rows = []

        if not rows:
            return {
                "time_range": time_range,
                "sla_threshold": sla_threshold,
                "at_risk_services": [],
                "total_services_analysed": 0,
                "message": "Insufficient data for SLA breach prediction",
                "generated_at": now.isoformat(),
            }

        # Group by service
        service_data: Dict[str, List[Dict]] = {}
        for row in rows:
            svc = row["service"]
            service_data.setdefault(svc, []).append({
                "bucket": row["bucket"],
                "error_rate": float(row["error_rate"]),
                "total": int(row["total"]),
                "errors": int(row["errors"]),
            })

        at_risk: List[Dict[str, Any]] = []
        prediction_horizon_hours = 72  # Look ahead 72 hours

        for svc, points in service_data.items():
            if len(points) < 3:
                continue

            slope, intercept, r_squared = self._linear_regression(
                points, "bucket", "error_rate"
            )

            # Only flag if error rate is trending upward
            if slope <= 0:
                continue

            # Current error rate (last data point)
            current_rate = points[-1]["error_rate"]
            n = len(points)

            # Will the projected rate exceed the threshold?
            projected_at_horizon = slope * (n - 1 + prediction_horizon_hours) + intercept

            if projected_at_horizon > sla_threshold_pct or current_rate > sla_threshold_pct * 0.7:
                # Estimate hours until breach
                if current_rate >= sla_threshold_pct:
                    hours_to_breach = 0
                else:
                    hours_to_breach = max(
                        0, (sla_threshold_pct - (slope * (n - 1) + intercept)) / slope
                    )

                breach_time = now + timedelta(hours=hours_to_breach)
                confidence = min(0.95, r_squared * 0.8 + 0.15) if r_squared > 0.3 else 0.3

                at_risk.append({
                    "service": svc,
                    "current_error_rate": round(current_rate, 4),
                    "sla_threshold_pct": round(sla_threshold_pct, 4),
                    "trend_slope_per_hour": round(slope, 6),
                    "projected_rate_72h": round(max(0, projected_at_horizon), 4),
                    "hours_to_breach": round(hours_to_breach, 1),
                    "predicted_breach_time": breach_time.isoformat() if hours_to_breach > 0 else "already breached",
                    "confidence": round(confidence, 3),
                    "r_squared": round(r_squared, 4),
                    "data_points": n,
                    "risk_level": (
                        "critical" if hours_to_breach == 0
                        else "high" if hours_to_breach < 12
                        else "medium" if hours_to_breach < 48
                        else "low"
                    ),
                })

        # Sort by risk: critical first, then by hours to breach
        risk_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        at_risk.sort(key=lambda s: (risk_order.get(s["risk_level"], 4), s["hours_to_breach"]))

        return {
            "time_range": time_range,
            "sla_threshold": sla_threshold,
            "sla_threshold_pct": round(sla_threshold_pct, 4),
            "prediction_horizon_hours": prediction_horizon_hours,
            "at_risk_services": at_risk,
            "total_services_analysed": len(service_data),
            "services_at_risk": len(at_risk),
            "generated_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # 4. What-If Scenario Modeling
    # ------------------------------------------------------------------

    async def run_what_if_scenario(
        self,
        customer_id: str,
        scenario_type: str,
        parameters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Model the impact of hypothetical changes against real baselines.

        Queries actual current metrics from logs_normalized_mt (last 24h)
        and applies the user-specified scenario to project impact.

        Supported scenario_types:
            - traffic_increase: parameters.factor (e.g. 2.0 = double traffic)
            - add_services: parameters.count (e.g. 5 = add 5 services)
            - error_rate_change: parameters.factor (e.g. 1.5 = 50% more errors)
            - combined: parameters with any combination of the above

        Args:
            customer_id: Tenant identifier.
            scenario_type: Type of scenario to model.
            parameters: Scenario-specific parameters.

        Returns:
            Baseline metrics, projected metrics, and impact analysis.
        """
        logger.info(
            "run_what_if_scenario called",
            customer_id=customer_id,
            scenario_type=scenario_type,
            parameters=parameters,
        )

        now = datetime.now(timezone.utc)
        start = now - timedelta(hours=24)

        # Fetch current 24h baseline
        baseline_query = """
        SELECT
            count(*) AS total_logs,
            countIf(level = 'ERROR') AS total_errors,
            countIf(level = 'WARN') AS total_warnings,
            ROUND(countIf(level = 'ERROR') * 100.0 / count(*), 4) AS error_rate,
            ROUND(countIf(level = 'WARN') * 100.0 / count(*), 4) AS warn_rate,
            uniq(service) AS service_count,
            uniq(src_ip) AS unique_sources,
            uniq(user_id) AS unique_users
        FROM logs_normalized_mt
        WHERE customer_id = %(customer_id)s
          AND ts >= %(start)s
          AND ts <= %(end)s
        """

        params = {
            "customer_id": customer_id,
            "start": self._format_dt(start),
            "end": self._format_dt(now),
        }

        try:
            result = await self.db.fetch_one(baseline_query, params)
        except Exception as exc:
            logger.error("what_if baseline query failed", error=str(exc))
            result = None

        if not result or result.get("total_logs", 0) == 0:
            return {
                "scenario_type": scenario_type,
                "parameters": parameters,
                "baseline": {},
                "projected": {},
                "impact": {},
                "message": "Insufficient baseline data for scenario modeling",
                "generated_at": now.isoformat(),
            }

        baseline = {
            "total_logs": int(result["total_logs"]),
            "total_errors": int(result["total_errors"]),
            "total_warnings": int(result["total_warnings"]),
            "error_rate": float(result["error_rate"]),
            "warn_rate": float(result["warn_rate"]),
            "service_count": int(result["service_count"]),
            "unique_sources": int(result["unique_sources"]),
            "unique_users": int(result["unique_users"]),
        }

        # Apply scenario
        projected = dict(baseline)
        impact_notes: List[str] = []

        traffic_factor = parameters.get("traffic_factor", parameters.get("factor", 1.0))
        added_services = parameters.get("service_count", parameters.get("count", 0))
        error_factor = parameters.get("error_factor", parameters.get("factor", 1.0))

        if scenario_type == "traffic_increase":
            traffic_factor = max(1.0, float(traffic_factor))
            projected["total_logs"] = round(baseline["total_logs"] * traffic_factor)
            projected["total_errors"] = round(baseline["total_errors"] * traffic_factor)
            projected["total_warnings"] = round(baseline["total_warnings"] * traffic_factor)
            projected["unique_sources"] = round(baseline["unique_sources"] * math.sqrt(traffic_factor))
            projected["unique_users"] = round(baseline["unique_users"] * math.sqrt(traffic_factor))
            impact_notes.append(
                f"Traffic multiplied by {traffic_factor}x: "
                f"{baseline['total_logs']:,} -> {projected['total_logs']:,} logs/day"
            )
            # Error rate stays proportional unless system is overloaded
            if traffic_factor > 3.0:
                overload_factor = 1.0 + (traffic_factor - 3.0) * 0.1
                projected["error_rate"] = round(baseline["error_rate"] * overload_factor, 4)
                impact_notes.append(
                    f"System overload expected at {traffic_factor}x traffic, "
                    f"error rate projected to increase to {projected['error_rate']}%"
                )

        elif scenario_type == "add_services":
            added = max(0, int(added_services))
            projected["service_count"] = baseline["service_count"] + added
            avg_logs_per_service = baseline["total_logs"] / max(1, baseline["service_count"])
            projected["total_logs"] = round(baseline["total_logs"] + avg_logs_per_service * added)
            projected["total_errors"] = round(
                baseline["total_errors"]
                + (baseline["total_errors"] / max(1, baseline["service_count"])) * added
            )
            projected["total_warnings"] = round(
                baseline["total_warnings"]
                + (baseline["total_warnings"] / max(1, baseline["service_count"])) * added
            )
            impact_notes.append(
                f"Adding {added} services: "
                f"{baseline['service_count']} -> {projected['service_count']} services"
            )
            impact_notes.append(
                f"Estimated additional log volume: "
                f"+{round(avg_logs_per_service * added):,} logs/day"
            )

        elif scenario_type == "error_rate_change":
            error_factor = max(0.0, float(error_factor))
            projected["error_rate"] = round(baseline["error_rate"] * error_factor, 4)
            projected["total_errors"] = round(baseline["total_errors"] * error_factor)
            impact_notes.append(
                f"Error rate changed by {error_factor}x: "
                f"{baseline['error_rate']}% -> {projected['error_rate']}%"
            )
            if projected["error_rate"] > 1.0:
                impact_notes.append(
                    "WARNING: Projected error rate exceeds 1% SLA threshold"
                )

        elif scenario_type == "combined":
            # Apply traffic increase
            if traffic_factor and float(traffic_factor) > 1.0:
                tf = float(traffic_factor)
                projected["total_logs"] = round(baseline["total_logs"] * tf)
                projected["total_errors"] = round(baseline["total_errors"] * tf)
                projected["total_warnings"] = round(baseline["total_warnings"] * tf)
                impact_notes.append(f"Traffic increase: {tf}x")

            # Apply additional services
            if added_services and int(added_services) > 0:
                added = int(added_services)
                projected["service_count"] = baseline["service_count"] + added
                avg_logs = projected["total_logs"] / max(1, baseline["service_count"])
                projected["total_logs"] = round(projected["total_logs"] + avg_logs * added)
                impact_notes.append(f"Added {added} services")

            # Apply error rate change
            if error_factor and float(error_factor) != 1.0:
                ef = float(error_factor)
                projected["total_errors"] = round(projected["total_errors"] * ef)
                impact_notes.append(f"Error rate factor: {ef}x")

            # Recalculate derived rates
            if projected["total_logs"] > 0:
                projected["error_rate"] = round(
                    projected["total_errors"] * 100.0 / projected["total_logs"], 4
                )
                projected["warn_rate"] = round(
                    projected["total_warnings"] * 100.0 / projected["total_logs"], 4
                )

        else:
            impact_notes.append(f"Unknown scenario type: {scenario_type}")

        # Recalculate derived rates for non-combined scenarios
        if scenario_type != "combined" and projected["total_logs"] > 0:
            projected["error_rate"] = round(
                projected["total_errors"] * 100.0 / projected["total_logs"], 4
            )
            projected["warn_rate"] = round(
                projected["total_warnings"] * 100.0 / projected["total_logs"], 4
            )

        # Compute impact summary
        impact = {
            "log_volume_change": projected["total_logs"] - baseline["total_logs"],
            "log_volume_change_pct": round(
                (projected["total_logs"] - baseline["total_logs"])
                * 100.0
                / max(1, baseline["total_logs"]),
                2,
            ),
            "error_rate_change": round(projected["error_rate"] - baseline["error_rate"], 4),
            "service_count_change": projected["service_count"] - baseline["service_count"],
            "sla_risk": projected["error_rate"] > 1.0,
            "capacity_risk": projected["total_logs"] > 50_000_000,
            "notes": impact_notes,
        }

        return {
            "scenario_type": scenario_type,
            "parameters": parameters,
            "baseline": baseline,
            "projected": projected,
            "impact": impact,
            "generated_at": now.isoformat(),
        }

    # ------------------------------------------------------------------
    # 5. Prediction Summary
    # ------------------------------------------------------------------

    async def get_prediction_summary(self, customer_id: str) -> Dict[str, Any]:
        """Return a combined summary of all prediction capabilities.

        Calls forecast, capacity planning, and SLA breach prediction with
        sensible defaults and aggregates the results into one payload.

        Args:
            customer_id: Tenant identifier.

        Returns:
            Combined summary with risk scores and key metrics.
        """
        logger.info("get_prediction_summary called", customer_id=customer_id)
        now = datetime.now(timezone.utc)

        # Run all analyses (catch individual failures gracefully)
        forecast_result = {}
        capacity_result = {}
        sla_result = {}

        try:
            forecast_result = await self.forecast_trends(
                customer_id=customer_id,
                metric="error_rate",
                time_range="7d",
                forecast_horizon="7d",
            )
        except Exception as exc:
            logger.error("summary: forecast_trends failed", error=str(exc))

        try:
            capacity_result = await self.get_capacity_planning(
                customer_id=customer_id, time_range="30d"
            )
        except Exception as exc:
            logger.error("summary: capacity_planning failed", error=str(exc))

        try:
            sla_result = await self.predict_sla_breaches(
                customer_id=customer_id, time_range="7d", sla_threshold=0.01
            )
        except Exception as exc:
            logger.error("summary: sla_breaches failed", error=str(exc))

        # Build risk score (0-100)
        risk_score = 0
        risk_factors: List[str] = []

        # SLA risk component (0-40)
        sla_at_risk = sla_result.get("services_at_risk", 0)
        if sla_at_risk > 0:
            sla_risk_points = min(40, sla_at_risk * 10)
            risk_score += sla_risk_points
            risk_factors.append(f"{sla_at_risk} service(s) at risk of SLA breach")

        # Trend component (0-30) based on error rate slope
        slope = forecast_result.get("regression", {}).get("slope", 0)
        if slope > 0:
            trend_risk_points = min(30, int(slope * 100))
            risk_score += trend_risk_points
            risk_factors.append("Error rate trending upward")

        # Capacity component (0-30)
        growth_pct = capacity_result.get("growth_rate_percent", 0)
        if growth_pct > 5:
            cap_risk_points = min(30, int(growth_pct * 2))
            risk_score += cap_risk_points
            risk_factors.append(f"Data volume growing at {growth_pct:.1f}% per day")

        risk_score = min(100, risk_score)
        risk_level = (
            "critical" if risk_score >= 75
            else "high" if risk_score >= 50
            else "medium" if risk_score >= 25
            else "low"
        )

        return {
            "overall_risk_score": risk_score,
            "risk_level": risk_level,
            "risk_factors": risk_factors,
            "forecast_summary": {
                "metric": forecast_result.get("metric", "error_rate"),
                "data_points": forecast_result.get("data_points", 0),
                "trend_direction": "up" if slope > 0 else "down" if slope < 0 else "flat",
                "slope": round(slope, 6),
                "r_squared": forecast_result.get("regression", {}).get("r_squared", 0),
            },
            "capacity_summary": {
                "current_daily_volume": capacity_result.get("current_daily_volume", 0),
                "growth_rate_percent": capacity_result.get("growth_rate_percent", 0),
                "top_services_count": len(capacity_result.get("top_services", [])),
                "projections": capacity_result.get("capacity_projections", []),
            },
            "sla_summary": {
                "total_services_analysed": sla_result.get("total_services_analysed", 0),
                "services_at_risk": sla_result.get("services_at_risk", 0),
                "at_risk_services": [
                    {
                        "service": s["service"],
                        "risk_level": s["risk_level"],
                        "hours_to_breach": s["hours_to_breach"],
                    }
                    for s in sla_result.get("at_risk_services", [])[:5]
                ],
            },
            "generated_at": now.isoformat(),
        }
