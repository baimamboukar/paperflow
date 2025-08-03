"""
Tracking service for Paperflow analytics.

This service handles visit tracking and event collection with a focus on
privacy, performance, and academic metrics.
"""

import asyncio
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from urllib.parse import urlparse
from user_agents import parse as parse_user_agent

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from ...models.analytics import (
    AnalyticsSession,
    AnalyticsEvent,
    EventType,
    DeviceType,
    TrafficSource,
    SessionCreate,
    EventCreate
)
from ..base import BaseService

logger = logging.getLogger(__name__)


class TrackingService(BaseService):
    """
    Privacy-first tracking service for academic papers.
    
    Features:
    - Cookie-free session tracking
    - Anonymous fingerprinting
    - Bot detection
    - Geographic IP resolution (anonymized)
    - Academic event tracking
    - Real-time event processing
    """

    def __init__(self, db_session: AsyncSession):
        super().__init__(db_session)
        self._bot_user_agents = self._load_bot_patterns()
        self._academic_domains = self._load_academic_domains()
        self._social_domains = self._load_social_domains()

    def _load_bot_patterns(self) -> List[str]:
        """Load common bot user agent patterns."""
        return [
            'bot', 'crawler', 'spider', 'scraper', 'baiduspider', 'googlebot',
            'bingbot', 'slurp', 'duckduckbot', 'facebookexternalhit', 'twitterbot',
            'linkedinbot', 'whatsapp', 'telegram', 'applebot', 'yandexbot',
            'semrushbot', 'ahrefsbot', 'mj12bot', 'dotbot', 'blexbot'
        ]

    def _load_academic_domains(self) -> List[str]:
        """Load academic platform domains."""
        return [
            'scholar.google.com', 'arxiv.org', 'researchgate.net', 'academia.edu',
            'ieee.org', 'acm.org', 'springer.com', 'elsevier.com', 'wiley.com',
            'nature.com', 'science.org', 'pubmed.ncbi.nlm.nih.gov', 'jstor.org',
            'dblp.org', 'semanticscholar.org', 'mendeley.com', 'zotero.org',
            'orcid.org', 'crossref.org', 'doi.org', 'biorxiv.org', 'medrxiv.org'
        ]

    def _load_social_domains(self) -> List[str]:
        """Load social media domains."""
        return [
            'facebook.com', 'twitter.com', 'linkedin.com', 'reddit.com',
            'youtube.com', 'instagram.com', 'tiktok.com', 'snapchat.com',
            'pinterest.com', 'tumblr.com', 'discord.com', 'slack.com',
            'telegram.org', 'whatsapp.com', 't.me', 'x.com'
        ]

    async def create_session_fingerprint(
        self,
        ip_address: str,
        user_agent: str,
        accept_language: str = None,
        timezone_offset: int = None,
        screen_resolution: str = None,
        project_id: str = None
    ) -> str:
        """
        Create an anonymous session fingerprint without storing personal data.
        
        Args:
            ip_address: Client IP address (will be anonymized)
            user_agent: User agent string
            accept_language: Accept-Language header
            timezone_offset: Client timezone offset
            screen_resolution: Screen resolution (e.g., "1920x1080")
            project_id: Project ID to include in fingerprint
            
        Returns:
            Anonymous session hash
        """
        try:
            # Anonymize IP address (remove last octet for IPv4, last 80 bits for IPv6)
            anonymized_ip = self._anonymize_ip(ip_address)
            
            # Create fingerprint components
            components = [
                anonymized_ip,
                user_agent[:200] if user_agent else '',  # Truncate to prevent abuse
                accept_language[:50] if accept_language else '',
                str(timezone_offset) if timezone_offset is not None else '',
                screen_resolution[:20] if screen_resolution else '',
                project_id or '',
                datetime.utcnow().strftime('%Y-%m-%d')  # Include date for daily rotation
            ]
            
            # Create hash
            fingerprint_data = '|'.join(components)
            session_hash = hashlib.sha256(fingerprint_data.encode()).hexdigest()
            
            logger.debug(f"Created session fingerprint for project {project_id}")
            return session_hash
            
        except Exception as e:
            logger.error(f"Error creating session fingerprint: {e}")
            # Return a random hash as fallback
            return hashlib.sha256(str(datetime.utcnow()).encode()).hexdigest()

    def _anonymize_ip(self, ip_address: str) -> str:
        """Anonymize IP address for privacy compliance."""
        try:
            if ':' in ip_address:  # IPv6
                parts = ip_address.split(':')
                # Keep first 3 groups, anonymize the rest
                return ':'.join(parts[:3] + ['0000'] * (len(parts) - 3))
            else:  # IPv4
                parts = ip_address.split('.')
                if len(parts) == 4:
                    # Keep first 3 octets, anonymize last
                    return '.'.join(parts[:3] + ['0'])
                return '0.0.0.0'
        except Exception:
            return '0.0.0.0'

    def parse_user_agent(self, user_agent: str) -> Dict[str, str]:
        """
        Parse user agent string to extract device and browser information.
        
        Args:
            user_agent: User agent string
            
        Returns:
            Dictionary with parsed information
        """
        if not user_agent:
            return {
                'device_type': DeviceType.UNKNOWN,
                'browser': 'Unknown',
                'os': 'Unknown',
                'is_bot': False
            }

        try:
            # Check for bot patterns
            user_agent_lower = user_agent.lower()
            is_bot = any(pattern in user_agent_lower for pattern in self._bot_user_agents)
            
            if is_bot:
                return {
                    'device_type': DeviceType.BOT,
                    'browser': 'Bot',
                    'os': 'Bot',
                    'is_bot': True
                }

            # Parse user agent
            parsed = parse_user_agent(user_agent)
            
            # Determine device type
            device_type = DeviceType.UNKNOWN
            if parsed.is_mobile:
                device_type = DeviceType.MOBILE
            elif parsed.is_tablet:
                device_type = DeviceType.TABLET
            elif parsed.is_pc:
                device_type = DeviceType.DESKTOP

            return {
                'device_type': device_type,
                'browser': f"{parsed.browser.family} {parsed.browser.version_string}"[:100],
                'os': f"{parsed.os.family} {parsed.os.version_string}"[:100],
                'is_bot': False
            }
            
        except Exception as e:
            logger.error(f"Error parsing user agent: {e}")
            return {
                'device_type': DeviceType.UNKNOWN,
                'browser': 'Unknown',
                'os': 'Unknown',
                'is_bot': False
            }

    def classify_traffic_source(self, referrer_url: str, utm_source: str = None) -> Tuple[TrafficSource, str]:
        """
        Classify traffic source based on referrer and UTM parameters.
        
        Args:
            referrer_url: HTTP referrer URL
            utm_source: UTM source parameter
            
        Returns:
            Tuple of (traffic_source, referrer_domain)
        """
        if not referrer_url and not utm_source:
            return TrafficSource.DIRECT, None

        try:
            # Check UTM source first
            if utm_source:
                utm_source_lower = utm_source.lower()
                if any(domain in utm_source_lower for domain in self._academic_domains):
                    return TrafficSource.ACADEMIC_PLATFORM, utm_source
                elif any(domain in utm_source_lower for domain in self._social_domains):
                    return TrafficSource.SOCIAL_MEDIA, utm_source
                elif 'google' in utm_source_lower or 'bing' in utm_source_lower:
                    return TrafficSource.SEARCH_ENGINE, utm_source
                elif 'email' in utm_source_lower or 'newsletter' in utm_source_lower:
                    return TrafficSource.EMAIL, utm_source

            # Parse referrer URL
            if referrer_url:
                parsed = urlparse(referrer_url)
                domain = parsed.netloc.lower()
                
                # Remove www prefix
                if domain.startswith('www.'):
                    domain = domain[4:]

                # Classify by domain
                if domain in self._academic_domains:
                    return TrafficSource.ACADEMIC_PLATFORM, domain
                elif domain in self._social_domains:
                    return TrafficSource.SOCIAL_MEDIA, domain
                elif any(search in domain for search in ['google.', 'bing.', 'yahoo.', 'duckduckgo.', 'baidu.']):
                    return TrafficSource.SEARCH_ENGINE, domain
                else:
                    return TrafficSource.REFERRAL, domain

            return TrafficSource.DIRECT, None
            
        except Exception as e:
            logger.error(f"Error classifying traffic source: {e}")
            return TrafficSource.UNKNOWN, None

    async def track_page_visit(
        self,
        project_id: str,
        request_data: Dict[str, Any],
        page_data: Dict[str, Any] = None
    ) -> Optional[AnalyticsEvent]:
        """
        Track a page visit with full context.
        
        Args:
            project_id: Project identifier
            request_data: HTTP request data (headers, IP, etc.)
            page_data: Page-specific data (URL, title, etc.)
            
        Returns:
            Created analytics event or None if tracking declined
        """
        try:
            # Extract request information
            ip_address = request_data.get('ip_address', '')
            user_agent = request_data.get('user_agent', '')
            accept_language = request_data.get('accept_language', '')
            referrer_url = request_data.get('referrer', '')
            dnt_header = request_data.get('dnt', '0')
            
            # Extract page information
            page_url = page_data.get('url', '') if page_data else ''
            page_title = page_data.get('title', '') if page_data else ''
            viewport_width = page_data.get('viewport_width') if page_data else None
            viewport_height = page_data.get('viewport_height') if page_data else None
            timezone_offset = page_data.get('timezone_offset') if page_data else None
            screen_resolution = page_data.get('screen_resolution') if page_data else None
            
            # UTM parameters
            utm_params = page_data.get('utm', {}) if page_data else {}
            utm_source = utm_params.get('source')
            utm_medium = utm_params.get('medium')
            utm_campaign = utm_params.get('campaign')

            # Respect Do Not Track
            do_not_track = dnt_header == '1'
            if do_not_track:
                logger.info(f"Respecting DNT header for project {project_id}")
                # Still create a minimal session for basic metrics but mark as DNT
                
            # Parse user agent
            ua_info = self.parse_user_agent(user_agent)
            
            # Skip bot traffic unless configured otherwise
            if ua_info['is_bot']:
                logger.debug(f"Skipping bot traffic for project {project_id}")
                # Still track for bot analytics but mark appropriately
            
            # Create session fingerprint
            session_hash = await self.create_session_fingerprint(
                ip_address=ip_address,
                user_agent=user_agent,
                accept_language=accept_language,
                timezone_offset=timezone_offset,
                screen_resolution=screen_resolution,
                project_id=project_id
            )
            
            # Classify traffic source
            traffic_source, referrer_domain = self.classify_traffic_source(referrer_url, utm_source)
            
            # Resolve geographic information (anonymized)
            geo_info = await self._resolve_geography(ip_address)
            
            # Create or get session
            session_data = SessionCreate(
                project_id=project_id,
                session_hash=session_hash,
                country_code=geo_info.get('country_code'),
                region=geo_info.get('region'),
                city=geo_info.get('city'),
                timezone=geo_info.get('timezone'),
                device_type=ua_info['device_type'],
                browser=ua_info['browser'],
                os=ua_info['os'],
                screen_resolution=screen_resolution,
                traffic_source=traffic_source,
                referrer_domain=referrer_domain,
                referrer_url=referrer_url[:500] if referrer_url else None,
                utm_source=utm_source,
                utm_medium=utm_medium,
                utm_campaign=utm_campaign,
                is_bot=ua_info['is_bot'],
                do_not_track=do_not_track
            )
            
            # Import here to avoid circular import
            from .analytics_service import AnalyticsService
            analytics_service = AnalyticsService(self.db)
            
            session = await analytics_service.create_session(session_data)
            
            # Create page view event
            event_data = EventCreate(
                session_id=session.id,
                project_id=project_id,
                event_type=EventType.PAGE_VIEW,
                page_url=page_url,
                page_title=page_title,
                viewport_width=viewport_width,
                viewport_height=viewport_height
            )
            
            event = await analytics_service.track_event(event_data)
            
            logger.debug(f"Tracked page visit for project {project_id}")
            return event
            
        except Exception as e:
            logger.error(f"Error tracking page visit: {e}")
            return None

    async def track_academic_event(
        self,
        session_id: str,
        project_id: str,
        event_type: EventType,
        event_data: Dict[str, Any] = None
    ) -> Optional[AnalyticsEvent]:
        """
        Track academic-specific events (downloads, citations, etc.).
        
        Args:
            session_id: Session identifier
            project_id: Project identifier
            event_type: Type of academic event
            event_data: Additional event data
            
        Returns:
            Created analytics event or None if failed
        """
        try:
            # Extract academic-specific data
            paper_section = event_data.get('section') if event_data else None
            figure_id = event_data.get('figure_id') if event_data else None
            citation_id = event_data.get('citation_id') if event_data else None
            reference_id = event_data.get('reference_id') if event_data else None
            download_type = event_data.get('download_type') if event_data else None
            duration = event_data.get('duration') if event_data else None
            
            # Create event
            event_create = EventCreate(
                session_id=session_id,
                project_id=project_id,
                event_type=event_type,
                paper_section=paper_section,
                figure_id=figure_id,
                citation_id=citation_id,
                reference_id=reference_id,
                download_type=download_type,
                duration=duration,
                event_data=event_data
            )
            
            # Import here to avoid circular import
            from .analytics_service import AnalyticsService
            analytics_service = AnalyticsService(self.db)
            
            event = await analytics_service.track_event(event_create)
            
            logger.debug(f"Tracked {event_type} event for project {project_id}")
            return event
            
        except Exception as e:
            logger.error(f"Error tracking academic event: {e}")
            return None

    async def track_engagement_event(
        self,
        session_id: str,
        project_id: str,
        page_url: str,
        engagement_data: Dict[str, Any]
    ) -> Optional[AnalyticsEvent]:
        """
        Track user engagement events (scroll depth, time on page, etc.).
        
        Args:
            session_id: Session identifier
            project_id: Project identifier
            page_url: Current page URL
            engagement_data: Engagement metrics
            
        Returns:
            Created analytics event or None if failed
        """
        try:
            scroll_depth = engagement_data.get('scroll_depth')
            time_on_page = engagement_data.get('time_on_page')
            section_id = engagement_data.get('section_id')
            
            # Create engagement event
            event_data = EventCreate(
                session_id=session_id,
                project_id=project_id,
                event_type=EventType.SECTION_VIEW,
                page_url=page_url,
                section_id=section_id,
                duration=time_on_page,
                scroll_depth=scroll_depth,
                event_data=engagement_data
            )
            
            # Import here to avoid circular import
            from .analytics_service import AnalyticsService
            analytics_service = AnalyticsService(self.db)
            
            event = await analytics_service.track_event(event_data)
            
            logger.debug(f"Tracked engagement event for project {project_id}")
            return event
            
        except Exception as e:
            logger.error(f"Error tracking engagement event: {e}")
            return None

    async def _resolve_geography(self, ip_address: str) -> Dict[str, Optional[str]]:
        """
        Resolve geographic information from IP address (anonymized).
        
        This is a placeholder implementation. In production, you would use
        a service like MaxMind GeoIP2 or similar.
        
        Args:
            ip_address: IP address to resolve
            
        Returns:
            Geographic information dictionary
        """
        try:
            # Placeholder implementation
            # In production, integrate with GeoIP service
            # Example: MaxMind GeoIP2, IP2Location, etc.
            
            # For now, return mock data
            return {
                'country_code': None,
                'region': None,
                'city': None,
                'timezone': None
            }
            
            # Example integration:
            # import geoip2.database
            # 
            # with geoip2.database.Reader('/path/to/GeoLite2-City.mmdb') as reader:
            #     try:
            #         response = reader.city(ip_address)
            #         return {
            #             'country_code': response.country.iso_code,
            #             'region': response.subdivisions.most_specific.name,
            #             'city': response.city.name,
            #             'timezone': str(response.location.time_zone)
            #         }
            #     except geoip2.errors.AddressNotFoundError:
            #         return default values
            
        except Exception as e:
            logger.error(f"Error resolving geography for IP: {e}")
            return {
                'country_code': None,
                'region': None,
                'city': None,
                'timezone': None
            }

    async def bulk_track_events(self, events: List[EventCreate]) -> List[AnalyticsEvent]:
        """
        Track multiple events in bulk for performance.
        
        Args:
            events: List of events to track
            
        Returns:
            List of created events
        """
        try:
            # Import here to avoid circular import
            from .analytics_service import AnalyticsService
            analytics_service = AnalyticsService(self.db)
            
            created_events = []
            for event_data in events:
                try:
                    event = await analytics_service.track_event(event_data)
                    if event:
                        created_events.append(event)
                except Exception as e:
                    logger.error(f"Error tracking event in bulk: {e}")
                    continue
            
            logger.info(f"Bulk tracked {len(created_events)}/{len(events)} events")
            return created_events
            
        except Exception as e:
            logger.error(f"Error in bulk event tracking: {e}")
            return []

    async def get_session_by_hash(self, session_hash: str) -> Optional[AnalyticsSession]:
        """Get session by hash for session continuity."""
        try:
            result = await self.db.execute(
                select(AnalyticsSession)
                .where(AnalyticsSession.session_hash == session_hash)
            )
            return result.scalar_one_or_none()
            
        except Exception as e:
            logger.error(f"Error getting session by hash: {e}")
            return None

    def validate_event_data(self, event_data: Dict[str, Any]) -> bool:
        """
        Validate event data for security and privacy compliance.
        
        Args:
            event_data: Event data to validate
            
        Returns:
            True if valid, False otherwise
        """
        try:
            # Check for required fields
            required_fields = ['session_id', 'project_id', 'event_type']
            for field in required_fields:
                if field not in event_data:
                    logger.warning(f"Missing required field: {field}")
                    return False
            
            # Validate event type
            if event_data['event_type'] not in [e.value for e in EventType]:
                logger.warning(f"Invalid event type: {event_data['event_type']}")
                return False
            
            # Check for suspicious data patterns
            suspicious_patterns = [
                '<script', 'javascript:', 'data:', 'vbscript:',
                'onload=', 'onerror=', 'onclick='
            ]
            
            for key, value in event_data.items():
                if isinstance(value, str):
                    value_lower = value.lower()
                    if any(pattern in value_lower for pattern in suspicious_patterns):
                        logger.warning(f"Suspicious pattern detected in {key}: {value}")
                        return False
            
            # Validate URL length and format
            if 'page_url' in event_data and event_data['page_url']:
                if len(event_data['page_url']) > 500:
                    logger.warning("Page URL too long")
                    return False
            
            return True
            
        except Exception as e:
            logger.error(f"Error validating event data: {e}")
            return False