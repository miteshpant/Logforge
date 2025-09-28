"""
M6 AI API - Natural Language Processing & Root Cause Analysis Endpoints
Database-backed service/dao pattern with comprehensive AI capabilities
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Header
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import structlog

from services.ai_service import AIService
from authn_authz_middleware import get_current_user

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/v1/ai", tags=["ai"])


# Pydantic models for API requests/responses
class NLQueryRequest(BaseModel):
    """Natural language query request"""
    question: str = Field(..., description="Natural language question")
    context: Dict[str, Any] = Field(default_factory=dict, description="Query context")
    max_results: int = Field(100, description="Maximum results to return")


class InvestigationRequest(BaseModel):
    """Investigation request"""
    title: str = Field(..., description="Investigation title")
    description: str = Field(..., description="Investigation description")
    incident_data: Dict[str, Any] = Field(..., description="Incident data")
    context: Dict[str, Any] = Field(default_factory=dict, description="Investigation context")


class AnalysisRequest(BaseModel):
    """Incident analysis request"""
    incident: Dict[str, Any] = Field(..., description="Incident details")
    context: Dict[str, Any] = Field(default_factory=dict, description="Analysis context")


class BaselineRequest(BaseModel):
    """ML baseline save request"""
    model_id: str = Field(..., description="Model identifier")
    service_name: str = Field(..., description="Service name")
    baseline_type: str = Field(..., description="Baseline type")
    baseline_data: Dict[str, Any] = Field(..., description="Baseline model data")
    training_metrics: Dict[str, Any] = Field(default_factory=dict, description="Training metrics")


class AnomalyDetectionRequest(BaseModel):
    """Anomaly detection request"""
    time_range: str = Field("24h", description="Time range for detection")
    severity_filter: List[str] = Field(default_factory=list, description="Severity filters")
    category_filter: List[str] = Field(default_factory=list, description="Category filters") 
    service_filter: List[str] = Field(default_factory=list, description="Service filters")


class KnowledgeSearchRequest(BaseModel):
    """Knowledge base search request"""
    symptoms: str = Field(..., description="Comma-separated symptoms")
    services: Optional[str] = Field(None, description="Comma-separated service names")
    category: Optional[str] = Field(None, description="Incident category")


class SolutionRequest(BaseModel):
    """Add solution request"""
    incident_type: str = Field(..., description="Type of incident")
    symptoms: List[str] = Field(..., description="Incident symptoms")
    solution: Dict[str, Any] = Field(..., description="Solution details")
    related_services: List[str] = Field(default_factory=list, description="Related services")


class CorrelationRequest(BaseModel):
    """Event correlation request"""
    events: List[Dict[str, Any]] = Field(..., description="Events to correlate")
    correlation_window: str = Field("1h", description="Correlation time window")
    confidence_threshold: float = Field(0.7, description="Minimum confidence threshold")


class QueryFeedbackRequest(BaseModel):
    """Query feedback request"""
    query_id: str = Field(..., description="Query ID")
    feedback_score: int = Field(..., description="Feedback score (-1, 0, 1)")
    feedback_notes: str = Field("", description="Feedback notes")


# Authentication handled by get_current_user middleware


@router.post("/query")
async def process_natural_language_query(
    request: NLQueryRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Process natural language question and generate insights"""
    user_id = current_user.id
    
    try:
        ai_service = AIService()
        
        result = await ai_service.process_natural_language_query(
            question=request.question,
            context=request.context,
            max_results=request.max_results,
            user_id=user_id,
            customer_id=customer_id
        )
        
        return {
            "query_id": result.query_id,
            "original_question": result.original_question,
            "generated_sql": result.generated_sql,
            "explanation": result.explanation,
            "results": result.results,
            "suggestions": result.suggestions,
            "confidence_score": result.confidence_score,
            "execution_time_ms": result.execution_time_ms,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to process NL query", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to process query: {str(e)}")


