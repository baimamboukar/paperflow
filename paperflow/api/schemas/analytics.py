"""
Analytics API schemas for Paperflow.

This module defines Pydantic schemas for analytics API requests and responses.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum

from pydantic import BaseModel, Field, validator
from .base import BaseResponse


class EventTypeSchema(str, Enum):
    """Event types for tracking."""
    PAGE_VIEW = "page_view"
    ABSTRACT_VIEW = "abstract_view"
    PDF_DOWNLOAD = "pdf_download"
    BIBTEX_DOWNLOAD = "bibtex_download"
    CITATION_CLICK = "citation_click"
    FIGURE_VIEW = "figure_view"
    REFERENCE_CLICK = "reference_click"
    PAPER_SHARE = "paper_share"
    SECTION_VIEW = "section_view"
    SEARCH_QUERY = "search_query"
    EXTERNAL_LINK = "external_link"


class DeviceTypeSchema(str, Enum):
    """Device types."""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    BOT = "bot"
    UNKNOWN = "unknown"


class TrafficSourceSchema(str, Enum):
    """Traffic source types."""
    DIRECT = "direct"
    SEARCH_ENGINE = "search_engine"
    SOCIAL_MEDIA = "social_media"
    ACADEMIC_PLATFORM = "academic_platform"
    REFERRAL = "referral"
    EMAIL = "email"
    UNKNOWN = "unknown"


class DateRangeSchema(str, Enum):
    """Date range types."""
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_YEAR = "this_year"
    ALL_TIME = "all_time"
    CUSTOM = "custom"


# Tracking Request Schemas
class TrackingRequest(BaseModel):
    """Base tracking request."""
    project_id: str = Field(..., description="Project identifier")
    session_hash: Optional[str] = Field(None, description="Session fingerprint hash")
    
    # Page information
    page_url: Optional[str] = Field(None, max_length=500, description="Current page URL")
    page_title: Optional[str] = Field(None, max_length=255, description="Page title")
    referrer: Optional[str] = Field(None, max_length=500, description="HTTP referrer")
    
    # User agent and device info
    user_agent: Optional[str] = Field(None, max_length=500, description="User agent string")
    screen_resolution: Optional[str] = Field(None, max_length=20, description="Screen resolution")
    viewport_width: Optional[int] = Field(None, ge=1, le=10000, description="Viewport width")
    viewport_height: Optional[int] = Field(None, ge=1, le=10000, description="Viewport height")
    
    # Geographic and language
    timezone_offset: Optional[int] = Field(None, ge=-720, le=720, description="Timezone offset in minutes")
    language: Optional[str] = Field(None, max_length=10, description="Browser language")
    
    # UTM parameters
    utm_source: Optional[str] = Field(None, max_length=100, description="UTM source")
    utm_medium: Optional[str] = Field(None, max_length=100, description="UTM medium")
    utm_campaign: Optional[str] = Field(None, max_length=100, description="UTM campaign")
    utm_term: Optional[str] = Field(None, max_length=100, description="UTM term")
    utm_content: Optional[str] = Field(None, max_length=100, description="UTM content")
    
    # Privacy flags
    do_not_track: bool = Field(default=False, description="Do not track preference")


class PageViewRequest(TrackingRequest):
    """Page view tracking request."""
    event_type: EventTypeSchema = Field(default=EventTypeSchema.PAGE_VIEW)
    
    # Page-specific data
    loading_time: Optional[int] = Field(None, ge=0, description="Page loading time in milliseconds")
    
    @validator('page_url')
    def validate_page_url(cls, v):
        if v and len(v) > 500:
            return v[:500]
        return v


class EventTrackingRequest(TrackingRequest):
    """Generic event tracking request."""
    event_type: EventTypeSchema = Field(..., description="Type of event to track")
    
    # Academic-specific fields
    section_id: Optional[str] = Field(None, max_length=100, description="Paper section ID")
    paper_section: Optional[str] = Field(None, max_length=100, description="Paper section name")
    figure_id: Optional[str] = Field(None, max_length=100, description="Figure identifier")
    citation_id: Optional[str] = Field(None, max_length=100, description="Citation identifier")
    reference_id: Optional[str] = Field(None, max_length=100, description="Reference identifier")
    download_type: Optional[str] = Field(None, max_length=50, description="Type of download")
    
    # Engagement metrics
    duration: Optional[int] = Field(None, ge=0, description="Time spent in seconds")
    scroll_depth: Optional[float] = Field(None, ge=0.0, le=1.0, description="Scroll depth percentage")
    
    # Click tracking
    click_x: Optional[int] = Field(None, ge=0, description="Click X coordinate")
    click_y: Optional[int] = Field(None, ge=0, description="Click Y coordinate")
    
    # Additional event data
    event_data: Optional[Dict[str, Any]] = Field(None, description="Additional event data")


class BulkEventsRequest(BaseModel):
    """Bulk event tracking request."""
    project_id: str = Field(..., description="Project identifier")
    events: List[EventTrackingRequest] = Field(..., min_items=1, max_items=100, description="List of events to track")


# Analytics Query Schemas
class AnalyticsQuery(BaseModel):
    """Base analytics query."""
    project_id: str = Field(..., description="Project identifier")
    date_range: DateRangeSchema = Field(default=DateRangeSchema.LAST_30_DAYS, description="Date range type")
    start_date: Optional[datetime] = Field(None, description="Custom start date")
    end_date: Optional[datetime] = Field(None, description="Custom end date")
    
    @validator('end_date')
    def validate_date_range(cls, v, values):
        if values.get('date_range') == DateRangeSchema.CUSTOM:
            if not values.get('start_date') or not v:
                raise ValueError("Custom date range requires both start_date and end_date")
            if values.get('start_date') >= v:
                raise ValueError("start_date must be before end_date")
        return v


class DashboardQuery(AnalyticsQuery):
    """Dashboard data query."""
    include_realtime: bool = Field(default=True, description="Include real-time metrics")
    include_trends: bool = Field(default=True, description="Include trending data")


class MetricsQuery(AnalyticsQuery):
    """Detailed metrics query."""
    metrics: List[str] = Field(default_factory=list, description="Specific metrics to include")
    granularity: str = Field(default="daily", description="Data granularity")
    
    @validator('granularity')
    def validate_granularity(cls, v):
        if v not in ['hourly', 'daily', 'weekly', 'monthly']:
            raise ValueError("Granularity must be one of: hourly, daily, weekly, monthly")
        return v


class ExportQuery(AnalyticsQuery):
    """Data export query."""
    export_format: str = Field(default="json", description="Export format")
    include_raw_data: bool = Field(default=False, description="Include raw event data")
    
    @validator('export_format')
    def validate_export_format(cls, v):
        if v not in ['json', 'csv', 'pdf']:
            raise ValueError("Export format must be one of: json, csv, pdf")
        return v


# Response Schemas
class TrackingResponse(BaseResponse):
    """Tracking response."""
    success: bool = Field(..., description="Whether tracking was successful")
    session_id: Optional[str] = Field(None, description="Session identifier")
    event_id: Optional[str] = Field(None, description="Event identifier")
    warnings: List[str] = Field(default_factory=list, description="Any warnings")


class OverviewMetrics(BaseModel):
    """Overview metrics."""
    unique_visitors: int = Field(..., description="Number of unique visitors")
    total_sessions: int = Field(..., description="Total number of sessions")
    total_page_views: int = Field(..., description="Total page views")
    bounce_rate: float = Field(..., description="Bounce rate percentage")
    avg_session_duration: float = Field(..., description="Average session duration in seconds")
    pages_per_session: float = Field(..., description="Average pages per session")


class AcademicMetrics(BaseModel):
    """Academic-specific metrics."""
    abstract_views: int = Field(..., description="Number of abstract views")
    pdf_downloads: int = Field(..., description="Number of PDF downloads")
    bibtex_downloads: int = Field(..., description="Number of BibTeX downloads")
    citation_clicks: int = Field(..., description="Number of citation clicks")
    figure_views: int = Field(..., description="Number of figure views")
    reference_clicks: int = Field(..., description="Number of reference clicks")
    paper_shares: int = Field(..., description="Number of paper shares")
    
    # Conversion rates
    abstract_to_pdf_rate: float = Field(..., description="Abstract to PDF conversion rate")
    visitor_to_pdf_rate: float = Field(..., description="Visitor to PDF conversion rate")
    pdf_to_citation_rate: float = Field(..., description="PDF to citation conversion rate")


class RealtimeMetrics(BaseModel):
    """Real-time metrics."""
    active_users: int = Field(..., description="Currently active users")
    users_last_hour: int = Field(..., description="Users in the last hour")
    page_views_last_hour: int = Field(..., description="Page views in the last hour")
    downloads_last_hour: int = Field(..., description="Downloads in the last hour")


class GeographicData(BaseModel):
    """Geographic distribution data."""
    country_code: str = Field(..., description="Country code")
    country_name: Optional[str] = Field(None, description="Country name")
    visitors: int = Field(..., description="Number of visitors")
    percentage: float = Field(..., description="Percentage of total visitors")
    page_views: int = Field(..., description="Total page views")
    avg_duration: float = Field(..., description="Average session duration")


class TrafficSource(BaseModel):
    """Traffic source data."""
    source: str = Field(..., description="Traffic source name")
    visitors: int = Field(..., description="Number of visitors")
    percentage: float = Field(..., description="Percentage of total visitors")
    page_views: int = Field(..., description="Total page views")
    avg_duration: float = Field(..., description="Average session duration")
    quality_score: float = Field(..., description="Traffic quality score")


class TrendData(BaseModel):
    """Trend data point."""
    date: str = Field(..., description="Date in ISO format")
    visitors: int = Field(..., description="Number of visitors")
    page_views: int = Field(..., description="Number of page views")
    downloads: int = Field(..., description="Number of downloads")
    bounce_rate: float = Field(..., description="Bounce rate")


class PopularContent(BaseModel):
    """Popular content data."""
    url: str = Field(..., description="Page URL")
    title: str = Field(..., description="Page title")
    views: int = Field(..., description="Number of views")
    unique_visitors: int = Field(..., description="Number of unique visitors")
    avg_time: float = Field(..., description="Average time on page")


class EngagementMetrics(BaseModel):
    """User engagement metrics."""
    avg_scroll_depth: float = Field(..., description="Average scroll depth")
    avg_time_on_page: float = Field(..., description="Average time on page")
    interaction_rate: float = Field(..., description="Interaction rate")
    exit_rate: float = Field(..., description="Exit rate")


class DashboardResponse(BaseResponse):
    """Dashboard data response."""
    project_id: str = Field(..., description="Project identifier")
    date_range: Dict[str, Any] = Field(..., description="Date range information")
    
    # Core metrics
    overview: OverviewMetrics = Field(..., description="Overview metrics")
    academic: AcademicMetrics = Field(..., description="Academic metrics")
    realtime: RealtimeMetrics = Field(..., description="Real-time metrics")
    
    # Breakdown data
    geographic: List[GeographicData] = Field(..., description="Geographic distribution")
    traffic_sources: List[TrafficSource] = Field(..., description="Traffic sources")
    device_breakdown: Dict[str, float] = Field(..., description="Device type breakdown")
    
    # Trends and content
    trends: List[TrendData] = Field(..., description="Daily trends")
    popular_content: List[PopularContent] = Field(..., description="Popular content")
    engagement: EngagementMetrics = Field(..., description="Engagement metrics")


class RealtimeResponse(BaseResponse):
    """Real-time dashboard response."""
    project_id: str = Field(..., description="Project identifier")
    timestamp: datetime = Field(..., description="Current timestamp")
    active_users: int = Field(..., description="Currently active users")
    recent_events: List[Dict[str, Any]] = Field(..., description="Recent events")
    live_page_views: Dict[str, int] = Field(..., description="Current page views")
    current_downloads: int = Field(..., description="Current downloads")


class MetricsResponse(BaseResponse):
    """Detailed metrics response."""
    project_id: str = Field(..., description="Project identifier")
    date_range: Dict[str, Any] = Field(..., description="Date range information")
    granularity: str = Field(..., description="Data granularity")
    
    # Detailed metrics
    visitor_analytics: Dict[str, Any] = Field(..., description="Visitor analytics")
    academic_metrics: Dict[str, Any] = Field(..., description="Academic metrics")
    geographic_analysis: Dict[str, Any] = Field(..., description="Geographic analysis")
    traffic_analysis: Dict[str, Any] = Field(..., description="Traffic analysis")
    engagement_analysis: Dict[str, Any] = Field(..., description="Engagement analysis")
    
    # Time series data
    time_series: List[Dict[str, Any]] = Field(..., description="Time series data")


class ExportResponse(BaseResponse):
    """Data export response."""
    project_id: str = Field(..., description="Project identifier")
    export_format: str = Field(..., description="Export format")
    download_url: str = Field(..., description="Download URL")
    expires_at: datetime = Field(..., description="URL expiration time")
    file_size: int = Field(..., description="File size in bytes")


class ReportResponse(BaseResponse):
    """Analytics report response."""
    project_id: str = Field(..., description="Project identifier")
    report_type: str = Field(..., description="Report type")
    generated_at: datetime = Field(..., description="Generation timestamp")
    
    # Report sections
    executive_summary: Dict[str, Any] = Field(..., description="Executive summary")
    detailed_analysis: Dict[str, Any] = Field(..., description="Detailed analysis")
    recommendations: List[str] = Field(..., description="Recommendations")
    
    # Download links
    pdf_url: Optional[str] = Field(None, description="PDF report URL")
    excel_url: Optional[str] = Field(None, description="Excel report URL")


class ConfigResponse(BaseResponse):
    """Analytics configuration response."""
    project_id: str = Field(..., description="Project identifier")
    tracking_enabled: bool = Field(..., description="Whether tracking is enabled")
    privacy_settings: Dict[str, Any] = Field(..., description="Privacy settings")
    retention_settings: Dict[str, Any] = Field(..., description="Data retention settings")
    tracking_script_url: str = Field(..., description="Tracking script URL")


class HealthResponse(BaseResponse):
    """Analytics health check response."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Service version")
    uptime: int = Field(..., description="Uptime in seconds")
    
    # Service metrics
    total_projects: int = Field(..., description="Total projects")
    total_sessions: int = Field(..., description="Total sessions")
    total_events: int = Field(..., description="Total events")
    events_last_hour: int = Field(..., description="Events in last hour")
    
    # Performance metrics
    avg_response_time: float = Field(..., description="Average response time")
    error_rate: float = Field(..., description="Error rate percentage")


