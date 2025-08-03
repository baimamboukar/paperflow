"""
Core analytics service for Paperflow.

This service orchestrates analytics collection, processing, and reporting
while maintaining privacy and GDPR compliance.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc
from sqlalchemy.orm import selectinload

from ...models.analytics import (
    AnalyticsSession,
    AnalyticsEvent,
    DailyMetrics,
    RealtimeMetrics,
    AnalyticsConfig,
    EventType,
    DeviceType,
    TrafficSource,
    SessionCreate,
    EventCreate,
    DashboardMetrics,
    ExportData,
    AnalyticsReport
)
from ..base import BaseService

logger = logging.getLogger(__name__)


class AnalyticsService(BaseService):
    """
    Core analytics service providing comprehensive analytics functionality.
    
    Features:
    - Privacy-first data collection
    - GDPR compliance
    - Real-time analytics
    - Academic metrics tracking
    - Geographic insights
    - Performance optimization
    """

    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session)
        self._realtime_cache = {}  # In-memory cache for real-time metrics
        self._aggregation_lock = asyncio.Lock()

    # Session Management
    async def create_session(self, session_data: SessionCreate) -> AnalyticsSession:
        """
        Create a new analytics session with privacy protection.
        
        Args:
            session_data: Session creation data
            
        Returns:
            Created analytics session
        """
        try:
            # Check if session already exists (duplicate protection)
            existing = await self.db.execute(
                select(AnalyticsSession).where(
                    AnalyticsSession.session_hash == session_data.session_hash
                )
            )
            existing_session = existing.scalar_one_or_none()
            
            if existing_session:
                # Update last activity
                existing_session.last_activity = datetime.utcnow()
                await self.db.commit()
                return existing_session

            # Create new session
            session = AnalyticsSession(
                project_id=session_data.project_id,
                session_hash=session_data.session_hash,
                country_code=session_data.country_code,
                region=session_data.region,
                city=session_data.city,
                timezone=session_data.timezone,
                device_type=session_data.device_type,
                browser=session_data.browser,
                os=session_data.os,
                screen_resolution=session_data.screen_resolution,
                traffic_source=session_data.traffic_source,
                referrer_domain=session_data.referrer_domain,
                referrer_url=session_data.referrer_url[:500] if session_data.referrer_url else None,
                utm_source=session_data.utm_source,
                utm_medium=session_data.utm_medium,
                utm_campaign=session_data.utm_campaign,
                is_bot=session_data.is_bot,
                do_not_track=session_data.do_not_track
            )

            self.db.add(session)
            await self.db.commit()
            await self.db.refresh(session)
            
            logger.info(f"Created analytics session for project {session_data.project_id}")
            return session

        except Exception as e:
            logger.error(f"Error creating analytics session: {e}")
            await self.db.rollback()
            raise

    async def update_session_activity(self, session_id: str) -> None:
        """Update session last activity timestamp."""
        try:
            result = await self.db.execute(
                select(AnalyticsSession).where(AnalyticsSession.id == session_id)
            )
            session = result.scalar_one_or_none()
            
            if session:
                session.last_activity = datetime.utcnow()
                await self.db.commit()

        except Exception as e:
            logger.error(f"Error updating session activity: {e}")

    # Event Tracking
    async def track_event(self, event_data: EventCreate) -> AnalyticsEvent:
        """
        Track an analytics event with academic focus.
        
        Args:
            event_data: Event data to track
            
        Returns:
            Created analytics event
        """
        try:
            # Verify session exists and is not marked as bot/DNT
            result = await self.db.execute(
                select(AnalyticsSession).where(AnalyticsSession.id == event_data.session_id)
            )
            session = result.scalar_one_or_none()
            
            if not session:
                raise ValueError(f"Session {event_data.session_id} not found")
                
            if session.is_bot or session.do_not_track:
                logger.info(f"Skipping event tracking for bot/DNT session {event_data.session_id}")
                return None

            # Create event
            event = AnalyticsEvent(
                session_id=event_data.session_id,
                project_id=event_data.project_id,
                event_type=event_data.event_type,
                page_url=event_data.page_url[:500] if event_data.page_url else None,
                page_title=event_data.page_title[:255] if event_data.page_title else None,
                section_id=event_data.section_id,
                paper_section=event_data.paper_section,
                figure_id=event_data.figure_id,
                citation_id=event_data.citation_id,
                reference_id=event_data.reference_id,
                download_type=event_data.download_type,
                event_data=event_data.event_data,
                duration=event_data.duration,
                scroll_depth=event_data.scroll_depth,
                click_position_x=event_data.click_position_x,
                click_position_y=event_data.click_position_y,
                viewport_width=event_data.viewport_width,
                viewport_height=event_data.viewport_height
            )

            self.db.add(event)
            
            # Update session counters
            if event_data.event_type == EventType.PAGE_VIEW:
                session.page_views += 1
                
            # Update session duration if provided
            if event_data.duration:
                session.session_duration += event_data.duration

            session.last_activity = datetime.utcnow()
            
            await self.db.commit()
            await self.db.refresh(event)
            
            # Update real-time metrics asynchronously
            asyncio.create_task(self._update_realtime_metrics(event_data.project_id, event))
            
            logger.debug(f"Tracked {event_data.event_type} event for project {event_data.project_id}")
            return event

        except Exception as e:
            logger.error(f"Error tracking event: {e}")
            await self.db.rollback()
            raise

    # Real-time Metrics
    async def _update_realtime_metrics(self, project_id: str, event: AnalyticsEvent) -> None:
        """Update real-time metrics cache and database."""
        try:
            now = datetime.utcnow()
            
            # Get or create real-time metrics record
            result = await self.db.execute(
                select(RealtimeMetrics)
                .where(RealtimeMetrics.project_id == project_id)
                .order_by(desc(RealtimeMetrics.timestamp))
                .limit(1)
            )
            metrics = result.scalar_one_or_none()
            
            if not metrics or (now - metrics.timestamp).seconds > 300:  # 5 minutes
                metrics = RealtimeMetrics(
                    project_id=project_id,
                    timestamp=now
                )
                self.db.add(metrics)

            # Calculate active users for different time windows
            one_min_ago = now - timedelta(minutes=1)
            five_min_ago = now - timedelta(minutes=5)
            thirty_min_ago = now - timedelta(minutes=30)
            one_hour_ago = now - timedelta(hours=1)

            # Active users counts
            active_1min = await self._count_active_users(project_id, one_min_ago)
            active_5min = await self._count_active_users(project_id, five_min_ago)
            active_30min = await self._count_active_users(project_id, thirty_min_ago)

            # Hourly stats
            hourly_stats = await self._get_hourly_stats(project_id, one_hour_ago)

            # Update metrics
            metrics.active_users_1min = active_1min
            metrics.active_users_5min = active_5min
            metrics.active_users_30min = active_30min
            metrics.page_views_1h = hourly_stats['page_views']
            metrics.pdf_downloads_1h = hourly_stats['pdf_downloads']
            metrics.unique_visitors_1h = hourly_stats['unique_visitors']

            # Top pages and recent events
            metrics.top_pages = await self._get_top_pages(project_id, one_hour_ago)
            metrics.recent_events = await self._get_recent_events(project_id, 10)

            await self.db.commit()

        except Exception as e:
            logger.error(f"Error updating real-time metrics: {e}")

    async def _count_active_users(self, project_id: str, since: datetime) -> int:
        """Count active users since given timestamp."""
        result = await self.db.execute(
            select(func.count(func.distinct(AnalyticsSession.id)))
            .where(
                and_(
                    AnalyticsSession.project_id == project_id,
                    AnalyticsSession.last_activity >= since,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
        )
        return result.scalar() or 0

    async def _get_hourly_stats(self, project_id: str, since: datetime) -> Dict[str, int]:
        """Get hourly statistics for real-time dashboard."""
        # Page views
        page_views_result = await self.db.execute(
            select(func.count(AnalyticsEvent.id))
            .join(AnalyticsSession)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsEvent.timestamp >= since,
                    AnalyticsEvent.event_type == EventType.PAGE_VIEW,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
        )
        page_views = page_views_result.scalar() or 0

        # PDF downloads
        pdf_downloads_result = await self.db.execute(
            select(func.count(AnalyticsEvent.id))
            .join(AnalyticsSession)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsEvent.timestamp >= since,
                    AnalyticsEvent.event_type == EventType.PDF_DOWNLOAD,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
        )
        pdf_downloads = pdf_downloads_result.scalar() or 0

        # Unique visitors
        unique_visitors_result = await self.db.execute(
            select(func.count(func.distinct(AnalyticsSession.id)))
            .join(AnalyticsEvent)
            .where(
                and_(
                    AnalyticsEvent.project_id == project_id,
                    AnalyticsEvent.timestamp >= since,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
        )
        unique_visitors = unique_visitors_result.scalar() or 0

        return {
            'page_views': page_views,
            'pdf_downloads': pdf_downloads,
            'unique_visitors': unique_visitors
        }

    async def _get_top_pages(self, project_id: str, since: datetime) -> List[Dict[str, Any]]:
        """Get top pages for real-time dashboard."""
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
                    AnalyticsEvent.timestamp >= since,
                    AnalyticsEvent.event_type == EventType.PAGE_VIEW,
                    AnalyticsEvent.page_url.isnot(None),
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

    async def _get_recent_events(self, project_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent events for real-time feed."""
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
                'data': {
                    'section': event.paper_section,
                    'figure_id': event.figure_id,
                    'download_type': event.download_type
                }
            })
        
        return events

    # Data Aggregation
    async def aggregate_daily_metrics(self, project_id: str, date: datetime) -> DailyMetrics:
        """
        Aggregate daily metrics for a specific date.
        
        Args:
            project_id: Project identifier
            date: Date to aggregate (will be truncated to day)
            
        Returns:
            Aggregated daily metrics
        """
        async with self._aggregation_lock:
            try:
                # Truncate to day
                day_start = date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = day_start + timedelta(days=1)
                
                # Check if already aggregated
                result = await self.db.execute(
                    select(DailyMetrics).where(
                        and_(
                            DailyMetrics.project_id == project_id,
                            DailyMetrics.date == day_start
                        )
                    )
                )
                existing = result.scalar_one_or_none()
                
                if existing:
                    return existing

                # Calculate metrics
                metrics_data = await self._calculate_daily_metrics(project_id, day_start, day_end)
                
                # Create daily metrics record
                daily_metrics = DailyMetrics(
                    project_id=project_id,
                    date=day_start,
                    **metrics_data
                )
                
                self.db.add(daily_metrics)
                await self.db.commit()
                await self.db.refresh(daily_metrics)
                
                logger.info(f"Aggregated daily metrics for {project_id} on {day_start.date()}")
                return daily_metrics

            except Exception as e:
                logger.error(f"Error aggregating daily metrics: {e}")
                await self.db.rollback()
                raise

    async def _calculate_daily_metrics(self, project_id: str, day_start: datetime, day_end: datetime) -> Dict[str, Any]:
        """Calculate all daily metrics for a given day."""
        # Base filter for valid sessions
        base_session_filter = and_(
            AnalyticsSession.project_id == project_id,
            AnalyticsSession.first_visit >= day_start,
            AnalyticsSession.first_visit < day_end,
            AnalyticsSession.is_bot == False,
            AnalyticsSession.do_not_track == False
        )
        
        # Base filter for valid events
        base_event_filter = and_(
            AnalyticsEvent.project_id == project_id,
            AnalyticsEvent.timestamp >= day_start,
            AnalyticsEvent.timestamp < day_end
        )

        # Unique visitors
        unique_visitors_result = await self.db.execute(
            select(func.count(func.distinct(AnalyticsSession.id)))
            .where(base_session_filter)
        )
        unique_visitors = unique_visitors_result.scalar() or 0

        # Total page views
        page_views_result = await self.db.execute(
            select(func.count(AnalyticsEvent.id))
            .join(AnalyticsSession)
            .where(
                and_(
                    base_event_filter,
                    AnalyticsEvent.event_type == EventType.PAGE_VIEW,
                    AnalyticsSession.is_bot == False,
                    AnalyticsSession.do_not_track == False
                )
            )
        )
        total_page_views = page_views_result.scalar() or 0

        # Calculate bounce rate (sessions with only 1 page view)
        single_page_sessions = await self.db.execute(
            select(func.count(AnalyticsSession.id))
            .where(
                and_(
                    base_session_filter,
                    AnalyticsSession.page_views == 1
                )
            )
        )
        single_page_count = single_page_sessions.scalar() or 0
        bounce_rate = (single_page_count / unique_visitors * 100) if unique_visitors > 0 else 0

        # Average session duration
        avg_duration_result = await self.db.execute(
            select(func.avg(AnalyticsSession.session_duration))
            .where(base_session_filter)
        )
        avg_session_duration = avg_duration_result.scalar() or 0

        # Academic metrics
        academic_metrics = await self._calculate_academic_metrics(base_event_filter)
        
        # Geographic data
        geographic_data = await self._calculate_geographic_data(base_session_filter)
        
        # Device breakdown
        device_data = await self._calculate_device_breakdown(base_session_filter)
        
        # Traffic sources
        traffic_data = await self._calculate_traffic_sources(base_session_filter)

        return {
            'unique_visitors': unique_visitors,
            'total_page_views': total_page_views,
            'bounce_rate': bounce_rate,
            'avg_session_duration': avg_session_duration,
            **academic_metrics,
            **geographic_data,
            **device_data,
            **traffic_data
        }

    async def _calculate_academic_metrics(self, base_filter) -> Dict[str, int]:
        """Calculate academic-specific metrics."""
        metrics = {}
        
        academic_events = [
            (EventType.ABSTRACT_VIEW, 'abstract_views'),
            (EventType.PDF_DOWNLOAD, 'pdf_downloads'),
            (EventType.BIBTEX_DOWNLOAD, 'bibtex_downloads'),
            (EventType.CITATION_CLICK, 'citation_clicks'),
            (EventType.FIGURE_VIEW, 'figure_views'),
            (EventType.REFERENCE_CLICK, 'reference_clicks')
        ]
        
        for event_type, metric_name in academic_events:
            result = await self.db.execute(
                select(func.count(AnalyticsEvent.id))
                .join(AnalyticsSession)
                .where(
                    and_(
                        base_filter,
                        AnalyticsEvent.event_type == event_type,
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
            )
            metrics[metric_name] = result.scalar() or 0
            
        return metrics

    async def _calculate_geographic_data(self, base_filter) -> Dict[str, Any]:
        """Calculate geographic distribution."""
        result = await self.db.execute(
            select(
                AnalyticsSession.country_code,
                func.count(AnalyticsSession.id).label('count')
            )
            .where(
                and_(
                    base_filter,
                    AnalyticsSession.country_code.isnot(None)
                )
            )
            .group_by(AnalyticsSession.country_code)
            .order_by(desc('count'))
            .limit(10)
        )
        
        top_countries = {}
        for row in result.fetchall():
            top_countries[row.country_code] = row.count
            
        return {'top_countries': top_countries}

    async def _calculate_device_breakdown(self, base_filter) -> Dict[str, float]:
        """Calculate device type breakdown."""
        total_result = await self.db.execute(
            select(func.count(AnalyticsSession.id))
            .where(base_filter)
        )
        total = total_result.scalar() or 0
        
        if total == 0:
            return {
                'desktop_percentage': 0,
                'mobile_percentage': 0,
                'tablet_percentage': 0
            }

        device_result = await self.db.execute(
            select(
                AnalyticsSession.device_type,
                func.count(AnalyticsSession.id).label('count')
            )
            .where(base_filter)
            .group_by(AnalyticsSession.device_type)
        )
        
        device_counts = {DeviceType.DESKTOP: 0, DeviceType.MOBILE: 0, DeviceType.TABLET: 0}
        for row in device_result.fetchall():
            if row.device_type in device_counts:
                device_counts[row.device_type] = row.count

        return {
            'desktop_percentage': (device_counts[DeviceType.DESKTOP] / total) * 100,
            'mobile_percentage': (device_counts[DeviceType.MOBILE] / total) * 100,
            'tablet_percentage': (device_counts[DeviceType.TABLET] / total) * 100
        }

    async def _calculate_traffic_sources(self, base_filter) -> Dict[str, Any]:
        """Calculate traffic source breakdown."""
        # Traffic source counts
        traffic_result = await self.db.execute(
            select(
                AnalyticsSession.traffic_source,
                func.count(AnalyticsSession.id).label('count')
            )
            .where(base_filter)
            .group_by(AnalyticsSession.traffic_source)
        )
        
        traffic_sources = {}
        for row in traffic_result.fetchall():
            traffic_sources[row.traffic_source] = row.count

        # Top referrers
        referrer_result = await self.db.execute(
            select(
                AnalyticsSession.referrer_domain,
                func.count(AnalyticsSession.id).label('count')
            )
            .where(
                and_(
                    base_filter,
                    AnalyticsSession.referrer_domain.isnot(None)
                )
            )
            .group_by(AnalyticsSession.referrer_domain)
            .order_by(desc('count'))
            .limit(10)
        )
        
        top_referrers = {}
        for row in referrer_result.fetchall():
            top_referrers[row.referrer_domain] = row.count

        return {
            'direct_traffic': traffic_sources.get(TrafficSource.DIRECT, 0),
            'search_traffic': traffic_sources.get(TrafficSource.SEARCH_ENGINE, 0),
            'referral_traffic': traffic_sources.get(TrafficSource.REFERRAL, 0),
            'social_traffic': traffic_sources.get(TrafficSource.SOCIAL_MEDIA, 0),
            'academic_traffic': traffic_sources.get(TrafficSource.ACADEMIC_PLATFORM, 0),
            'top_referrers': top_referrers
        }

    # Configuration Management
    async def get_project_config(self, project_id: str) -> AnalyticsConfig:
        """Get analytics configuration for a project."""
        # For now, return default config - in future this could be stored in database
        return AnalyticsConfig(project_id=project_id)

    async def update_project_config(self, project_id: str, config: AnalyticsConfig) -> AnalyticsConfig:
        """Update analytics configuration for a project."""
        # TODO: Implement configuration storage
        logger.info(f"Updated analytics config for project {project_id}")
        return config

    # Utility Methods
    async def cleanup_old_data(self, retention_days: int = 365) -> int:
        """
        Clean up old analytics data based on retention policy.
        
        Args:
            retention_days: Number of days to retain data
            
        Returns:
            Number of records deleted
        """
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        try:
            # Delete old events
            events_result = await self.db.execute(
                select(func.count(AnalyticsEvent.id))
                .where(AnalyticsEvent.timestamp < cutoff_date)
            )
            events_to_delete = events_result.scalar() or 0
            
            if events_to_delete > 0:
                await self.db.execute(
                    AnalyticsEvent.__table__.delete()
                    .where(AnalyticsEvent.timestamp < cutoff_date)
                )

            # Delete old sessions
            sessions_result = await self.db.execute(
                select(func.count(AnalyticsSession.id))
                .where(AnalyticsSession.first_visit < cutoff_date)
            )
            sessions_to_delete = sessions_result.scalar() or 0
            
            if sessions_to_delete > 0:
                await self.db.execute(
                    AnalyticsSession.__table__.delete()
                    .where(AnalyticsSession.first_visit < cutoff_date)
                )

            # Delete old daily metrics
            metrics_result = await self.db.execute(
                select(func.count(DailyMetrics.id))
                .where(DailyMetrics.date < cutoff_date)
            )
            metrics_to_delete = metrics_result.scalar() or 0
            
            if metrics_to_delete > 0:
                await self.db.execute(
                    DailyMetrics.__table__.delete()
                    .where(DailyMetrics.date < cutoff_date)
                )

            await self.db.commit()
            
            total_deleted = events_to_delete + sessions_to_delete + metrics_to_delete
            logger.info(f"Cleaned up {total_deleted} old analytics records")
            return total_deleted

        except Exception as e:
            logger.error(f"Error cleaning up old data: {e}")
            await self.db.rollback()
            raise

    async def get_project_summary(self, project_id: str) -> Dict[str, Any]:
        """Get a quick summary of project analytics."""
        try:
            # Get total counts
            total_sessions = await self.db.execute(
                select(func.count(AnalyticsSession.id))
                .where(
                    and_(
                        AnalyticsSession.project_id == project_id,
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
            )
            
            total_events = await self.db.execute(
                select(func.count(AnalyticsEvent.id))
                .where(AnalyticsEvent.project_id == project_id)
            )
            
            # Get recent activity (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            recent_sessions = await self.db.execute(
                select(func.count(AnalyticsSession.id))
                .where(
                    and_(
                        AnalyticsSession.project_id == project_id,
                        AnalyticsSession.first_visit >= thirty_days_ago,
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
            )
            
            return {
                'total_visitors': total_sessions.scalar() or 0,
                'total_events': total_events.scalar() or 0,
                'recent_visitors_30d': recent_sessions.scalar() or 0,
                'tracking_active': True
            }
            
        except Exception as e:
            logger.error(f"Error getting project summary: {e}")
            return {
                'total_visitors': 0,
                'total_events': 0,
                'recent_visitors_30d': 0,
                'tracking_active': False
            }