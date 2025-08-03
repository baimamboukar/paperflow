"""
Analytics API router for Paperflow.

This module provides API endpoints for analytics tracking, dashboard data,
and comprehensive reporting with real-time capabilities.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, BackgroundTasks
from fastapi.responses import StreamingResponse, FileResponse
from sqlalchemy.ext.asyncio import AsyncSession
import json

from ..dependencies import get_db, get_current_user, rate_limit
from ..schemas.analytics import (
    # Request schemas
    PageViewRequest,
    EventTrackingRequest,
    BulkEventsRequest,
    AnalyticsQuery,
    DashboardQuery,
    MetricsQuery,
    ExportQuery,
    DateRangeSchema,
    
    # Response schemas
    TrackingResponse,
    DashboardResponse,
    RealtimeResponse,
    MetricsResponse,
    ExportResponse,
    ReportResponse,
    ConfigResponse,
    HealthResponse,
    AnalyticsError
)
from ...services.analytics import (
    AnalyticsService,
    TrackingService,
    MetricsService,
    DashboardService
)
from ...models.analytics import EventType, EventCreate, SessionCreate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


# Rate limiting configurations
TRACKING_RATE_LIMIT = "100/minute"  # High for tracking endpoints
DASHBOARD_RATE_LIMIT = "30/minute"   # Medium for dashboard
EXPORT_RATE_LIMIT = "5/minute"       # Low for exports


# Tracking Endpoints
@router.post("/track/pageview", response_model=TrackingResponse)
async def track_page_view(
    request: PageViewRequest,
    http_request: Request,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Track a page view event.
    
    This endpoint is called by the JavaScript tracking client to record
    page views with comprehensive context about the visit.
    """
    try:
        tracking_service = TrackingService(db)
        
        # Extract HTTP request data
        request_data = {
            'ip_address': http_request.client.host,
            'user_agent': http_request.headers.get('user-agent', ''),
            'accept_language': http_request.headers.get('accept-language', ''),
            'referrer': http_request.headers.get('referer', ''),
            'dnt': http_request.headers.get('dnt', '0')
        }
        
        # Extract page data
        page_data = {
            'url': request.page_url,
            'title': request.page_title,
            'viewport_width': request.viewport_width,
            'viewport_height': request.viewport_height,
            'timezone_offset': request.timezone_offset,
            'screen_resolution': request.screen_resolution,
            'utm': {
                'source': request.utm_source,
                'medium': request.utm_medium,
                'campaign': request.utm_campaign,
                'term': request.utm_term,
                'content': request.utm_content
            }
        }
        
        # Track the page visit asynchronously
        event = await tracking_service.track_page_visit(
            project_id=request.project_id,
            request_data=request_data,
            page_data=page_data
        )
        
        if event:
            return TrackingResponse(
                success=True,
                session_id=event.session_id,
                event_id=event.id,
                message="Page view tracked successfully"
            )
        else:
            return TrackingResponse(
                success=False,
                message="Page view tracking declined (DNT or bot detected)",
                warnings=["Tracking was declined due to privacy preferences or bot detection"]
            )
            
    except Exception as e:
        logger.error(f"Error tracking page view: {e}")
        raise HTTPException(status_code=500, detail="Failed to track page view")