# WebSocket Schemas
class WebSocketMessage(BaseModel):
    """WebSocket message schema."""
    type: str = Field(..., description="Message type")
    project_id: str = Field(..., description="Project identifier")
    data: Dict[str, Any] = Field(..., description="Message data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Message timestamp")


class RealtimeUpdate(WebSocketMessage):
    """Real-time analytics update."""
    type: str = Field(default="realtime_update", description="Message type")
    
    class Data(BaseModel):
        active_users: int
        recent_events: List[Dict[str, Any]]
        live_metrics: Dict[str, Any]
    
    data: Data = Field(..., description="Real-time data")


# Error Schemas
class AnalyticsError(BaseModel):
    """Analytics error response."""
    error_code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")


class ValidationError(AnalyticsError):
    """Validation error response."""
    error_code: str = Field(default="VALIDATION_ERROR", description="Error code")
    field_errors: Dict[str, List[str]] = Field(..., description="Field-specific errors")


class RateLimitError(AnalyticsError):
    """Rate limit error response."""
    error_code: str = Field(default="RATE_LIMIT_EXCEEDED", description="Error code")
    retry_after: int = Field(..., description="Retry after seconds")
    limit: int = Field(..., description="Rate limit")
    window: int = Field(..., description="Rate limit window in seconds")