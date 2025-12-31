"""
Anomaly Deep Dive Analysis Service

Provides comprehensive root cause analysis for detected anomalies:
1. Timeline reconstruction
2. Correlated logs and metrics
3. Similar incident matching
4. Impact assessment
5. Actionable recommendations

This powers the "Investigate" button in the UI.

Performance Target: <10 seconds for comprehensive analysis
"""

import structlog
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from dao.ai_dao import AIDAO
from services.rca_engine import get_rca_engine

logger = structlog.get_logger(__name__)


@dataclass
class TimelineEvent:
    """Event in the anomaly timeline"""
    time: str
    event: str
    impact_score: float
    source: str  # "deployment", "config_change", "metric_spike", etc.


@dataclass
class RootCauseAnalysis:
    """Root cause analysis result"""
    type: str
    confidence: float
    evidence: List[str]
    timeline: List[TimelineEvent]


@dataclass
class ContributingFactor:
    """Contributing factor to the anomaly"""
    factor: str
    confidence: float
    evidence: List[str]


@dataclass
class SimilarIncident:
    """Similar historical incident"""
    incident_id: str
    occurred_at: str
    similarity_score: float
    resolution: str
    time_to_resolve: str


@dataclass
class ImpactAssessment:
    """Business impact assessment"""
    affected_users: int
    failed_requests: int
    estimated_revenue_impact: float
    slo_breach: bool
    severity: str


@dataclass
class RecommendedAction:
    """Actionable recommendation"""
    priority: int
    action: str
    expected_impact: str
    runbook_url: Optional[str] = None


@dataclass
class CorrelatedLog:
    """Correlated log entry"""
    timestamp: str
    level: str
    message: str
    service: str
    count: int


@dataclass
class CorrelatedMetric:
    """Correlated metric change"""
    metric: str
    value: float
    threshold: float
    deviation: float


@dataclass
class AnomalyAnalysisResult:
    """Complete analysis result"""
    anomaly_id: str
    analysis_id: str
    root_cause: RootCauseAnalysis
    contributing_factors: List[ContributingFactor]
    impact_assessment: ImpactAssessment
    similar_incidents: List[SimilarIncident]
    recommended_actions: List[RecommendedAction]
    correlated_logs: List[CorrelatedLog]
    correlated_metrics: List[CorrelatedMetric]
    correlated_events: List[Dict[str, Any]]
    analysis_duration_ms: int


