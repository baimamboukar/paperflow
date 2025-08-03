"""
Dashboard service for Paperflow analytics.

This service generates dashboard data and provides comprehensive analytics
views for researchers to understand their paper's reach and impact.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc

from ...models.analytics import (
    AnalyticsSession,
    AnalyticsEvent,
    DailyMetrics,
    RealtimeMetrics,
    DashboardMetrics,
    AnalyticsReport,
    ExportData,
    RealtimeUpdate,
    EventType,
    TrafficSource
)
from .analytics_service import AnalyticsService
from .tracking_service import TrackingService
from .metrics_service import MetricsService
from ..base import BaseService

logger = logging.getLogger(__name__)


class DateRangeType(str, Enum):
    """Predefined date range types."""
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


class DashboardService(BaseService):
    """
    Comprehensive dashboard service for analytics visualization.
    
    Features:
    - Real-time dashboard data
    - Academic-focused metrics
    - Interactive visualizations
    - Performance insights
    - Export capabilities
    - Automated reporting
    """

    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session)
        self.analytics_service = AnalyticsService(db_session)
        self.tracking_service = TrackingService(db_session)
        self.metrics_service = MetricsService(db_session)

    async def get_dashboard_overview(
        self,
        project_id: str,
        date_range: DateRangeType = DateRangeType.LAST_30_DAYS,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> DashboardMetrics:
        """
        Get comprehensive dashboard overview for a project.
        
        Args:
            project_id: Project identifier
            date_range: Predefined date range type
            start_date: Custom start date (for CUSTOM range)
            end_date: Custom end date (for CUSTOM range)
            
        Returns:
            Dashboard metrics object
        """
        try:
            # Calculate date range
            start_dt, end_dt = self._calculate_date_range(date_range, start_date, end_date)
            
            # Get all metrics in parallel for performance
            tasks = [
                self._get_overview_metrics(project_id, start_dt, end_dt),
                self._get_academic_metrics(project_id, start_dt, end_dt),
                self._get_realtime_metrics(project_id),
                self._get_geographic_data(project_id, start_dt, end_dt),
                self._get_traffic_sources(project_id, start_dt, end_dt),
                self._get_device_breakdown(project_id, start_dt, end_dt),
                self._get_trending_data(project_id, start_dt, end_dt),
                self._get_popular_content(project_id, start_dt, end_dt),
                self._get_engagement_metrics(project_id, start_dt, end_dt),
                self._get_download_trends(project_id, start_dt, end_dt)
            ]
            
            results = await asyncio.gather(*tasks)
            
            (overview_metrics, academic_metrics, realtime_metrics, 
             geographic_data, traffic_sources, device_breakdown,
             trending_data, popular_content, engagement_metrics, download_trends) = results

            # Compile dashboard metrics
            dashboard = DashboardMetrics(
                project_id=project_id,
                date_range={
                    'start': start_dt,
                    'end': end_dt,
                    'type': date_range
                },
                **overview_metrics,
                **academic_metrics,
                **realtime_metrics,
                top_countries=geographic_data['countries'],
                traffic_sources=traffic_sources['sources'],
                top_referrers=traffic_sources['referrers'],
                device_breakdown=device_breakdown,
                daily_trends=trending_data,
                popular_content=popular_content,
                engagement_metrics=engagement_metrics,
                download_trends=download_trends
            )
            
            logger.info(f"Generated dashboard overview for project {project_id}")
            return dashboard

        except Exception as e:
            logger.error(f"Error generating dashboard overview: {e}")
            raise

    async def get_realtime_dashboard(self, project_id: str) -> RealtimeUpdate:
        """
        Get real-time dashboard data for live updates.
        
        Args:
            project_id: Project identifier
            
        Returns:
            Real-time update object
        """
        try:
            # Get latest real-time metrics
            result = await self.db.execute(
                select(RealtimeMetrics)
                .where(RealtimeMetrics.project_id == project_id)
                .order_by(desc(RealtimeMetrics.timestamp))
                .limit(1)
            )
            realtime = result.scalar_one_or_none()
            
            if not realtime:
                # Create empty real-time data
                return RealtimeUpdate(
                    project_id=project_id,
                    timestamp=datetime.utcnow(),
                    active_users=0,
                    recent_events=[],
                    live_page_views={},
                    current_downloads=0
                )

            # Get recent events for live feed
            recent_events = await self._get_recent_live_events(project_id, 20)
            
            # Get current page views
            live_page_views = await self._get_current_page_views(project_id)
            
            # Get current downloads (last hour)
            current_downloads = await self._get_current_downloads(project_id)

            return RealtimeUpdate(
                project_id=project_id,
                timestamp=datetime.utcnow(),
                active_users=realtime.active_users_5min,
                recent_events=recent_events,
                live_page_views=live_page_views,
                current_downloads=current_downloads
            )

        except Exception as e:
            logger.error(f"Error getting real-time dashboard: {e}")
            raise

    async def get_analytics_report(
        self,
        project_id: str,
        report_type: str = "monthly",
        date_range: DateRangeType = DateRangeType.LAST_30_DAYS,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> AnalyticsReport:
        """
        Generate comprehensive analytics report.
        
        Args:
            project_id: Project identifier
            report_type: Type of report (daily, weekly, monthly, custom)
            date_range: Predefined date range type
            start_date: Custom start date
            end_date: Custom end date
            
        Returns:
            Analytics report object
        """
        try:
            start_dt, end_dt = self._calculate_date_range(date_range, start_date, end_date)
            
            # Generate comprehensive metrics
            visitor_analytics = await self.metrics_service.calculate_visitor_metrics(
                project_id, start_dt, end_dt
            )
            academic_metrics = await self.metrics_service.calculate_academic_metrics(
                project_id, start_dt, end_dt
            )
            geographic_analysis = await self.metrics_service.calculate_geographic_metrics(
                project_id, start_dt, end_dt
            )
            traffic_analysis = await self.metrics_service.calculate_traffic_source_metrics(
                project_id, start_dt, end_dt
            )
            engagement_metrics = await self.metrics_service.calculate_engagement_metrics(
                project_id, start_dt, end_dt
            )
            
            # Generate content performance analysis
            content_performance = await self._analyze_content_performance(
                project_id, start_dt, end_dt
            )
            
            # Generate technical insights
            technical_insights = await self._analyze_technical_insights(
                project_id, start_dt, end_dt
            )
            
            # Generate summary and recommendations
            summary = self._generate_executive_summary(
                visitor_analytics, academic_metrics, geographic_analysis, traffic_analysis
            )
            recommendations = self._generate_recommendations(
                visitor_analytics, academic_metrics, traffic_analysis, engagement_metrics
            )
            
            # Generate charts data
            charts_data = await self._generate_charts_data(project_id, start_dt, end_dt)

            report = AnalyticsReport(
                project_id=project_id,
                report_type=report_type,
                date_range={'start': start_dt, 'end': end_dt},
                generated_at=datetime.utcnow(),
                summary=summary,
                visitor_analytics=visitor_analytics,
                academic_metrics=academic_metrics,
                geographic_analysis=geographic_analysis,
                traffic_analysis=traffic_analysis,
                content_performance=content_performance,
                technical_insights=technical_insights,
                recommendations=recommendations,
                charts=charts_data
            )

            logger.info(f"Generated analytics report for project {project_id}")
            return report

        except Exception as e:
            logger.error(f"Error generating analytics report: {e}")
            raise

    async def export_analytics_data(
        self,
        project_id: str,
        export_type: str = "csv",
        date_range: DateRangeType = DateRangeType.LAST_30_DAYS,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_raw_data: bool = False
    ) -> ExportData:
        """
        Export analytics data in various formats.
        
        Args:
            project_id: Project identifier
            export_type: Export format (csv, json, pdf)
            date_range: Predefined date range type
            start_date: Custom start date
            end_date: Custom end date
            include_raw_data: Whether to include raw event data
            
        Returns:
            Export data object
        """
        try:
            start_dt, end_dt = self._calculate_date_range(date_range, start_date, end_date)
            
            # Collect data for export
            export_data = {
                'summary': await self._get_export_summary(project_id, start_dt, end_dt),
                'daily_metrics': await self._get_export_daily_metrics(project_id, start_dt, end_dt),
                'traffic_sources': await self._get_export_traffic_sources(project_id, start_dt, end_dt),
                'geographic_data': await self._get_export_geographic_data(project_id, start_dt, end_dt),
                'academic_events': await self._get_export_academic_events(project_id, start_dt, end_dt)
            }
            
            if include_raw_data:
                export_data['raw_events'] = await self._get_export_raw_events(
                    project_id, start_dt, end_dt, limit=10000
                )

            return ExportData(
                project_id=project_id,
                export_type=export_type,
                date_range={'start': start_dt, 'end': end_dt},
                data=export_data,
                generated_at=datetime.utcnow(),
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )

        except Exception as e:
            logger.error(f"Error exporting analytics data: {e}")
            raise

    # Helper Methods for Dashboard Data
    async def _get_overview_metrics(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get overview metrics for dashboard."""
        visitor_metrics = await self.metrics_service.calculate_visitor_metrics(
            project_id, start_date, end_date
        )
        
        return {
            'total_visitors': visitor_metrics.get('unique_visitors', 0),
            'total_page_views': visitor_metrics.get('total_page_views', 0),
            'bounce_rate': visitor_metrics.get('bounce_rate', 0),
            'avg_session_duration': visitor_metrics.get('avg_session_duration', 0)
        }

    async def _get_academic_metrics(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get academic metrics for dashboard."""
        academic_metrics = await self.metrics_service.calculate_academic_metrics(
            project_id, start_date, end_date
        )
        
        return {
            'abstract_views': academic_metrics.get('abstract_views', 0),
            'pdf_downloads': academic_metrics.get('pdf_downloads', 0),
            'bibtex_downloads': academic_metrics.get('bibtex_downloads', 0),
            'citation_clicks': academic_metrics.get('citation_clicks', 0),
            'figure_views': academic_metrics.get('figure_views', 0),
            'reference_clicks': academic_metrics.get('reference_clicks', 0)
        }

    async def _get_realtime_metrics(self, project_id: str) -> Dict[str, Any]:
        """Get real-time metrics for dashboard."""
        result = await self.db.execute(
            select(RealtimeMetrics)
            .where(RealtimeMetrics.project_id == project_id)
            .order_by(desc(RealtimeMetrics.timestamp))
            .limit(1)
        )
        realtime = result.scalar_one_or_none()
        
        if realtime:
            return {
                'active_users': realtime.active_users_5min,
                'users_last_hour': realtime.unique_visitors_1h
            }
        else:
            return {
                'active_users': 0,
                'users_last_hour': 0
            }

    async def _get_geographic_data(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get geographic data for dashboard."""
        geographic_metrics = await self.metrics_service.calculate_geographic_metrics(
            project_id, start_date, end_date
        )
        
        return {
            'countries': geographic_metrics.get('countries', [])[:10],  # Top 10 countries
            'total_countries': geographic_metrics.get('total_countries', 0)
        }

    async def _get_traffic_sources(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get traffic sources data for dashboard."""
        traffic_metrics = await self.metrics_service.calculate_traffic_source_metrics(
            project_id, start_date, end_date
        )
        
        sources = {}
        for source in traffic_metrics.get('traffic_sources', []):
            sources[source['source']] = source['visitors']
        
        referrers = [
            {'domain': r['domain'], 'visitors': r['visitors']}
            for r in traffic_metrics.get('referrers', [])[:10]
        ]
        
        return {
            'sources': sources,
            'referrers': referrers
        }

    async def _get_device_breakdown(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, float]:
        """Get device breakdown for dashboard."""
        result = await self.db.execute(
            select(
                AnalyticsSession.device_type,
                func.count(AnalyticsSession.id).label('count')
            )
            .where(
                and_(
                    AnalyticsSession.project_id == project_id,
                    AnalyticsSession.first_visit >= start_date,
                    AnalyticsSession.first_visit <= end_date,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
            .group_by(AnalyticsSession.device_type)
        )
        
        device_counts = {}
        total = 0
        for row in result.fetchall():
            device_counts[row.device_type] = row.count
            total += row.count
        
        if total == 0:
            return {'desktop': 0, 'mobile': 0, 'tablet': 0}
        
        return {
            'desktop': (device_counts.get('desktop', 0) / total) * 100,
            'mobile': (device_counts.get('mobile', 0) / total) * 100,
            'tablet': (device_counts.get('tablet', 0) / total) * 100
        }

    async def _get_trending_data(self, project_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get trending data for charts."""
        result = await self.db.execute(
            select(DailyMetrics)
            .where(
                and_(
                    DailyMetrics.project_id == project_id,
                    DailyMetrics.date >= start_date.date(),
                    DailyMetrics.date <= end_date.date()
                )
            )
            .order_by(DailyMetrics.date)
        )
        
        trends = []
        for metrics in result.scalars():
            trends.append({
                'date': metrics.date.isoformat(),
                'visitors': metrics.unique_visitors,
                'page_views': metrics.total_page_views,
                'downloads': metrics.pdf_downloads
            })
        
        return trends

    async def _get_popular_content(self, project_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get popular content data."""
        result = await self.db.execute(
            select(
                AnalyticsEvent.page_url,
                AnalyticsEvent.page_title,
                func.count(AnalyticsEvent.id).label('views')
            )
            .join(AnalyticsSession)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsEvent.timestamp >= start_date,
                    AnalyticsEvent.timestamp <= end_date,
                    AnalyticsEvent.event_type == EventType.PAGE_VIEW,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
            .group_by(AnalyticsEvent.page_url, AnalyticsEvent.page_title)
            .order_by(desc('views'))
            .limit(10)
        )
        
        return [
            {
                'url': row.page_url,
                'title': row.page_title or 'Unknown',
                'views': row.views
            }
            for row in result.fetchall()
        ]

    async def _get_engagement_metrics(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get engagement metrics for dashboard."""
        engagement = await self.metrics_service.calculate_engagement_metrics(
            project_id, start_date, end_date
        )
        
        return {
            'avg_scroll_depth': engagement.get('scroll_depth', {}).get('avg_scroll_depth', 0),
            'avg_time_on_page': engagement.get('time_on_page', {}).get('overall_avg_time', 0),
            'interaction_rate': engagement.get('interaction_patterns', {}).get('interaction_rate', 0)
        }

    async def _get_download_trends(self, project_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get download trends data."""
        result = await self.db.execute(
            select(
                func.date(AnalyticsEvent.timestamp).label('date'),
                AnalyticsEvent.download_type,
                func.count(AnalyticsEvent.id).label('downloads')
            )
            .join(AnalyticsSession)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsEvent.timestamp >= start_date,
                    AnalyticsEvent.timestamp <= end_date,
                    AnalyticsEvent.event_type.in_([EventType.PDF_DOWNLOAD, EventType.BIBTEX_DOWNLOAD]),
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
            .group_by(func.date(AnalyticsEvent.timestamp), AnalyticsEvent.download_type)
            .order_by('date')
        )
        
        trends = []
        for row in result.fetchall():
            trends.append({
                'date': row.date.isoformat(),
                'type': row.download_type,
                'downloads': row.downloads
            })
        
        return trends

    async def _get_recent_live_events(self, project_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent events for live feed."""
        result = await self.db.execute(
            select(AnalyticsEvent, AnalyticsSession.country_code)
            .join(AnalyticsSession)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
            .order_by(desc(AnalyticsEvent.timestamp))
            .limit(limit)
        )
        
        events = []
        for event, country_code in result.fetchall():
            events.append({
                'type': event.event_type,
                'timestamp': event.timestamp.isoformat(),
                'page_title': event.page_title,
                'country': country_code,
                'details': self._format_event_details(event)
            })
        
        return events

    async def _get_current_page_views(self, project_id: str) -> Dict[str, int]:
        """Get current page views (last 5 minutes)."""
        five_min_ago = datetime.utcnow() - timedelta(minutes=5)
        
        result = await self.db.execute(
            select(
                AnalyticsEvent.page_url,
                func.count(AnalyticsEvent.id).label('views')
            )
            .join(AnalyticsSession)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsEvent.timestamp >= five_min_ago,
                    AnalyticsEvent.event_type == EventType.PAGE_VIEW,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
            .group_by(AnalyticsEvent.page_url)
        )
        
        page_views = {}
        for row in result.fetchall():
            if row.page_url:
                page_views[row.page_url] = row.views
        
        return page_views

    async def _get_current_downloads(self, project_id: str) -> int:
        """Get current downloads (last hour)."""
        one_hour_ago = datetime.utcnow() - timedelta(hours=1)
        
        result = await self.db.execute(
            select(func.count(AnalyticsEvent.id))
            .join(AnalyticsSession)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsEvent.timestamp >= one_hour_ago,
                    AnalyticsEvent.event_type.in_([EventType.PDF_DOWNLOAD, EventType.BIBTEX_DOWNLOAD]),
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
        )
        
        return result.scalar() or 0

    def _calculate_date_range(
        self,
        date_range: DateRangeType,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Tuple[datetime, datetime]:
        """Calculate start and end dates for given range type."""
        now = datetime.utcnow()
        today = now.replace(hour=0, minute=0, second=0, microsecond=0)
        
        if date_range == DateRangeType.CUSTOM:
            if not start_date or not end_date:
                raise ValueError("Custom date range requires start_date and end_date")
            return start_date, end_date
        elif date_range == DateRangeType.TODAY:
            return today, now
        elif date_range == DateRangeType.YESTERDAY:
            yesterday = today - timedelta(days=1)
            return yesterday, today
        elif date_range == DateRangeType.LAST_7_DAYS:
            return today - timedelta(days=7), now
        elif date_range == DateRangeType.LAST_30_DAYS:
            return today - timedelta(days=30), now
        elif date_range == DateRangeType.LAST_90_DAYS:
            return today - timedelta(days=90), now
        elif date_range == DateRangeType.THIS_MONTH:
            month_start = today.replace(day=1)
            return month_start, now
        elif date_range == DateRangeType.LAST_MONTH:
            month_start = today.replace(day=1)
            last_month_end = month_start - timedelta(days=1)
            last_month_start = last_month_end.replace(day=1)
            return last_month_start, month_start
        elif date_range == DateRangeType.THIS_YEAR:
            year_start = today.replace(month=1, day=1)
            return year_start, now
        elif date_range == DateRangeType.ALL_TIME:
            # Get the earliest session for this project
            return datetime(2020, 1, 1), now  # Fallback to reasonable start date
        else:
            return today - timedelta(days=30), now  # Default to last 30 days

    def _format_event_details(self, event: AnalyticsEvent) -> Dict[str, Any]:
        """Format event details for display."""
        details = {}
        
        if event.paper_section:
            details['section'] = event.paper_section
        if event.figure_id:
            details['figure'] = event.figure_id
        if event.download_type:
            details['download_type'] = event.download_type
        if event.citation_id:
            details['citation'] = event.citation_id
        
        return details

    # Report Generation Helper Methods
    async def _analyze_content_performance(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze content performance for reports."""
        # Get section performance
        section_performance = await self.metrics_service.calculate_academic_metrics(
            project_id, start_date, end_date
        )
        
        return {
            'section_popularity': section_performance.get('section_popularity', {}),
            'figure_engagement': section_performance.get('figure_engagement', {}),
            'download_patterns': section_performance.get('download_patterns', {})
        }

    async def _analyze_technical_insights(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze technical insights for reports."""
        # Placeholder for technical analysis
        return {
            'load_performance': {},
            'browser_compatibility': {},
            'device_optimization': {}
        }

    def _generate_executive_summary(
        self,
        visitor_analytics: Dict,
        academic_metrics: Dict,
        geographic_analysis: Dict,
        traffic_analysis: Dict
    ) -> Dict[str, Any]:
        """Generate executive summary for reports."""
        return {
            'total_visitors': visitor_analytics.get('unique_visitors', 0),
            'engagement_rate': (1 - visitor_analytics.get('bounce_rate', 0) / 100) * 100,
            'international_reach': geographic_analysis.get('total_countries', 0),
            'academic_engagement': academic_metrics.get('pdf_downloads', 0),
            'top_traffic_source': traffic_analysis.get('traffic_quality', {}).get('best_quality_source', 'Direct')
        }

    def _generate_recommendations(
        self,
        visitor_analytics: Dict,
        academic_metrics: Dict,
        traffic_analysis: Dict,
        engagement_metrics: Dict
    ) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        # Bounce rate recommendation
        bounce_rate = visitor_analytics.get('bounce_rate', 0)
        if bounce_rate > 70:
            recommendations.append("Consider improving your abstract or introduction to reduce the high bounce rate of {:.1f}%".format(bounce_rate))
        
        # Download conversion recommendation
        pdf_downloads = academic_metrics.get('pdf_downloads', 0)
        abstract_views = academic_metrics.get('abstract_views', 0)
        if abstract_views > 0:
            conversion_rate = (pdf_downloads / abstract_views) * 100
            if conversion_rate < 10:
                recommendations.append("Consider optimizing your abstract to improve PDF download conversion rate ({:.1f}%)".format(conversion_rate))
        
        # Traffic diversification
        traffic_sources = traffic_analysis.get('traffic_sources', [])
        if len(traffic_sources) < 3:
            recommendations.append("Consider diversifying your traffic sources by promoting on academic platforms and social media")
        
        # Engagement optimization
        avg_scroll = engagement_metrics.get('scroll_depth', {}).get('avg_scroll_depth', 0)
        if avg_scroll < 0.5:
            recommendations.append("Consider restructuring content to improve reader engagement (average scroll depth: {:.1%})".format(avg_scroll))
        
        return recommendations

    async def _generate_charts_data(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate data for charts and visualizations."""
        # Get time series data
        time_series = await self.metrics_service.calculate_time_series_metrics(
            project_id, start_date, end_date, 'daily'
        )
        
        return {
            'visitor_trends': time_series.get('daily_data', []),
            'traffic_source_pie': {},
            'geographic_map': {},
            'engagement_funnel': {}
        }

    # Export Helper Methods
    async def _get_export_summary(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get summary data for export."""
        overview = await self._get_overview_metrics(project_id, start_date, end_date)
        academic = await self._get_academic_metrics(project_id, start_date, end_date)
        
        return {**overview, **academic}

    async def _get_export_daily_metrics(self, project_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get daily metrics for export."""
        result = await self.db.execute(
            select(DailyMetrics)
            .where(
                and_(
                    DailyMetrics.project_id == project_id,
                    DailyMetrics.date >= start_date.date(),
                    DailyMetrics.date <= end_date.date()
                )
            )
            .order_by(DailyMetrics.date)
        )
        
        return [
            {
                'date': metrics.date.isoformat(),
                'unique_visitors': metrics.unique_visitors,
                'page_views': metrics.total_page_views,
                'pdf_downloads': metrics.pdf_downloads,
                'bounce_rate': metrics.bounce_rate,
                'avg_session_duration': metrics.avg_session_duration
            }
            for metrics in result.scalars()
        ]

    async def _get_export_traffic_sources(self, project_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get traffic sources for export."""
        traffic_metrics = await self.metrics_service.calculate_traffic_source_metrics(
            project_id, start_date, end_date
        )
        
        return traffic_metrics.get('traffic_sources', [])

    async def _get_export_geographic_data(self, project_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get geographic data for export."""
        geo_metrics = await self.metrics_service.calculate_geographic_metrics(
            project_id, start_date, end_date
        )
        
        return geo_metrics.get('countries', [])

    async def _get_export_academic_events(self, project_id: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get academic events for export."""
        result = await self.db.execute(
            select(
                func.date(AnalyticsEvent.timestamp).label('date'),
                AnalyticsEvent.event_type,
                func.count(AnalyticsEvent.id).label('count')
            )
            .join(AnalyticsSession)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsEvent.timestamp >= start_date,
                    AnalyticsEvent.timestamp <= end_date,
                    AnalyticsEvent.event_type.in_([
                        EventType.ABSTRACT_VIEW, EventType.PDF_DOWNLOAD,
                        EventType.BIBTEX_DOWNLOAD, EventType.CITATION_CLICK,
                        EventType.FIGURE_VIEW, EventType.REFERENCE_CLICK
                    ]),
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
            .group_by(func.date(AnalyticsEvent.timestamp), AnalyticsEvent.event_type)
            .order_by('date')
        )
        
        return [
            {
                'date': row.date.isoformat(),
                'event_type': row.event_type,
                'count': row.count
            }
            for row in result.fetchall()
        ]

    async def _get_export_raw_events(self, project_id: str, start_date: datetime, end_date: datetime, limit: int = 10000) -> List[Dict[str, Any]]:
        """Get raw events for export (limited for performance)."""
        result = await self.db.execute(
            select(AnalyticsEvent, AnalyticsSession.country_code)
            .join(AnalyticsSession)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsEvent.timestamp >= start_date,
                    AnalyticsEvent.timestamp <= end_date,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
            .order_by(desc(AnalyticsEvent.timestamp))
            .limit(limit)
        )
        
        events = []
        for event, country_code in result.fetchall():
            events.append({
                'timestamp': event.timestamp.isoformat(),
                'event_type': event.event_type,
                'page_url': event.page_url,
                'page_title': event.page_title,
                'country': country_code,
                'duration': event.duration,
                'scroll_depth': event.scroll_depth
            })
        
        return events