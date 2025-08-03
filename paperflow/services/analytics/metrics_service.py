"""
Metrics service for Paperflow analytics.

This service handles metrics calculation, aggregation, and advanced analytics
with focus on academic publishing insights.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import statistics

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_, desc, asc, text
from sqlalchemy.orm import selectinload

from ...models.analytics import (
    AnalyticsSession,
    AnalyticsEvent,
    DailyMetrics,
    RealtimeMetrics,
    EventType,
    DeviceType,
    TrafficSource
)
from ..base import BaseService

logger = logging.getLogger(__name__)


class MetricsService(BaseService):
    """
    Advanced metrics calculation and aggregation service.
    
    Features:
    - Academic-specific metrics calculation
    - Time-series analysis
    - Geographic distribution analysis
    - Engagement metrics calculation
    - Performance optimization with caching
    - Statistical analysis and insights
    """

    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session)
        self._metrics_cache = {}
        self._cache_ttl = 300  # 5 minutes cache TTL

    # Core Metrics Calculations
    async def calculate_visitor_metrics(
        self,
        project_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Calculate comprehensive visitor metrics for a date range.
        
        Args:
            project_id: Project identifier
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary with visitor metrics
        """
        try:
            cache_key = f"visitor_metrics_{project_id}_{start_date.date()}_{end_date.date()}"
            if cache_key in self._metrics_cache:
                cached_data, timestamp = self._metrics_cache[cache_key]
                if (datetime.utcnow() - timestamp).seconds < self._cache_ttl:
                    return cached_data

            # Base filters
            session_filter = and_(
                AnalyticsSession.project_id == project_id,
                AnalyticsSession.first_visit >= start_date,
                AnalyticsSession.first_visit <= end_date,
                AnalyticsSession.is_bot == False,
                AnalyticsSession.do_not_track == False
            )

            # Unique visitors
            unique_visitors_result = await self.db.execute(
                select(func.count(func.distinct(AnalyticsSession.id)))
                .where(session_filter)
            )
            unique_visitors = unique_visitors_result.scalar() or 0

            # Total sessions
            total_sessions_result = await self.db.execute(
                select(func.count(AnalyticsSession.id))
                .where(session_filter)
            )
            total_sessions = total_sessions_result.scalar() or 0

            # Page views
            page_views_result = await self.db.execute(
                select(func.sum(AnalyticsSession.page_views))
                .where(session_filter)
            )
            total_page_views = page_views_result.scalar() or 0

            # Session duration statistics
            duration_stats = await self._calculate_session_duration_stats(session_filter)

            # Bounce rate (sessions with only 1 page view)
            bounce_sessions_result = await self.db.execute(
                select(func.count(AnalyticsSession.id))
                .where(
                    and_(
                        session_filter,
                        AnalyticsSession.page_views == 1
                    )
                )
            )
            bounce_sessions = bounce_sessions_result.scalar() or 0
            bounce_rate = (bounce_sessions / unique_visitors * 100) if unique_visitors > 0 else 0

            # New vs returning visitors (simplified - based on session frequency)
            new_visitors = unique_visitors  # For now, treat all as new
            returning_visitors = 0  # TODO: Implement proper new/returning logic

            metrics = {
                'unique_visitors': unique_visitors,
                'total_sessions': total_sessions,
                'total_page_views': total_page_views,
                'avg_pages_per_session': (total_page_views / total_sessions) if total_sessions > 0 else 0,
                'bounce_rate': bounce_rate,
                'new_visitors': new_visitors,
                'returning_visitors': returning_visitors,
                'avg_session_duration': duration_stats['avg_duration'],
                'median_session_duration': duration_stats['median_duration'],
                'session_duration_distribution': duration_stats['duration_distribution']
            }

            # Cache the result
            self._metrics_cache[cache_key] = (metrics, datetime.utcnow())
            
            return metrics

        except Exception as e:
            logger.error(f"Error calculating visitor metrics: {e}")
            return {}

    async def calculate_academic_metrics(
        self,
        project_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Calculate academic-specific engagement metrics.
        
        Args:
            project_id: Project identifier
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary with academic metrics
        """
        try:
            event_filter = and_(
                AnalyticsEvent.project_id == project_id,
                AnalyticsEvent.timestamp >= start_date,
                AnalyticsEvent.timestamp <= end_date
            )

            # Academic event counts
            academic_events = {
                'abstract_views': EventType.ABSTRACT_VIEW,
                'pdf_downloads': EventType.PDF_DOWNLOAD,
                'bibtex_downloads': EventType.BIBTEX_DOWNLOAD,
                'citation_clicks': EventType.CITATION_CLICK,
                'figure_views': EventType.FIGURE_VIEW,
                'reference_clicks': EventType.REFERENCE_CLICK,
                'paper_shares': EventType.PAPER_SHARE
            }

            metrics = {}
            for metric_name, event_type in academic_events.items():
                result = await self.db.execute(
                    select(func.count(AnalyticsEvent.id))
                    .join(AnalyticsSession)
                    .where(
                        and_(
                            event_filter,
                            AnalyticsEvent.event_type == event_type,
                            AnalyticsSession.is_bot == False,
                            AnalyticsSession.do_not_track == False
                        )
                    )
                )
                metrics[metric_name] = result.scalar() or 0

            # Calculate conversion rates
            total_visitors = await self._get_unique_visitors_count(project_id, start_date, end_date)
            
            metrics['conversion_rates'] = {
                'abstract_to_pdf': (metrics['pdf_downloads'] / metrics['abstract_views'] * 100) 
                                   if metrics['abstract_views'] > 0 else 0,
                'visitor_to_pdf': (metrics['pdf_downloads'] / total_visitors * 100) 
                                  if total_visitors > 0 else 0,
                'pdf_to_citation': (metrics['citation_clicks'] / metrics['pdf_downloads'] * 100) 
                                   if metrics['pdf_downloads'] > 0 else 0,
                'visitor_to_citation': (metrics['citation_clicks'] / total_visitors * 100) 
                                       if total_visitors > 0 else 0
            }

            # Figure engagement analysis
            figure_engagement = await self._analyze_figure_engagement(project_id, start_date, end_date)
            metrics['figure_engagement'] = figure_engagement

            # Section popularity analysis
            section_popularity = await self._analyze_section_popularity(project_id, start_date, end_date)
            metrics['section_popularity'] = section_popularity

            # Download patterns
            download_patterns = await self._analyze_download_patterns(project_id, start_date, end_date)
            metrics['download_patterns'] = download_patterns

            return metrics

        except Exception as e:
            logger.error(f"Error calculating academic metrics: {e}")
            return {}

    async def calculate_engagement_metrics(
        self,
        project_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Calculate user engagement metrics.
        
        Args:
            project_id: Project identifier
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary with engagement metrics
        """
        try:
            # Scroll depth analysis
            scroll_depth_stats = await self._analyze_scroll_depth(project_id, start_date, end_date)
            
            # Time on page analysis
            time_on_page_stats = await self._analyze_time_on_page(project_id, start_date, end_date)
            
            # Content interaction patterns
            interaction_patterns = await self._analyze_interaction_patterns(project_id, start_date, end_date)
            
            # Exit points analysis
            exit_points = await self._analyze_exit_points(project_id, start_date, end_date)

            return {
                'scroll_depth': scroll_depth_stats,
                'time_on_page': time_on_page_stats,
                'interaction_patterns': interaction_patterns,
                'exit_points': exit_points
            }

        except Exception as e:
            logger.error(f"Error calculating engagement metrics: {e}")
            return {}

    async def calculate_geographic_metrics(
        self,
        project_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Calculate geographic distribution metrics.
        
        Args:
            project_id: Project identifier
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary with geographic metrics
        """
        try:
            session_filter = and_(
                AnalyticsSession.project_id == project_id,
                AnalyticsSession.first_visit >= start_date,
                AnalyticsSession.first_visit <= end_date,
                AnalyticsSession.is_bot == False,
                AnalyticsSession.do_not_track == False
            )

            # Country distribution
            country_result = await self.db.execute(
                select(
                    AnalyticsSession.country_code,
                    func.count(AnalyticsSession.id).label('visitor_count'),
                    func.sum(AnalyticsSession.page_views).label('page_views'),
                    func.avg(AnalyticsSession.session_duration).label('avg_duration')
                )
                .where(
                    and_(
                        session_filter,
                        AnalyticsSession.country_code.isnot(None)
                    )
                )
                .group_by(AnalyticsSession.country_code)
                .order_by(desc('visitor_count'))
            )

            countries = []
            total_visitors = 0
            for row in country_result.fetchall():
                countries.append({
                    'country_code': row.country_code,
                    'visitors': row.visitor_count,
                    'page_views': row.page_views or 0,
                    'avg_duration': row.avg_duration or 0
                })
                total_visitors += row.visitor_count

            # Calculate percentages
            for country in countries:
                country['percentage'] = (country['visitors'] / total_visitors * 100) if total_visitors > 0 else 0

            # Region distribution (top regions)
            region_result = await self.db.execute(
                select(
                    AnalyticsSession.region,
                    func.count(AnalyticsSession.id).label('visitor_count')
                )
                .where(
                    and_(
                        session_filter,
                        AnalyticsSession.region.isnot(None)
                    )
                )
                .group_by(AnalyticsSession.region)
                .order_by(desc('visitor_count'))
                .limit(20)
            )

            regions = [
                {
                    'region': row.region,
                    'visitors': row.visitor_count
                }
                for row in region_result.fetchall()
            ]

            # City distribution (top cities)
            city_result = await self.db.execute(
                select(
                    AnalyticsSession.city,
                    AnalyticsSession.country_code,
                    func.count(AnalyticsSession.id).label('visitor_count')
                )
                .where(
                    and_(
                        session_filter,
                        AnalyticsSession.city.isnot(None)
                    )
                )
                .group_by(AnalyticsSession.city, AnalyticsSession.country_code)
                .order_by(desc('visitor_count'))
                .limit(20)
            )

            cities = [
                {
                    'city': row.city,
                    'country_code': row.country_code,
                    'visitors': row.visitor_count
                }
                for row in city_result.fetchall()
            ]

            return {
                'countries': countries,
                'regions': regions,
                'cities': cities,
                'total_countries': len(countries),
                'geographic_diversity': self._calculate_geographic_diversity(countries)
            }

        except Exception as e:
            logger.error(f"Error calculating geographic metrics: {e}")
            return {}

    async def calculate_traffic_source_metrics(
        self,
        project_id: str,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """
        Calculate traffic source and referrer metrics.
        
        Args:
            project_id: Project identifier
            start_date: Start of date range
            end_date: End of date range
            
        Returns:
            Dictionary with traffic source metrics
        """
        try:
            session_filter = and_(
                AnalyticsSession.project_id == project_id,
                AnalyticsSession.first_visit >= start_date,
                AnalyticsSession.first_visit <= end_date,
                AnalyticsSession.is_bot == False,
                AnalyticsSession.do_not_track == False
            )

            # Traffic source distribution
            traffic_source_result = await self.db.execute(
                select(
                    AnalyticsSession.traffic_source,
                    func.count(AnalyticsSession.id).label('visitor_count'),
                    func.sum(AnalyticsSession.page_views).label('page_views'),
                    func.avg(AnalyticsSession.session_duration).label('avg_duration')
                )
                .where(session_filter)
                .group_by(AnalyticsSession.traffic_source)
                .order_by(desc('visitor_count'))
            )

            traffic_sources = []
            total_visitors = 0
            for row in traffic_source_result.fetchall():
                traffic_sources.append({
                    'source': row.traffic_source,
                    'visitors': row.visitor_count,
                    'page_views': row.page_views or 0,
                    'avg_duration': row.avg_duration or 0
                })
                total_visitors += row.visitor_count

            # Calculate percentages and quality metrics
            for source in traffic_sources:
                source['percentage'] = (source['visitors'] / total_visitors * 100) if total_visitors > 0 else 0
                source['pages_per_session'] = (source['page_views'] / source['visitors']) if source['visitors'] > 0 else 0

            # Referrer domain analysis
            referrer_result = await self.db.execute(
                select(
                    AnalyticsSession.referrer_domain,
                    AnalyticsSession.traffic_source,
                    func.count(AnalyticsSession.id).label('visitor_count'),
                    func.avg(AnalyticsSession.page_views).label('avg_pages'),
                    func.avg(AnalyticsSession.session_duration).label('avg_duration')
                )
                .where(
                    and_(
                        session_filter,
                        AnalyticsSession.referrer_domain.isnot(None)
                    )
                )
                .group_by(AnalyticsSession.referrer_domain, AnalyticsSession.traffic_source)
                .order_by(desc('visitor_count'))
                .limit(50)
            )

            referrers = [
                {
                    'domain': row.referrer_domain,
                    'source_type': row.traffic_source,
                    'visitors': row.visitor_count,
                    'avg_pages': row.avg_pages or 0,
                    'avg_duration': row.avg_duration or 0,
                    'quality_score': self._calculate_referrer_quality_score(
                        row.avg_pages or 0,
                        row.avg_duration or 0
                    )
                }
                for row in referrer_result.fetchall()
            ]

            # Academic platform analysis
            academic_referrers = [r for r in referrers if r['source_type'] == TrafficSource.ACADEMIC_PLATFORM]
            
            # UTM campaign analysis
            utm_analysis = await self._analyze_utm_campaigns(project_id, start_date, end_date)

            return {
                'traffic_sources': traffic_sources,
                'referrers': referrers,
                'academic_referrers': academic_referrers,
                'utm_campaigns': utm_analysis,
                'traffic_quality': self._analyze_traffic_quality(traffic_sources)
            }

        except Exception as e:
            logger.error(f"Error calculating traffic source metrics: {e}")
            return {}

    async def calculate_time_series_metrics(
        self,
        project_id: str,
        start_date: datetime,
        end_date: datetime,
        granularity: str = 'daily'
    ) -> Dict[str, Any]:
        """
        Calculate time-series metrics for trend analysis.
        
        Args:
            project_id: Project identifier
            start_date: Start of date range
            end_date: End of date range
            granularity: Time granularity ('hourly', 'daily', 'weekly', 'monthly')
            
        Returns:
            Dictionary with time-series data
        """
        try:
            if granularity == 'daily':
                return await self._calculate_daily_time_series(project_id, start_date, end_date)
            elif granularity == 'hourly':
                return await self._calculate_hourly_time_series(project_id, start_date, end_date)
            elif granularity == 'weekly':
                return await self._calculate_weekly_time_series(project_id, start_date, end_date)
            elif granularity == 'monthly':
                return await self._calculate_monthly_time_series(project_id, start_date, end_date)
            else:
                raise ValueError(f"Unsupported granularity: {granularity}")

        except Exception as e:
            logger.error(f"Error calculating time series metrics: {e}")
            return {}

    # Helper Methods
    async def _calculate_session_duration_stats(self, session_filter) -> Dict[str, Any]:
        """Calculate session duration statistics."""
        try:
            # Get all session durations
            duration_result = await self.db.execute(
                select(AnalyticsSession.session_duration)
                .where(
                    and_(
                        session_filter,
                        AnalyticsSession.session_duration > 0
                    )
                )
            )
            
            durations = [row[0] for row in duration_result.fetchall()]
            
            if not durations:
                return {
                    'avg_duration': 0,
                    'median_duration': 0,
                    'duration_distribution': {}
                }

            avg_duration = sum(durations) / len(durations)
            median_duration = statistics.median(durations)
            
            # Duration distribution buckets
            buckets = {
                '0-30s': 0,
                '30s-1m': 0,
                '1-5m': 0,
                '5-15m': 0,
                '15-30m': 0,
                '30m+': 0
            }
            
            for duration in durations:
                if duration <= 30:
                    buckets['0-30s'] += 1
                elif duration <= 60:
                    buckets['30s-1m'] += 1
                elif duration <= 300:
                    buckets['1-5m'] += 1
                elif duration <= 900:
                    buckets['5-15m'] += 1
                elif duration <= 1800:
                    buckets['15-30m'] += 1
                else:
                    buckets['30m+'] += 1

            return {
                'avg_duration': avg_duration,
                'median_duration': median_duration,
                'duration_distribution': buckets
            }

        except Exception as e:
            logger.error(f"Error calculating session duration stats: {e}")
            return {
                'avg_duration': 0,
                'median_duration': 0,
                'duration_distribution': {}
            }

    async def _get_unique_visitors_count(self, project_id: str, start_date: datetime, end_date: datetime) -> int:
        """Get unique visitors count for date range."""
        try:
            result = await self.db.execute(
                select(func.count(func.distinct(AnalyticsSession.id)))
                .where(
                    and_(
                        AnalyticsSession.project_id == project_id,
                        AnalyticsSession.first_visit >= start_date,
                        AnalyticsSession.first_visit <= end_date,
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
            )
            return result.scalar() or 0
        except Exception:
            return 0

    async def _analyze_figure_engagement(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze figure engagement patterns."""
        try:
            result = await self.db.execute(
                select(
                    AnalyticsEvent.figure_id,
                    func.count(AnalyticsEvent.id).label('view_count'),
                    func.count(func.distinct(AnalyticsEvent.session_id)).label('unique_viewers')
                )
                .join(AnalyticsSession)
                .where(
                    and_(
                        AnalyticsEvent.project_id == project_id,
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date,
                        AnalyticsEvent.event_type == EventType.FIGURE_VIEW,
                        AnalyticsEvent.figure_id.isnot(None),
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
                .group_by(AnalyticsEvent.figure_id)
                .order_by(desc('view_count'))
            )

            figures = [
                {
                    'figure_id': row.figure_id,
                    'views': row.view_count,
                    'unique_viewers': row.unique_viewers
                }
                for row in result.fetchall()
            ]

            return {
                'top_figures': figures[:10],
                'total_figure_views': sum(f['views'] for f in figures),
                'avg_views_per_figure': sum(f['views'] for f in figures) / len(figures) if figures else 0
            }

        except Exception as e:
            logger.error(f"Error analyzing figure engagement: {e}")
            return {}

    async def _analyze_section_popularity(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze paper section popularity."""
        try:
            result = await self.db.execute(
                select(
                    AnalyticsEvent.paper_section,
                    func.count(AnalyticsEvent.id).label('view_count'),
                    func.avg(AnalyticsEvent.duration).label('avg_time'),
                    func.avg(AnalyticsEvent.scroll_depth).label('avg_scroll')
                )
                .join(AnalyticsSession)
                .where(
                    and_(
                        AnalyticsEvent.project_id == project_id,
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date,
                        AnalyticsEvent.paper_section.isnot(None),
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
                .group_by(AnalyticsEvent.paper_section)
                .order_by(desc('view_count'))
            )

            sections = [
                {
                    'section': row.paper_section,
                    'views': row.view_count,
                    'avg_time': row.avg_time or 0,
                    'avg_scroll_depth': row.avg_scroll or 0
                }
                for row in result.fetchall()
            ]

            return {
                'sections': sections,
                'most_popular_section': sections[0]['section'] if sections else None,
                'engagement_scores': {
                    s['section']: (s['avg_time'] * s['avg_scroll_depth']) 
                    for s in sections
                }
            }

        except Exception as e:
            logger.error(f"Error analyzing section popularity: {e}")
            return {}

    async def _analyze_download_patterns(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze download patterns and timing."""
        try:
            # Download type distribution
            download_result = await self.db.execute(
                select(
                    AnalyticsEvent.download_type,
                    func.count(AnalyticsEvent.id).label('download_count'),
                    func.count(func.distinct(AnalyticsEvent.session_id)).label('unique_downloaders')
                )
                .join(AnalyticsSession)
                .where(
                    and_(
                        AnalyticsEvent.project_id == project_id,
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date,
                        AnalyticsEvent.event_type.in_([EventType.PDF_DOWNLOAD, EventType.BIBTEX_DOWNLOAD]),
                        AnalyticsEvent.download_type.isnot(None),
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
                .group_by(AnalyticsEvent.download_type)
                .order_by(desc('download_count'))
            )

            downloads = [
                {
                    'type': row.download_type,
                    'count': row.download_count,
                    'unique_users': row.unique_downloaders
                }
                for row in download_result.fetchall()
            ]

            return {
                'download_types': downloads,
                'total_downloads': sum(d['count'] for d in downloads)
            }

        except Exception as e:
            logger.error(f"Error analyzing download patterns: {e}")
            return {}

    async def _analyze_scroll_depth(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze scroll depth patterns."""
        try:
            result = await self.db.execute(
                select(
                    func.avg(AnalyticsEvent.scroll_depth).label('avg_scroll'),
                    func.percentile_cont(0.5).within_group(AnalyticsEvent.scroll_depth).label('median_scroll'),
                    func.count(AnalyticsEvent.id).label('total_events')
                )
                .join(AnalyticsSession)
                .where(
                    and_(
                        AnalyticsEvent.project_id == project_id,
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date,
                        AnalyticsEvent.scroll_depth.isnot(None),
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
            )

            row = result.first()
            if row:
                return {
                    'avg_scroll_depth': row.avg_scroll or 0,
                    'median_scroll_depth': row.median_scroll or 0,
                    'total_scroll_events': row.total_events or 0
                }
            else:
                return {
                    'avg_scroll_depth': 0,
                    'median_scroll_depth': 0,
                    'total_scroll_events': 0
                }

        except Exception as e:
            logger.error(f"Error analyzing scroll depth: {e}")
            return {}

    async def _analyze_time_on_page(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze time spent on pages."""
        try:
            result = await self.db.execute(
                select(
                    AnalyticsEvent.page_url,
                    func.avg(AnalyticsEvent.duration).label('avg_time'),
                    func.count(AnalyticsEvent.id).label('page_views')
                )
                .join(AnalyticsSession)
                .where(
                    and_(
                        AnalyticsEvent.project_id == project_id,
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date,
                        AnalyticsEvent.duration.isnot(None),
                        AnalyticsEvent.duration > 0,
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
                .group_by(AnalyticsEvent.page_url)
                .order_by(desc('avg_time'))
            )

            pages = [
                {
                    'url': row.page_url,
                    'avg_time': row.avg_time,
                    'page_views': row.page_views
                }
                for row in result.fetchall()
            ]

            return {
                'pages': pages[:20],  # Top 20 pages by time
                'overall_avg_time': sum(p['avg_time'] * p['page_views'] for p in pages) / sum(p['page_views'] for p in pages) if pages else 0
            }

        except Exception as e:
            logger.error(f"Error analyzing time on page: {e}")
            return {}

    async def _analyze_interaction_patterns(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze user interaction patterns."""
        try:
            # Click patterns
            click_result = await self.db.execute(
                select(
                    func.count(AnalyticsEvent.id).label('total_clicks')
                )
                .join(AnalyticsSession)
                .where(
                    and_(
                        AnalyticsEvent.project_id == project_id,
                        AnalyticsEvent.timestamp >= start_date,
                        AnalyticsEvent.timestamp <= end_date,
                        AnalyticsEvent.click_position_x.isnot(None),
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
            )

            total_clicks = click_result.scalar() or 0

            return {
                'total_interactions': total_clicks,
                'interaction_rate': total_clicks / (await self._get_unique_visitors_count(project_id, start_date, end_date)) if total_clicks > 0 else 0
            }

        except Exception as e:
            logger.error(f"Error analyzing interaction patterns: {e}")
            return {}

    async def _analyze_exit_points(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze where users exit the site."""
        try:
            # This is a simplified implementation
            # In practice, you'd analyze session patterns to determine exit pages
            return {
                'top_exit_pages': [],
                'exit_rate': 0
            }

        except Exception as e:
            logger.error(f"Error analyzing exit points: {e}")
            return {}

    async def _analyze_utm_campaigns(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analyze UTM campaign performance."""
        try:
            result = await self.db.execute(
                select(
                    AnalyticsSession.utm_source,
                    AnalyticsSession.utm_medium,
                    AnalyticsSession.utm_campaign,
                    func.count(AnalyticsSession.id).label('sessions'),
                    func.sum(AnalyticsSession.page_views).label('page_views')
                )
                .where(
                    and_(
                        AnalyticsSession.project_id == project_id,
                        AnalyticsSession.first_visit >= start_date,
                        AnalyticsSession.first_visit <= end_date,
                        AnalyticsSession.utm_source.isnot(None),
                        AnalyticsSession.is_bot == False,
                        AnalyticsSession.do_not_track == False
                    )
                )
                .group_by(
                    AnalyticsSession.utm_source,
                    AnalyticsSession.utm_medium,
                    AnalyticsSession.utm_campaign
                )
                .order_by(desc('sessions'))
            )

            campaigns = [
                {
                    'source': row.utm_source,
                    'medium': row.utm_medium,
                    'campaign': row.utm_campaign,
                    'sessions': row.sessions,
                    'page_views': row.page_views or 0
                }
                for row in result.fetchall()
            ]

            return {
                'campaigns': campaigns,
                'total_utm_sessions': sum(c['sessions'] for c in campaigns)
            }

        except Exception as e:
            logger.error(f"Error analyzing UTM campaigns: {e}")
            return {}

    def _calculate_geographic_diversity(self, countries: List[Dict]) -> float:
        """Calculate geographic diversity index."""
        try:
            if not countries:
                return 0.0
                
            total_visitors = sum(c['visitors'] for c in countries)
            if total_visitors == 0:
                return 0.0
                
            # Calculate Herfindahl-Hirschman Index for diversity
            hhi = sum((c['visitors'] / total_visitors) ** 2 for c in countries)
            diversity = 1 - hhi
            
            return diversity
            
        except Exception:
            return 0.0

    def _calculate_referrer_quality_score(self, avg_pages: float, avg_duration: float) -> float:
        """Calculate quality score for referrers based on engagement."""
        try:
            # Normalize and weight the metrics
            page_score = min(avg_pages / 5.0, 1.0) * 0.6  # Max score for 5+ pages
            duration_score = min(avg_duration / 300.0, 1.0) * 0.4  # Max score for 5+ minutes
            
            return (page_score + duration_score) * 100
            
        except Exception:
            return 0.0

    def _analyze_traffic_quality(self, traffic_sources: List[Dict]) -> Dict[str, Any]:
        """Analyze traffic quality by source."""
        try:
            quality_scores = {}
            
            for source in traffic_sources:
                if source['visitors'] > 0:
                    pages_per_session = source['page_views'] / source['visitors']
                    quality_scores[source['source']] = {
                        'pages_per_session': pages_per_session,
                        'avg_duration': source['avg_duration'],
                        'quality_score': self._calculate_referrer_quality_score(
                            pages_per_session,
                            source['avg_duration']
                        )
                    }
            
            return {
                'source_quality': quality_scores,
                'best_quality_source': max(quality_scores.keys(), 
                                         key=lambda x: quality_scores[x]['quality_score']) 
                                       if quality_scores else None
            }
            
        except Exception as e:
            logger.error(f"Error analyzing traffic quality: {e}")
            return {}

    async def _calculate_daily_time_series(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate daily time series data."""
        try:
            # Use pre-aggregated daily metrics if available
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

            daily_data = []
            for metrics in result.scalars():
                daily_data.append({
                    'date': metrics.date.isoformat(),
                    'unique_visitors': metrics.unique_visitors,
                    'page_views': metrics.total_page_views,
                    'pdf_downloads': metrics.pdf_downloads,
                    'avg_session_duration': metrics.avg_session_duration,
                    'bounce_rate': metrics.bounce_rate
                })

            return {
                'daily_data': daily_data,
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                }
            }

        except Exception as e:
            logger.error(f"Error calculating daily time series: {e}")
            return {}

    async def _calculate_hourly_time_series(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate hourly time series data."""
        # Implementation for hourly aggregation
        # This would be more complex and require real-time processing
        return {}

    async def _calculate_weekly_time_series(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate weekly time series data."""
        # Implementation for weekly aggregation
        return {}

    async def _calculate_monthly_time_series(self, project_id: str, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Calculate monthly time series data."""
        # Implementation for monthly aggregation
        return {}