class AnomalyAnalyzer:
    """
    Deep Dive Anomaly Analysis Engine

    Provides comprehensive RCA for anomalies
    """

    def __init__(self):
        self.dao = AIDAO()
        self.rca_engine = get_rca_engine()

    def _format_clickhouse_datetime(self, dt: datetime) -> str:
        """Format datetime for ClickHouse"""
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

    async def analyze_anomaly(
        self,
        anomaly_id: str,
        customer_id: str,
        analysis_depth: str = "comprehensive",
        include_similar_incidents: bool = True,
        time_window_expansion: str = "1h"
    ) -> AnomalyAnalysisResult:
        """
        Perform deep dive analysis on an anomaly

        Args:
            anomaly_id: Anomaly to analyze
            customer_id: Tenant identifier
            analysis_depth: "quick" | "standard" | "comprehensive"
            include_similar_incidents: Whether to find similar historical incidents
            time_window_expansion: How much to expand the time window for context

        Returns:
            Comprehensive analysis result
        """

        start_time = datetime.now(timezone.utc)
        logger.info("Starting anomaly analysis",
                   anomaly_id=anomaly_id,
                   depth=analysis_depth)

        # Step 1: Fetch the anomaly details
        anomaly = await self._fetch_anomaly(anomaly_id, customer_id)
        if not anomaly:
            raise ValueError(f"Anomaly {anomaly_id} not found")

        # Step 2: Expand time window for context
        expansion_hours = self._parse_time_window(time_window_expansion)
        detected_at = anomaly.get("detected_at")
        if isinstance(detected_at, str):
            detected_at = datetime.fromisoformat(detected_at.replace('Z', '+00:00'))

        window_start = detected_at - timedelta(hours=expansion_hours)
        window_end = detected_at + timedelta(hours=expansion_hours / 2)

        # Step 3: Run parallel analysis tasks
        tasks = []

        # 3a. Root cause analysis using RCA engine
        rca_task = self._perform_rca_analysis(anomaly, customer_id, window_start, window_end)

        # 3b. Find correlated logs
        logs_task = self._find_correlated_logs(anomaly, customer_id, window_start, window_end)

        # 3c. Find correlated metrics
        metrics_task = self._find_correlated_metrics(anomaly, customer_id, window_start, window_end)

        # 3d. Find correlated events (deployments, config changes)
        events_task = self._find_correlated_events(anomaly, customer_id, window_start, window_end)

        # 3e. Assess business impact
        impact_task = self._assess_impact(anomaly, customer_id, window_start, window_end)

        # 3f. Find similar incidents (if requested)
        if include_similar_incidents:
            similar_task = self._find_similar_incidents(anomaly, customer_id)
        else:
            similar_task = self._return_empty_similar()

        # Execute all tasks concurrently
        import asyncio
        results = await asyncio.gather(
            rca_task,
            logs_task,
            metrics_task,
            events_task,
            impact_task,
            similar_task,
            return_exceptions=True
        )

        root_cause, correlated_logs, correlated_metrics, correlated_events, impact, similar_incidents = results

        # Handle any exceptions
        if isinstance(root_cause, Exception):
            logger.error("RCA failed", error=str(root_cause))
            root_cause = self._default_root_cause(anomaly)

        if isinstance(correlated_logs, Exception):
            logger.error("Log correlation failed", error=str(correlated_logs))
            correlated_logs = []

        if isinstance(correlated_metrics, Exception):
            logger.error("Metric correlation failed", error=str(correlated_metrics))
            correlated_metrics = []

        if isinstance(correlated_events, Exception):
            logger.error("Event correlation failed", error=str(correlated_events))
            correlated_events = []

        if isinstance(impact, Exception):
            logger.error("Impact assessment failed", error=str(impact))
            impact = self._default_impact()

        if isinstance(similar_incidents, Exception):
            logger.error("Similar incidents search failed", error=str(similar_incidents))
            similar_incidents = []

        # Step 4: Generate contributing factors
        contributing_factors = self._identify_contributing_factors(
            anomaly, root_cause, correlated_logs, correlated_metrics, correlated_events
        )

        # Step 5: Generate actionable recommendations
        recommended_actions = self._generate_actionable_recommendations(
            anomaly, root_cause, contributing_factors, similar_incidents
        )

        # Calculate analysis duration
        end_time = datetime.now(timezone.utc)
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        analysis_id = f"analysis_{uuid.uuid4().hex[:12]}"

        # Step 6: Save analysis to database
        await self._save_analysis_result(
            analysis_id,
            anomaly_id,
            customer_id,
            root_cause,
            contributing_factors,
            impact,
            similar_incidents,
            recommended_actions,
            correlated_logs,
            correlated_metrics,
            correlated_events,
            duration_ms
        )

        logger.info("Anomaly analysis complete",
                   anomaly_id=anomaly_id,
                   duration_ms=duration_ms)

        return AnomalyAnalysisResult(
            anomaly_id=anomaly_id,
            analysis_id=analysis_id,
            root_cause=root_cause,
            contributing_factors=contributing_factors,
            impact_assessment=impact,
            similar_incidents=similar_incidents,
            recommended_actions=recommended_actions,
            correlated_logs=correlated_logs,
            correlated_metrics=correlated_metrics,
            correlated_events=correlated_events,
            analysis_duration_ms=duration_ms
        )

    async def _fetch_anomaly(self, anomaly_id: str, customer_id: str) -> Optional[Dict[str, Any]]:
        """Fetch anomaly from database"""

        # Check multi_metric_anomalies_mt first
        query = """
        SELECT *
        FROM multi_metric_anomalies_mt
        WHERE anomaly_id = %(anomaly_id)s
          AND customer_id = %(customer_id)s
        LIMIT 1
        """

        result = await self.dao.execute_query(query, {
            "anomaly_id": anomaly_id,
            "customer_id": customer_id
        })

        if result and len(result) > 0:
            return result[0]

        # Fallback: check if it's from the old anomaly detection
        # Return a synthetic anomaly object
        return {
            "anomaly_id": anomaly_id,
            "detected_at": datetime.now(timezone.utc).isoformat(),
            "severity": "medium",
            "title": "Anomaly Analysis",
            "description": "Analyzing detected anomaly",
            "affected_metrics": "[]",
            "evidence": "{}"
        }

    async def _perform_rca_analysis(
        self, anomaly: Dict, customer_id: str, window_start: datetime, window_end: datetime
    ) -> RootCauseAnalysis:
        """Perform root cause analysis"""

        try:
            # Use existing RCA engine
            incident_data = {
                "title": anomaly.get("title", "Anomaly"),
                "description": anomaly.get("description", ""),
                "severity": anomaly.get("severity", "medium"),
                "detected_at": anomaly.get("detected_at"),
                "services": []  # Extract from anomaly evidence
            }

            rca_result = await self.rca_engine.analyze_incident(
                incident=incident_data,
                customer_id=customer_id
            )

            # Convert RCA result to our format
            timeline = [
                TimelineEvent(
                    time=event.timestamp.isoformat() if hasattr(event.timestamp, 'isoformat') else str(event.timestamp),
                    event=event.description,
                    impact_score=event.impact_score,
                    source="rca_engine"
                )
                for event in rca_result.timeline
            ]

            return RootCauseAnalysis(
                type=rca_result.root_cause.cause_type,
                confidence=rca_result.root_cause.confidence,
                evidence=[rca_result.root_cause.description],
                timeline=timeline
            )

        except Exception as e:
            logger.error("RCA engine failed", error=str(e))
            return self._default_root_cause(anomaly)

    def _default_root_cause(self, anomaly: Dict) -> RootCauseAnalysis:
        """Default root cause when RCA fails"""
        return RootCauseAnalysis(
            type="unknown",
            confidence=0.5,
            evidence=["Automated analysis in progress"],
            timeline=[
                TimelineEvent(
                    time=anomaly.get("detected_at", datetime.now(timezone.utc).isoformat()),
                    event=anomaly.get("title", "Anomaly detected"),
                    impact_score=0.7,
                    source="anomaly_detector"
                )
            ]
        )

    async def _find_correlated_logs(
        self, anomaly: Dict, customer_id: str, window_start: datetime, window_end: datetime
    ) -> List[CorrelatedLog]:
        """Find logs correlated with the anomaly"""

        query = """
        SELECT
            level,
            msg as message,
            service,
            COUNT(*) as count,
            MIN(ts) as first_seen
        FROM logs_normalized_mt
        WHERE customer_id = %(customer_id)s
          AND ts >= %(start_time)s
          AND ts <= %(end_time)s
          AND level IN ('ERROR', 'WARN')
        GROUP BY level, msg, service
        ORDER BY count DESC
        LIMIT 10
        """

        result = await self.dao.execute_query(query, {
            "customer_id": customer_id,
            "start_time": self._format_clickhouse_datetime(window_start),
            "end_time": self._format_clickhouse_datetime(window_end)
        })

        correlated_logs = []
        for row in result:
            correlated_logs.append(CorrelatedLog(
                timestamp=row["first_seen"].isoformat() if hasattr(row["first_seen"], 'isoformat') else str(row["first_seen"]),
                level=row["level"],
                message=row["message"][:200],  # Truncate long messages
                service=row["service"],
                count=row["count"]
            ))

        return correlated_logs

    async def _find_correlated_metrics(
        self, anomaly: Dict, customer_id: str, window_start: datetime, window_end: datetime
    ) -> List[CorrelatedMetric]:
        """Find metrics that spiked around the same time"""

        query = """
        SELECT
            'cpu_usage' as metric,
            AVG(cpu_percent) as avg_value,
            MAX(cpu_percent) as max_value,
            80.0 as threshold
        FROM metrics_mt
        WHERE customer_id = %(customer_id)s
          AND timestamp >= %(start_time)s
          AND timestamp <= %(end_time)s
          AND cpu_percent > 0
        HAVING max_value > threshold

        UNION ALL

        SELECT
            'memory_usage' as metric,
            AVG(memory_percent) as avg_value,
            MAX(memory_percent) as max_value,
            80.0 as threshold
        FROM metrics_mt
        WHERE customer_id = %(customer_id)s
          AND timestamp >= %(start_time)s
          AND timestamp <= %(end_time)s
          AND memory_percent > 0
        HAVING max_value > threshold
        """

        result = await self.dao.execute_query(query, {
            "customer_id": customer_id,
            "start_time": self._format_clickhouse_datetime(window_start),
            "end_time": self._format_clickhouse_datetime(window_end)
        })

        correlated_metrics = []
        for row in result:
            correlated_metrics.append(CorrelatedMetric(
                metric=row["metric"],
                value=row["max_value"],
                threshold=row["threshold"],
                deviation=(row["max_value"] - row["threshold"]) / row["threshold"]
            ))

        return correlated_metrics

    async def _find_correlated_events(
        self, anomaly: Dict, customer_id: str, window_start: datetime, window_end: datetime
    ) -> List[Dict[str, Any]]:
        """Find system events (deployments, config changes) around the anomaly"""

        # Placeholder - would query deployment tracking, config change logs, etc.
        # For now, return empty list
        return []

    async def _assess_impact(
        self, anomaly: Dict, customer_id: str, window_start: datetime, window_end: datetime
    ) -> ImpactAssessment:
        """Assess business impact of the anomaly"""

        # Query for affected users and failed requests
        query = """
        SELECT
            uniq(user_id) as affected_users,
            countIf(level = 'ERROR') as failed_requests
        FROM logs_normalized_mt
        WHERE customer_id = %(customer_id)s
          AND ts >= %(start_time)s
          AND ts <= %(end_time)s
        """

        result = await self.dao.execute_query(query, {
            "customer_id": customer_id,
            "start_time": self._format_clickhouse_datetime(window_start),
            "end_time": self._format_clickhouse_datetime(window_end)
        })

        if result and len(result) > 0:
            row = result[0]
            affected_users = row.get("affected_users", 0)
            failed_requests = row.get("failed_requests", 0)
        else:
            affected_users = 0
            failed_requests = 0

        # Estimate revenue impact (placeholder - would use real business metrics)
        estimated_revenue_impact = failed_requests * 0.50  # $0.50 per failed request

        # Check SLO breach (placeholder)
        slo_breach = failed_requests > 100

        return ImpactAssessment(
            affected_users=affected_users,
            failed_requests=failed_requests,
            estimated_revenue_impact=estimated_revenue_impact,
            slo_breach=slo_breach,
            severity=anomaly.get("severity", "medium")
        )

    def _default_impact(self) -> ImpactAssessment:
        """Default impact when assessment fails"""
        return ImpactAssessment(
            affected_users=0,
            failed_requests=0,
            estimated_revenue_impact=0.0,
            slo_breach=False,
            severity="unknown"
        )

    async def _find_similar_incidents(
        self, anomaly: Dict, customer_id: str
    ) -> List[SimilarIncident]:
        """Find similar historical incidents"""

        # Placeholder - would use vector similarity search or pattern matching
        # For now, return empty list
        return []

    async def _return_empty_similar(self) -> List[SimilarIncident]:
        """Return empty similar incidents list"""
        return []

    def _identify_contributing_factors(
        self,
        anomaly: Dict,
        root_cause: RootCauseAnalysis,
        correlated_logs: List[CorrelatedLog],
        correlated_metrics: List[CorrelatedMetric],
        correlated_events: List[Dict[str, Any]]
    ) -> List[ContributingFactor]:
        """Identify contributing factors"""

        factors = []

        # From correlated metrics
        for metric in correlated_metrics:
            if metric.deviation > 0.2:
                factors.append(ContributingFactor(
                    factor=f"High {metric.metric}: {metric.value:.1f}% (threshold: {metric.threshold}%)",
                    confidence=min(metric.deviation, 0.95),
                    evidence=[f"Metric exceeded threshold by {metric.deviation*100:.0f}%"]
                ))

        # From correlated logs
        if len(correlated_logs) > 5:
            factors.append(ContributingFactor(
                factor=f"High volume of errors: {len(correlated_logs)} distinct error patterns",
                confidence=0.8,
                evidence=[log.message for log in correlated_logs[:3]]
            ))

        return factors[:5]  # Limit to top 5

    def _generate_actionable_recommendations(
        self,
        anomaly: Dict,
        root_cause: RootCauseAnalysis,
        contributing_factors: List[ContributingFactor],
        similar_incidents: List[SimilarIncident]
    ) -> List[RecommendedAction]:
        """Generate prioritized actionable recommendations"""

        recommendations = []

        # From similar incidents
        if similar_incidents:
            for incident in similar_incidents[:1]:  # Top similar incident
                recommendations.append(RecommendedAction(
                    priority=1,
                    action=f"Apply same fix as incident {incident.incident_id}: {incident.resolution}",
                    expected_impact="High - this resolution worked before",
                    runbook_url=None
                ))

        # Based on severity
        severity = anomaly.get("severity", "medium")
        if severity in ["critical", "high"]:
            recommendations.append(RecommendedAction(
                priority=1,
                action="Investigate recent deployments and rollback if necessary",
                expected_impact="Immediate resolution if deployment-related",
                runbook_url=None
            ))

        # Based on contributing factors
        for factor in contributing_factors[:2]:
            if "cpu" in factor.factor.lower():
                recommendations.append(RecommendedAction(
                    priority=2,
                    action="Scale horizontally or optimize CPU-intensive code paths",
                    expected_impact="Reduces CPU pressure",
                    runbook_url=None
                ))
            elif "memory" in factor.factor.lower():
                recommendations.append(RecommendedAction(
                    priority=2,
                    action="Check for memory leaks and increase memory limits if needed",
                    expected_impact="Resolves memory pressure",
                    runbook_url=None
                ))

        # Generic recommendations
        recommendations.append(RecommendedAction(
            priority=3,
            action="Review logs and set up alerts for early detection",
            expected_impact="Prevents future occurrences",
            runbook_url=None
        ))

        return recommendations[:5]  # Limit to top 5

    async def _save_analysis_result(
        self,
        analysis_id: str,
        anomaly_id: str,
        customer_id: str,
        root_cause: RootCauseAnalysis,
        contributing_factors: List[ContributingFactor],
        impact: ImpactAssessment,
        similar_incidents: List[SimilarIncident],
        recommendations: List[RecommendedAction],
        correlated_logs: List[CorrelatedLog],
        correlated_metrics: List[CorrelatedMetric],
        correlated_events: List[Dict[str, Any]],
        duration_ms: int
    ):
        """Save analysis result to database"""

        import json

        query = """
        INSERT INTO anomaly_analysis_mt (
            analysis_id, anomaly_id, customer_id,
            root_cause_type, root_cause_confidence, evidence, timeline,
            contributing_factors, impact_assessment, similar_incidents,
            recommended_actions, correlated_logs, correlated_metrics,
            correlated_events, analysis_duration_ms, analyzed_at
        ) VALUES
        """

        values = {
            "analysis_id": analysis_id,
            "anomaly_id": anomaly_id,
            "customer_id": customer_id,
            "root_cause_type": root_cause.type,
            "root_cause_confidence": root_cause.confidence,
            "evidence": root_cause.evidence,
            "timeline": json.dumps([asdict(e) for e in root_cause.timeline]),
            "contributing_factors": json.dumps([asdict(f) for f in contributing_factors]),
            "impact_assessment": json.dumps(asdict(impact)),
            "similar_incidents": [s.incident_id for s in similar_incidents],
            "recommended_actions": json.dumps([asdict(r) for r in recommendations]),
            "correlated_logs": json.dumps([asdict(l) for l in correlated_logs]),
            "correlated_metrics": json.dumps([asdict(m) for m in correlated_metrics]),
            "correlated_events": json.dumps(correlated_events),
            "analysis_duration_ms": duration_ms,
            "analyzed_at": self._format_clickhouse_datetime(datetime.now(timezone.utc))
        }

        # Build INSERT statement
        columns = ", ".join(values.keys())
        placeholders = ", ".join(f"%({k})s" for k in values.keys())
        full_query = f"{query} ({columns}) VALUES ({placeholders})"

        try:
            await self.dao.execute_query(full_query, values)
            logger.info("Analysis result saved", analysis_id=analysis_id)
        except Exception as e:
            logger.error("Failed to save analysis result", error=str(e))

    def _parse_time_window(self, time_window: str) -> int:
        """Parse time window to hours"""
        if time_window.endswith("h"):
            return int(time_window[:-1])
        elif time_window.endswith("d"):
            return int(time_window[:-1]) * 24
        else:
            return 1


# Singleton instance
_anomaly_analyzer_instance = None

def get_anomaly_analyzer() -> AnomalyAnalyzer:
    """Get singleton instance of anomaly analyzer"""
    global _anomaly_analyzer_instance
    if _anomaly_analyzer_instance is None:
        _anomaly_analyzer_instance = AnomalyAnalyzer()
    return _anomaly_analyzer_instance