@router.get("/query/history")
async def get_query_history(
    limit: int = 50,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Get user's natural language query history"""
    user_id = current_user.id
    
    try:
        ai_service = AIService()
        
        history = await ai_service.get_query_history(user_id, customer_id, limit)
        
        return {
            "history": history,
            "total": len(history),
            "user_id": user_id,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to get query history", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get query history: {str(e)}")


@router.post("/query/feedback")
async def submit_query_feedback(
    request: QueryFeedbackRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Submit feedback for a query"""
    
    try:
        ai_service = AIService()
        
        success = await ai_service.update_query_feedback(
            query_id=request.query_id,
            feedback_score=request.feedback_score,
            feedback_notes=request.feedback_notes,
            customer_id=customer_id
        )
        
        return {
            "success": success,
            "message": "Feedback submitted successfully" if success else "Failed to submit feedback"
        }
        
    except Exception as e:
        logger.error("Failed to submit feedback", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@router.post("/investigate")
async def start_investigation(
    request: InvestigationRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Start AI-powered investigation"""
    user_id = current_user.id
    
    try:
        ai_service = AIService()
        
        investigation = await ai_service.start_investigation(
            investigation_data={
                'title': request.title,
                'description': request.description,
                'incident_data': request.incident_data,
                'context': request.context
            },
            investigation_type='root_cause',
            started_by=user_id,
            customer_id=customer_id
        )
        
        return {
            "investigation_id": investigation.investigation_id,
            "title": investigation.title,
            "status": investigation.status,
            "hypothesis": investigation.hypothesis,
            "next_steps": investigation.next_steps,
            "started_at": investigation.started_at.isoformat(),
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to start investigation", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to start investigation: {str(e)}")


@router.get("/investigate/{investigation_id}")
async def get_investigation_status(
    investigation_id: str,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Get investigation status and results"""
    
    try:
        ai_service = AIService()
        
        investigation = await ai_service.get_investigation(investigation_id, customer_id)
        
        if not investigation:
            raise HTTPException(status_code=404, detail="Investigation not found")
        
        return {
            "investigation_id": investigation.investigation_id,
            "title": investigation.title,
            "description": investigation.description,
            "status": investigation.status,
            "results": investigation.results,
            "confidence_score": investigation.confidence_score,
            "started_at": investigation.started_at.isoformat(),
            "completed_at": investigation.completed_at.isoformat() if investigation.completed_at else None,
            "customer_id": customer_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get investigation", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get investigation: {str(e)}")


@router.post("/analyze")
async def analyze_incident(
    request: AnalysisRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Perform automated root cause analysis"""
    user_id = current_user.id
    
    try:
        ai_service = AIService()
        
        analysis = await ai_service.analyze_incident(
            incident=request.incident,
            context=request.context,
            started_by=user_id,
            customer_id=customer_id
        )
        
        return {
            "analysis_id": analysis.analysis_id,
            "incident_id": analysis.incident_id,
            "primary_cause": analysis.primary_cause,
            "contributing_factors": analysis.contributing_factors,
            "timeline": analysis.timeline,
            "business_impact": analysis.business_impact,
            "recommendations": analysis.recommendations,
            "similar_incidents": analysis.similar_incidents,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to analyze incident", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to analyze incident: {str(e)}")


@router.post("/baselines")
async def save_baseline(
    request: BaselineRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Save ML model baseline"""
    
    try:
        ai_service = AIService()
        
        model_id = await ai_service.save_baseline(
            model_id=request.model_id,
            service_name=request.service_name,
            baseline_type=request.baseline_type,
            baseline_data=request.baseline_data,
            training_metrics=request.training_metrics,
            customer_id=customer_id
        )
        
        return {
            "model_id": model_id,
            "status": "saved",
            "message": "Baseline saved successfully",
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to save baseline", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to save baseline: {str(e)}")


@router.get("/baselines")
async def list_baselines(
    service_name: Optional[str] = None,
    baseline_type: Optional[str] = None,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """List ML model baselines"""
    
    try:
        ai_service = AIService()
        
        baselines = await ai_service.get_baselines(customer_id, service_name, baseline_type)
        
        return {
            "baselines": baselines,
            "total": len(baselines),
            "filters": {
                "service_name": service_name,
                "baseline_type": baseline_type
            },
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to list baselines", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to list baselines: {str(e)}")


@router.post("/anomalies/detect")
async def detect_anomalies(
    request: AnomalyDetectionRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Detect anomalies using ML baselines"""
    
    try:
        ai_service = AIService()
        
        results = await ai_service.detect_anomalies(
            time_range=request.time_range,
            severity_list=request.severity_filter,
            category_list=request.category_filter,
            service_list=request.service_filter,
            customer_id=customer_id
        )
        
        return {
            "anomalies": results["anomalies"],
            "summary": results["summary"],
            "time_range": results["time_range"],
            "detection_timestamp": results["detection_timestamp"],
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to detect anomalies", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to detect anomalies: {str(e)}")


@router.post("/knowledge/search")
async def search_knowledge_base(
    request: KnowledgeSearchRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Search knowledge base for solutions"""
    
    try:
        ai_service = AIService()
        
        results = await ai_service.search_knowledge_base(
            symptoms=request.symptoms,
            services=request.services,
            category=request.category,
            customer_id=customer_id
        )
        
        return {
            "solutions": results["solutions"],
            "total_found": results["total_found"],
            "search_terms": results["search_terms"],
            "knowledge_base_stats": results["knowledge_base_stats"],
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to search knowledge base", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to search knowledge base: {str(e)}")


@router.post("/knowledge/solutions")
async def add_solution(
    request: SolutionRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Add solution to knowledge base"""
    
    try:
        ai_service = AIService()
        
        result = await ai_service.add_solution(
            solution_data={
                'incident_type': request.incident_type,
                'symptoms': request.symptoms,
                'solution': request.solution,
                'related_services': request.related_services
            },
            customer_id=customer_id
        )
        
        return {
            "solution_id": result["solution_id"],
            "status": result["status"],
            "message": result["message"],
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to add solution", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to add solution: {str(e)}")


@router.get("/insights")
async def get_operational_insights(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Get operational insights and recommendations"""
    
    try:
        ai_service = AIService()
        
        insights = await ai_service.get_operational_insights(customer_id)
        
        return {
            "insights": insights["insights"],
            "statistics": insights["statistics"],
            "recommendations": insights["recommendations"],
            "generated_at": insights["generated_at"],
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to get insights", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to get insights: {str(e)}")


@router.post("/correlate")
async def correlate_events(
    request: CorrelationRequest,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Find correlations between events and metrics"""
    
    try:
        ai_service = AIService()
        
        results = await ai_service.correlate_events(
            events=request.events,
            correlation_window=request.correlation_window,
            confidence_threshold=request.confidence_threshold,
            customer_id=customer_id
        )
        
        return {
            "correlations": results["correlations"],
            "total_events": results["total_events"],
            "correlation_window": results["correlation_window"],
            "confidence_threshold": results["confidence_threshold"],
            "analysis_timestamp": results["analysis_timestamp"],
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to correlate events", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to correlate events: {str(e)}")


@router.get("/health")
async def ai_health():
    """Health check for AI service"""
    try:
        ai_service = AIService()
        
        # Test database connectivity through service
        test_customer = "health-check-test"
        await ai_service.get_query_history("test-user", test_customer, limit=1)
        
        return {
            "status": "healthy",
            "message": "AI service operational",
            "features": [
                "natural_language_queries",
                "root_cause_analysis",
                "incident_investigations",
                "anomaly_detection",
                "knowledge_management",
                "operational_insights",
                "event_correlation",
                "ml_baselines"
            ]
        }
        
    except Exception as e:
        logger.error("AI health check failed", error=str(e))
        return {"status": "error", "message": f"Health check failed: {str(e)}"}


# Advanced AI endpoints
@router.post("/predict")
async def predict_incidents(
    time_horizon: str = "24h",
    confidence_threshold: float = 0.7,
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Predict potential incidents using ML models"""
    
    try:
        ai_service = AIService()
        
        predictions = await ai_service.predict_incidents(
            time_horizon=time_horizon,
            confidence_threshold=confidence_threshold,
            customer_id=customer_id
        )
        
        return {
            "predictions": predictions["predictions"],
            "time_horizon": time_horizon,
            "confidence_threshold": confidence_threshold,
            "total_predictions": predictions["total_predictions"],
            "generated_at": predictions["generated_at"],
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to predict incidents", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to predict incidents: {str(e)}")


@router.post("/optimize")
async def optimize_performance(
    service_name: str,
    optimization_type: str = "cost_performance",
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """Generate performance optimization recommendations"""
    
    try:
        ai_service = AIService()
        
        optimization_plan = await ai_service.generate_optimization_recommendations(
            service_name=service_name,
            optimization_type=optimization_type,
            customer_id=customer_id
        )
        
        return {
            "optimization_plan": optimization_plan,
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to generate optimization plan", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to generate optimization plan: {str(e)}")


@router.get("/models")
async def list_ai_models(
    customer_id: str = Header(..., alias="X-Customer-ID"),
    current_user = Depends(get_current_user)
):
    """List available AI models and their status"""
    
    try:
        ai_service = AIService()
        
        models_data = await ai_service.list_ai_models(customer_id)
        
        return {
            "models": models_data["models"],
            "total": models_data["total"],
            "active_models": models_data["active_models"],
            "customer_id": customer_id
        }
        
    except Exception as e:
        logger.error("Failed to list AI models", error=str(e), customer_id=customer_id)
        raise HTTPException(status_code=500, detail=f"Failed to list AI models: {str(e)}")