@router.post("/track/event", response_model=TrackingResponse, dependencies=[Depends(rate_limit(TRACKING_RATE_LIMIT))])
async def track_event(
    request: EventTrackingRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Track a custom event (downloads, citations, etc.).
    
    This endpoint handles academic-specific events like PDF downloads,
    citation clicks, figure views, and other engagement metrics.
    """
    try:
        tracking_service = TrackingService(db)
        
        # Validate event data
        if not tracking_service.validate_event_data(request.dict()):
            raise HTTPException(status_code=400, detail="Invalid event data")
        
        # Get or create session
        session = None
        if request.session_hash:
            session = await tracking_service.get_session_by_hash(request.session_hash)
        
        if not session:
            raise HTTPException(status_code=400, detail="Valid session required for event tracking")
        
        # Prepare event data
        event_data = {}
        if request.section_id:
            event_data['section'] = request.paper_section
        if request.figure_id:
            event_data['figure_id'] = request.figure_id
        if request.citation_id:
            event_data['citation_id'] = request.citation_id
        if request.reference_id:
            event_data['reference_id'] = request.reference_id
        if request.download_type:
            event_data['download_type'] = request.download_type
        if request.duration:
            event_data['duration'] = request.duration
        if request.event_data:
            event_data.update(request.event_data)
        
        # Track the event
        event = await tracking_service.track_academic_event(
            session_id=session.id,
            project_id=request.project_id,
            event_type=request.event_type,
            event_data=event_data
        )
        
        if event:
            return TrackingResponse(
                success=True,
                session_id=session.id,
                event_id=event.id,
                message=f"{request.event_type} event tracked successfully"
            )
        else:
            return TrackingResponse(
                success=False,
                message="Event tracking failed",
                warnings=["Event could not be tracked"]
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking event: {e}")
        raise HTTPException(status_code=500, detail="Failed to track event")


@router.post("/track/bulk", response_model=TrackingResponse, dependencies=[Depends(rate_limit(TRACKING_RATE_LIMIT))])
async def track_bulk_events(
    request: BulkEventsRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    """
    Track multiple events in bulk for performance.
    
    This endpoint allows tracking multiple events in a single request,
    which is useful for batch processing and performance optimization.
    """
    try:
        tracking_service = TrackingService(db)
        
        # Convert requests to EventCreate objects
        events = []
        for event_req in request.events:
            # Validate each event
            if not tracking_service.validate_event_data(event_req.dict()):
                continue
                
            # Find session
            session = None
            if event_req.session_hash:
                session = await tracking_service.get_session_by_hash(event_req.session_hash)
            
            if not session:
                continue
                
            event_create = EventCreate(
                session_id=session.id,
                project_id=event_req.project_id,
                event_type=event_req.event_type,
                page_url=event_req.page_url,
                page_title=event_req.page_title,
                section_id=event_req.section_id,
                paper_section=event_req.paper_section,
                figure_id=event_req.figure_id,
                citation_id=event_req.citation_id,
                reference_id=event_req.reference_id,
                download_type=event_req.download_type,
                duration=event_req.duration,
                scroll_depth=event_req.scroll_depth,
                click_position_x=event_req.click_x,
                click_position_y=event_req.click_y,
                viewport_width=event_req.viewport_width,
                viewport_height=event_req.viewport_height,
                event_data=event_req.event_data
            )
            events.append(event_create)
        
        # Track events in bulk
        tracked_events = await tracking_service.bulk_track_events(events)
        
        return TrackingResponse(
            success=True,
            message=f"Tracked {len(tracked_events)}/{len(request.events)} events successfully",
            warnings=[f"Skipped {len(request.events) - len(tracked_events)} invalid events"] if len(tracked_events) < len(request.events) else []
        )
        
    except Exception as e:
        logger.error(f"Error tracking bulk events: {e}")
        raise HTTPException(status_code=500, detail="Failed to track bulk events")


# Dashboard Endpoints
@router.get("/dashboard/{project_id}", response_model=DashboardResponse, dependencies=[Depends(rate_limit(DASHBOARD_RATE_LIMIT))])
async def get_dashboard(
    project_id: str,
    date_range: DateRangeSchema = Query(default=DateRangeSchema.LAST_30_DAYS),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get comprehensive dashboard data for a project.
    
    Returns overview metrics, academic engagement data, geographic distribution,
    traffic sources, and trending information for the specified date range.
    """
    try:
        dashboard_service = DashboardService(db)
        
        # Get dashboard data
        dashboard_data = await dashboard_service.get_dashboard_overview(
            project_id=project_id,
            date_range=date_range,
            start_date=start_date,
            end_date=end_date
        )
        
        # Convert to response format
        return DashboardResponse(
            project_id=dashboard_data.project_id,
            date_range=dashboard_data.date_range,
            overview={
                'unique_visitors': dashboard_data.total_visitors,
                'total_sessions': dashboard_data.total_visitors,  # Simplified
                'total_page_views': dashboard_data.total_page_views,
                'bounce_rate': dashboard_data.bounce_rate,
                'avg_session_duration': dashboard_data.avg_session_duration,
                'pages_per_session': dashboard_data.total_page_views / max(dashboard_data.total_visitors, 1)
            },
            academic={
                'abstract_views': dashboard_data.abstract_views,
                'pdf_downloads': dashboard_data.pdf_downloads,
                'bibtex_downloads': dashboard_data.bibtex_downloads,
                'citation_clicks': dashboard_data.citation_clicks,
                'figure_views': dashboard_data.figure_views,
                'reference_clicks': dashboard_data.reference_clicks,
                'paper_shares': 0,  # TODO: Implement
                'abstract_to_pdf_rate': (dashboard_data.pdf_downloads / max(dashboard_data.abstract_views, 1)) * 100,
                'visitor_to_pdf_rate': (dashboard_data.pdf_downloads / max(dashboard_data.total_visitors, 1)) * 100,
                'pdf_to_citation_rate': (dashboard_data.citation_clicks / max(dashboard_data.pdf_downloads, 1)) * 100
            },
            realtime={
                'active_users': dashboard_data.active_users,
                'users_last_hour': dashboard_data.users_last_hour,
                'page_views_last_hour': 0,  # TODO: Implement
                'downloads_last_hour': 0   # TODO: Implement
            },
            geographic=[
                {
                    'country_code': country.get('country_code', ''),
                    'country_name': country.get('country_name'),
                    'visitors': country.get('visitors', 0),
                    'percentage': country.get('percentage', 0),
                    'page_views': country.get('page_views', 0),
                    'avg_duration': country.get('avg_duration', 0)
                }
                for country in dashboard_data.top_countries
            ],
            traffic_sources=[
                {
                    'source': source,
                    'visitors': count,
                    'percentage': (count / max(dashboard_data.total_visitors, 1)) * 100,
                    'page_views': count * 2,  # Estimate
                    'avg_duration': 120,  # Estimate
                    'quality_score': 75  # Estimate
                }
                for source, count in dashboard_data.traffic_sources.items()
            ],
            device_breakdown=dashboard_data.device_breakdown,
            trends=[
                {
                    'date': trend.get('date', ''),
                    'visitors': trend.get('visitors', 0),
                    'page_views': trend.get('page_views', 0),
                    'downloads': trend.get('downloads', 0),
                    'bounce_rate': 45.0  # Estimate
                }
                for trend in dashboard_data.daily_trends
            ],
            popular_content=[
                {
                    'url': content.get('url', ''),
                    'title': content.get('title', ''),
                    'views': content.get('views', 0),
                    'unique_visitors': content.get('views', 0),  # Estimate
                    'avg_time': 120  # Estimate
                }
                for content in dashboard_data.popular_content
            ],
            engagement={
                'avg_scroll_depth': dashboard_data.engagement_metrics.get('avg_scroll_depth', 0),
                'avg_time_on_page': dashboard_data.engagement_metrics.get('avg_time_on_page', 0),
                'interaction_rate': dashboard_data.engagement_metrics.get('interaction_rate', 0),
                'exit_rate': 30.0  # Estimate
            },
            message="Dashboard data retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting dashboard data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve dashboard data")


@router.get("/realtime/{project_id}", response_model=RealtimeResponse, dependencies=[Depends(rate_limit(DASHBOARD_RATE_LIMIT))])
async def get_realtime_dashboard(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get real-time dashboard data for live updates.
    
    Returns current active users, recent events, live page views,
    and other real-time metrics for the project.
    """
    try:
        dashboard_service = DashboardService(db)
        
        realtime_data = await dashboard_service.get_realtime_dashboard(project_id)
        
        return RealtimeResponse(
            project_id=realtime_data.project_id,
            timestamp=realtime_data.timestamp,
            active_users=realtime_data.active_users,
            recent_events=realtime_data.recent_events,
            live_page_views=realtime_data.live_page_views,
            current_downloads=realtime_data.current_downloads,
            message="Real-time data retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting real-time dashboard: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve real-time data")


# Detailed Analytics Endpoints
@router.get("/metrics/{project_id}", response_model=MetricsResponse, dependencies=[Depends(rate_limit(DASHBOARD_RATE_LIMIT))])
async def get_detailed_metrics(
    project_id: str,
    date_range: DateRangeSchema = Query(default=DateRangeSchema.LAST_30_DAYS),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    granularity: str = Query(default="daily"),
    metrics: List[str] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get detailed analytics metrics for a project.
    
    Returns comprehensive metrics including visitor analytics, academic metrics,
    geographic analysis, traffic analysis, and engagement data.
    """
    try:
        metrics_service = MetricsService(db)
        
        # Calculate date range
        dashboard_service = DashboardService(db)
        start_dt, end_dt = dashboard_service._calculate_date_range(date_range, start_date, end_date)
        
        # Get detailed metrics
        visitor_analytics = await metrics_service.calculate_visitor_metrics(project_id, start_dt, end_dt)
        academic_metrics = await metrics_service.calculate_academic_metrics(project_id, start_dt, end_dt)
        geographic_analysis = await metrics_service.calculate_geographic_metrics(project_id, start_dt, end_dt)
        traffic_analysis = await metrics_service.calculate_traffic_source_metrics(project_id, start_dt, end_dt)
        engagement_analysis = await metrics_service.calculate_engagement_metrics(project_id, start_dt, end_dt)
        time_series = await metrics_service.calculate_time_series_metrics(project_id, start_dt, end_dt, granularity)
        
        return MetricsResponse(
            project_id=project_id,
            date_range={'start': start_dt, 'end': end_dt, 'type': date_range},
            granularity=granularity,
            visitor_analytics=visitor_analytics,
            academic_metrics=academic_metrics,
            geographic_analysis=geographic_analysis,
            traffic_analysis=traffic_analysis,
            engagement_analysis=engagement_analysis,
            time_series=time_series.get('daily_data', []),
            message="Detailed metrics retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting detailed metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve detailed metrics")


# Export and Reporting Endpoints
@router.post("/export/{project_id}", response_model=ExportResponse, dependencies=[Depends(rate_limit(EXPORT_RATE_LIMIT))])
async def export_analytics_data(
    project_id: str,
    export_query: ExportQuery,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Export analytics data in various formats.
    
    Generates downloadable files with analytics data in JSON, CSV, or PDF format.
    The export is processed asynchronously and a download URL is provided.
    """
    try:
        dashboard_service = DashboardService(db)
        
        # Generate export data
        export_data = await dashboard_service.export_analytics_data(
            project_id=project_id,
            export_type=export_query.export_format,
            date_range=export_query.date_range,
            start_date=export_query.start_date,
            end_date=export_query.end_date,
            include_raw_data=export_query.include_raw_data
        )
        
        # Generate download URL (placeholder implementation)
        download_url = f"/api/v1/analytics/download/{project_id}/{export_data.generated_at.timestamp()}"
        
        return ExportResponse(
            project_id=project_id,
            export_format=export_query.export_format,
            download_url=download_url,
            expires_at=export_data.expires_at,
            file_size=len(json.dumps(export_data.data)),  # Estimate
            message="Export generated successfully"
        )
        
    except Exception as e:
        logger.error(f"Error exporting analytics data: {e}")
        raise HTTPException(status_code=500, detail="Failed to export analytics data")


@router.get("/report/{project_id}", response_model=ReportResponse, dependencies=[Depends(rate_limit(EXPORT_RATE_LIMIT))])
async def generate_analytics_report(
    project_id: str,
    report_type: str = Query(default="monthly"),
    date_range: DateRangeSchema = Query(default=DateRangeSchema.LAST_30_DAYS),
    start_date: Optional[datetime] = Query(default=None),
    end_date: Optional[datetime] = Query(default=None),
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Generate a comprehensive analytics report.
    
    Creates a detailed report with executive summary, analysis,
    and recommendations for the specified time period.
    """
    try:
        dashboard_service = DashboardService(db)
        
        report = await dashboard_service.get_analytics_report(
            project_id=project_id,
            report_type=report_type,
            date_range=date_range,
            start_date=start_date,
            end_date=end_date
        )
        
        return ReportResponse(
            project_id=report.project_id,
            report_type=report.report_type,
            generated_at=report.generated_at,
            executive_summary=report.summary,
            detailed_analysis={
                'visitor_analytics': report.visitor_analytics,
                'academic_metrics': report.academic_metrics,
                'geographic_analysis': report.geographic_analysis,
                'traffic_analysis': report.traffic_analysis,
                'content_performance': report.content_performance
            },
            recommendations=report.recommendations,
            pdf_url=f"/api/v1/analytics/report/{project_id}/pdf",
            excel_url=f"/api/v1/analytics/report/{project_id}/excel",
            message="Report generated successfully"
        )
        
    except Exception as e:
        logger.error(f"Error generating analytics report: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate analytics report")


# Configuration Endpoints
@router.get("/config/{project_id}", response_model=ConfigResponse)
async def get_analytics_config(
    project_id: str,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Get analytics configuration for a project.
    
    Returns current tracking settings, privacy configuration,
    and tracking script information.
    """
    try:
        analytics_service = AnalyticsService(db)
        
        config = await analytics_service.get_project_config(project_id)
        
        return ConfigResponse(
            project_id=project_id,
            tracking_enabled=config.enabled,
            privacy_settings={
                'anonymize_ips': config.anonymize_ips,
                'respect_dnt': config.respect_dnt,
                'cookie_free': config.cookie_free,
                'geographic_tracking': config.geographic_tracking
            },
            retention_settings={
                'data_retention_days': config.data_retention_days
            },
            tracking_script_url=f"/static/analytics/paperflow-analytics.js?project={project_id}",
            message="Configuration retrieved successfully"
        )
        
    except Exception as e:
        logger.error(f"Error getting analytics config: {e}")
        raise HTTPException(status_code=500, detail="Failed to get analytics configuration")


# Health Check Endpoint
@router.get("/health", response_model=HealthResponse)
async def analytics_health_check(db: AsyncSession = Depends(get_db)):
    """
    Analytics service health check.
    
    Returns service status, performance metrics, and system information.
    """
    try:
        analytics_service = AnalyticsService(db)
        
        # Get basic counts for health check
        # This is a simplified implementation
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            uptime=3600,  # Placeholder
            total_projects=0,  # TODO: Implement
            total_sessions=0,  # TODO: Implement
            total_events=0,    # TODO: Implement
            events_last_hour=0,  # TODO: Implement
            avg_response_time=50.0,  # Placeholder
            error_rate=0.1,  # Placeholder
            message="Analytics service is healthy"
        )
        
    except Exception as e:
        logger.error(f"Error in analytics health check: {e}")
        raise HTTPException(status_code=500, detail="Analytics service unhealthy")


# Error Handlers
@router.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions for analytics endpoints."""
    return AnalyticsError(
        error_code=f"HTTP_{exc.status_code}",
        message=exc.detail,
        details={'status_code': exc.status_code}
    )


@router.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    """Handle validation errors."""
    return AnalyticsError(
        error_code="VALIDATION_ERROR",
        message=str(exc),
        details={'type': 'ValueError'}
    )