"""
Analytics models for visit tracking and metrics collection.

This module provides GDPR-compliant, privacy-first analytics models
for tracking paper website visits and academic engagement metrics.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, Dict, Any, List
from uuid import uuid4

from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, String, Integer, DateTime, Float, JSON, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

from .base import BaseModelMixin

Base = declarative_base()


class EventType(str, Enum):
    """Types of events that can be tracked."""
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


class DeviceType(str, Enum):
    """Device types for tracking."""
    DESKTOP = "desktop"
    MOBILE = "mobile"
    TABLET = "tablet"
    BOT = "bot"
    UNKNOWN = "unknown"


class TrafficSource(str, Enum):
    """Traffic source categories."""
    DIRECT = "direct"
    SEARCH_ENGINE = "search_engine"
    SOCIAL_MEDIA = "social_media"
    ACADEMIC_PLATFORM = "academic_platform"
    REFERRAL = "referral"
    EMAIL = "email"
    UNKNOWN = "unknown"


# Database Models
class AnalyticsSession(Base, BaseModelMixin):
    """
    Anonymous session tracking without personal data.
    Uses fingerprinting instead of cookies for privacy.
    """
    __tablename__ = "analytics_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    session_hash = Column(String, nullable=False, unique=True)  # Anonymous fingerprint
    first_visit = Column(DateTime, default=datetime.utcnow)
    last_activity = Column(DateTime, default=datetime.utcnow)
    page_views = Column(Integer, default=0)
    session_duration = Column(Integer, default=0)  # seconds
    
    # Geographic data (anonymized to city/region level)
    country_code = Column(String(2))
    region = Column(String(100))
    city = Column(String(100))
    timezone = Column(String(50))
    
    # Technical information
    device_type = Column(String, default=DeviceType.UNKNOWN)
    browser = Column(String(100))
    os = Column(String(100))
    screen_resolution = Column(String(20))
    
    # Traffic source
    traffic_source = Column(String, default=TrafficSource.UNKNOWN)
    referrer_domain = Column(String(255))
    referrer_url = Column(String(500))  # Truncated for privacy
    utm_source = Column(String(100))
    utm_medium = Column(String(100))
    utm_campaign = Column(String(100))
    
    # Privacy flags
    is_bot = Column(Boolean, default=False)
    do_not_track = Column(Boolean, default=False)
    
    # Relationships
    events = relationship("AnalyticsEvent", back_populates="session")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_session_project_date', 'project_id', 'first_visit'),
        Index('idx_session_hash', 'session_hash'),
        Index('idx_session_country', 'country_code'),
    )


class AnalyticsEvent(Base, BaseModelMixin):
    """
    Individual events tracked during sessions.
    Academic-focused event tracking.
    """
    __tablename__ = "analytics_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    session_id = Column(String, ForeignKey("analytics_sessions.id"), nullable=False)
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    
    event_type = Column(String, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Page/content information
    page_url = Column(String(500))
    page_title = Column(String(255))
    section_id = Column(String(100))  # For section tracking
    
    # Academic-specific data
    paper_section = Column(String(100))  # abstract, introduction, results, etc.
    figure_id = Column(String(100))
    citation_id = Column(String(100))
    reference_id = Column(String(100))
    download_type = Column(String(50))  # pdf, bibtex, supplementary
    
    # Event metadata
    event_data = Column(JSON)  # Flexible data for specific events
    duration = Column(Integer)  # Time spent on page/section (seconds)
    scroll_depth = Column(Float)  # Percentage of page scrolled
    
    # User interaction
    click_position_x = Column(Integer)
    click_position_y = Column(Integer)
    viewport_width = Column(Integer)
    viewport_height = Column(Integer)
    
    # Relationships
    session = relationship("AnalyticsSession", back_populates="events")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_event_project_date', 'project_id', 'timestamp'),
        Index('idx_event_type', 'event_type'),
        Index('idx_event_session', 'session_id'),
    )


class DailyMetrics(Base, BaseModelMixin):
    """
    Pre-aggregated daily metrics for performance.
    """
    __tablename__ = "daily_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    date = Column(DateTime, nullable=False)
    
    # Visit metrics
    unique_visitors = Column(Integer, default=0)
    total_page_views = Column(Integer, default=0)
    bounce_rate = Column(Float, default=0.0)
    avg_session_duration = Column(Float, default=0.0)
    
    # Academic metrics
    abstract_views = Column(Integer, default=0)
    pdf_downloads = Column(Integer, default=0)
    bibtex_downloads = Column(Integer, default=0)
    citation_clicks = Column(Integer, default=0)
    figure_views = Column(Integer, default=0)
    reference_clicks = Column(Integer, default=0)
    
    # Geographic distribution (top 10)
    top_countries = Column(JSON)  # {"US": 45, "UK": 23, ...}
    top_referrers = Column(JSON)  # {"google.com": 67, "scholar.google.com": 23, ...}
    
    # Device metrics
    desktop_percentage = Column(Float, default=0.0)
    mobile_percentage = Column(Float, default=0.0)
    tablet_percentage = Column(Float, default=0.0)
    
    # Traffic sources
    direct_traffic = Column(Integer, default=0)
    search_traffic = Column(Integer, default=0)
    referral_traffic = Column(Integer, default=0)
    social_traffic = Column(Integer, default=0)
    academic_traffic = Column(Integer, default=0)
    
    # Indexes
    __table_args__ = (
        Index('idx_daily_project_date', 'project_id', 'date'),
    )


class RealtimeMetrics(Base, BaseModelMixin):
    """
    Real-time metrics for live dashboard updates.
    """
    __tablename__ = "realtime_metrics"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    project_id = Column(String, ForeignKey("projects.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Current active users
    active_users_1min = Column(Integer, default=0)
    active_users_5min = Column(Integer, default=0)
    active_users_30min = Column(Integer, default=0)
    
    # Real-time events (last hour)
    page_views_1h = Column(Integer, default=0)
    pdf_downloads_1h = Column(Integer, default=0)
    unique_visitors_1h = Column(Integer, default=0)
    
    # Current popular content
    top_pages = Column(JSON)  # [{"url": "/abstract", "views": 15}, ...]
    recent_events = Column(JSON)  # Recent events for live feed
    
    # Indexes
    __table_args__ = (
        Index('idx_realtime_project', 'project_id'),
        Index('idx_realtime_timestamp', 'timestamp'),
    )


# Pydantic models for API
class SessionCreate(BaseModel):
    """Create a new analytics session."""
    project_id: str
    session_hash: str = Field(..., min_length=32, max_length=64)
    country_code: Optional[str] = Field(None, max_length=2)
    region: Optional[str] = Field(None, max_length=100)
    city: Optional[str] = Field(None, max_length=100)
    timezone: Optional[str] = Field(None, max_length=50)
    device_type: DeviceType = DeviceType.UNKNOWN
    browser: Optional[str] = Field(None, max_length=100)
    os: Optional[str] = Field(None, max_length=100)
    screen_resolution: Optional[str] = Field(None, max_length=20)
    traffic_source: TrafficSource = TrafficSource.UNKNOWN
    referrer_domain: Optional[str] = Field(None, max_length=255)
    referrer_url: Optional[str] = Field(None, max_length=500)
    utm_source: Optional[str] = Field(None, max_length=100)
    utm_medium: Optional[str] = Field(None, max_length=100)
    utm_campaign: Optional[str] = Field(None, max_length=100)
    is_bot: bool = False
    do_not_track: bool = False


class EventCreate(BaseModel):
    """Create a new analytics event."""
    session_id: str
    project_id: str
    event_type: EventType
    page_url: Optional[str] = Field(None, max_length=500)
    page_title: Optional[str] = Field(None, max_length=255)
    section_id: Optional[str] = Field(None, max_length=100)
    paper_section: Optional[str] = Field(None, max_length=100)
    figure_id: Optional[str] = Field(None, max_length=100)
    citation_id: Optional[str] = Field(None, max_length=100)
    reference_id: Optional[str] = Field(None, max_length=100)
    download_type: Optional[str] = Field(None, max_length=50)
    event_data: Optional[Dict[str, Any]] = None
    duration: Optional[int] = None
    scroll_depth: Optional[float] = Field(None, ge=0.0, le=1.0)
    click_position_x: Optional[int] = None
    click_position_y: Optional[int] = None
    viewport_width: Optional[int] = None
    viewport_height: Optional[int] = None


class DashboardMetrics(BaseModel):
    """Dashboard metrics response."""
    project_id: str
    date_range: Dict[str, datetime]
    
    # Overview metrics
    total_visitors: int
    total_page_views: int
    bounce_rate: float
    avg_session_duration: float
    
    # Academic metrics
    abstract_views: int
    pdf_downloads: int
    bibtex_downloads: int
    citation_clicks: int
    figure_views: int
    reference_clicks: int
    
    # Real-time metrics
    active_users: int
    users_last_hour: int
    
    # Geographic data
    top_countries: List[Dict[str, Any]]
    
    # Traffic sources
    traffic_sources: Dict[str, int]
    top_referrers: List[Dict[str, Any]]
    
    # Device breakdown
    device_breakdown: Dict[str, float]
    
    # Trending data
    daily_trends: List[Dict[str, Any]]
    popular_content: List[Dict[str, Any]]
    
    # Academic insights
    engagement_metrics: Dict[str, Any]
    download_trends: List[Dict[str, Any]]


class ExportData(BaseModel):
    """Data export response."""
    project_id: str
    export_type: str  # "csv", "json", "pdf"
    date_range: Dict[str, datetime]
    data: Dict[str, Any]
    generated_at: datetime
    expires_at: datetime


class RealtimeUpdate(BaseModel):
    """Real-time analytics update."""
    project_id: str
    timestamp: datetime
    active_users: int
    recent_events: List[Dict[str, Any]]
    live_page_views: Dict[str, int]
    current_downloads: int


class AnalyticsConfig(BaseModel):
    """Analytics configuration for a project."""
    project_id: str
    enabled: bool = True
    
    # Privacy settings
    anonymize_ips: bool = True
    respect_dnt: bool = True  # Respect Do Not Track
    cookie_free: bool = True
    
    # Data retention
    data_retention_days: int = Field(default=365, ge=30, le=2555)  # 30 days to 7 years
    
    # Tracking settings
    track_downloads: bool = True
    track_citations: bool = True
    track_figures: bool = True
    track_scroll_depth: bool = True
    track_click_positions: bool = False  # More privacy invasive
    
    # Real-time settings
    realtime_enabled: bool = True
    websocket_enabled: bool = True
    
    # Geographic tracking
    geographic_tracking: bool = True
    geographic_precision: str = Field(default="city")  # "country", "region", "city"
    
    # Academic platform integration
    google_scholar_tracking: bool = True
    arxiv_tracking: bool = True
    researchgate_tracking: bool = True
    
    @validator('geographic_precision')
    def validate_precision(cls, v):
        if v not in ['country', 'region', 'city']:
            raise ValueError('Geographic precision must be country, region, or city')
        return v


class AnalyticsReport(BaseModel):
    """Comprehensive analytics report."""
    project_id: str
    report_type: str  # "daily", "weekly", "monthly", "custom"
    date_range: Dict[str, datetime]
    generated_at: datetime
    
    # Executive summary
    summary: Dict[str, Any]
    
    # Detailed sections
    visitor_analytics: Dict[str, Any]
    academic_metrics: Dict[str, Any]
    geographic_analysis: Dict[str, Any]
    traffic_analysis: Dict[str, Any]
    content_performance: Dict[str, Any]
    technical_insights: Dict[str, Any]
    
    # Recommendations
    recommendations: List[str]
    
    # Charts data
    charts: Dict[str, Any]