"""
Authentication-related schemas for Paperflow API.

This module provides request and response models for authentication
and authorization operations.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, validator

from .base import APIResponse


class AuthProvider(str, Enum):
    """Authentication provider enumeration."""

    LOCAL = "local"
    GITHUB = "github"
    GOOGLE = "google"
    ORCID = "orcid"
    OVERLEAF = "overleaf"


class UserRole(str, Enum):
    """User role enumeration."""

    USER = "user"
    ADMIN = "admin"
    MODERATOR = "moderator"


class TokenType(str, Enum):
    """Token type enumeration."""

    ACCESS = "access"
    REFRESH = "refresh"
    API_KEY = "api_key"
    WEBHOOK = "webhook"


class AuthScope(str, Enum):
    """Authentication scope enumeration."""

    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    PROJECTS = "projects"
    SYNC = "sync"
    BUILD = "build"
    TEMPLATES = "templates"


class UserInfo(BaseModel):
    """User information."""

    id: str = Field(..., description="Unique user identifier")
    username: str = Field(..., description="Username")
    email: str = Field(..., description="Email address")
    full_name: Optional[str] = Field(None, description="Full name")
    avatar_url: Optional[str] = Field(None, description="Avatar URL")
    role: UserRole = Field(UserRole.USER, description="User role")
    
    # Profile information
    bio: Optional[str] = Field(None, description="User biography")
    location: Optional[str] = Field(None, description="User location")
    website: Optional[str] = Field(None, description="Personal website")
    
    # Academic information
    orcid: Optional[str] = Field(None, description="ORCID identifier")
    affiliation: Optional[str] = Field(None, description="Academic affiliation")
    
    # Account status
    active: bool = Field(True, description="Whether account is active")
    verified: bool = Field(False, description="Whether email is verified")
    
    # Timestamps
    created_at: datetime = Field(..., description="Account creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    last_login: Optional[datetime] = Field(None, description="Last login timestamp")
    
    # Preferences
    preferences: Dict[str, Any] = Field(
        default_factory=dict, description="User preferences"
    )


class LoginRequest(BaseModel):
    """Login request schema."""

    provider: AuthProvider = Field(..., description="Authentication provider")
    username: Optional[str] = Field(None, description="Username (for local auth)")
    email: Optional[str] = Field(None, description="Email (for local auth)")
    password: Optional[str] = Field(None, description="Password (for local auth)")
    
    # OAuth fields
    code: Optional[str] = Field(None, description="OAuth authorization code")
    state: Optional[str] = Field(None, description="OAuth state parameter")
    redirect_uri: Optional[str] = Field(None, description="OAuth redirect URI")
    
    # Additional options
    remember_me: bool = Field(False, description="Remember login")
    scopes: List[AuthScope] = Field(
        default_factory=list, description="Requested scopes"
    )

    @validator("username", "email")
    def validate_credentials(cls, v, values):
        """Validate that required credentials are provided."""
        provider = values.get("provider")
        if provider == AuthProvider.LOCAL:
            if not v and not values.get("password"):
                raise ValueError("Username/email and password required for local auth")
        return v


class RegisterRequest(BaseModel):
    """User registration request."""

    username: str = Field(..., description="Desired username")
    email: str = Field(..., description="Email address")
    password: str = Field(..., description="Password")
    full_name: Optional[str] = Field(None, description="Full name")
    
    # Optional profile information
    bio: Optional[str] = Field(None, description="User biography")
    location: Optional[str] = Field(None, description="User location")
    website: Optional[str] = Field(None, description="Personal website")
    orcid: Optional[str] = Field(None, description="ORCID identifier")
    affiliation: Optional[str] = Field(None, description="Academic affiliation")
    
    # Terms and conditions
    accept_terms: bool = Field(..., description="Accept terms and conditions")
    
    # Newsletter subscription
    subscribe_newsletter: bool = Field(False, description="Subscribe to newsletter")

    @validator("username")
    def validate_username(cls, v):
        """Validate username."""
        if len(v) < 3:
            raise ValueError("Username must be at least 3 characters long")
        if len(v) > 50:
            raise ValueError("Username cannot exceed 50 characters")
        
        import re
        if not re.match(r"^[a-zA-Z0-9_-]+$", v):
            raise ValueError(
                "Username can only contain letters, numbers, hyphens, and underscores"
            )
        return v

    @validator("email")
    def validate_email(cls, v):
        """Validate email format."""
        import re
        if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
            raise ValueError("Invalid email format")
        return v

    @validator("password")
    def validate_password(cls, v):
        """Validate password strength."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        if len(v) > 128:
            raise ValueError("Password cannot exceed 128 characters")
        
        # Check for at least one uppercase, lowercase, and digit
        import re
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        
        return v

    @validator("accept_terms")
    def validate_terms(cls, v):
        """Validate terms acceptance."""
        if not v:
            raise ValueError("You must accept the terms and conditions")
        return v


class PasswordResetRequest(BaseModel):
    """Password reset request."""

    email: str = Field(..., description="Email address")


class PasswordResetConfirm(BaseModel):
    """Password reset confirmation."""

    token: str = Field(..., description="Reset token")
    new_password: str = Field(..., description="New password")

    @validator("new_password")
    def validate_password(cls, v):
        """Validate new password."""
        # Reuse validation from RegisterRequest
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class PasswordChange(BaseModel):
    """Password change request."""

    current_password: str = Field(..., description="Current password")
    new_password: str = Field(..., description="New password")


class EmailVerificationRequest(BaseModel):
    """Email verification request."""

    email: str = Field(..., description="Email address to verify")


class EmailVerificationConfirm(BaseModel):
    """Email verification confirmation."""

    token: str = Field(..., description="Verification token")


class TokenInfo(BaseModel):
    """Token information."""

    token: str = Field(..., description="Token value")
    token_type: TokenType = Field(..., description="Token type")
    expires_at: Optional[datetime] = Field(None, description="Token expiration")
    scopes: List[AuthScope] = Field(
        default_factory=list, description="Token scopes"
    )
    created_at: datetime = Field(..., description="Token creation timestamp")
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")


class AuthToken(BaseModel):
    """Authentication token response."""

    access_token: str = Field(..., description="Access token")
    refresh_token: Optional[str] = Field(None, description="Refresh token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    scope: str = Field(..., description="Token scope")


class APIKeyCreate(BaseModel):
    """API key creation request."""

    name: str = Field(..., description="API key name")
    description: Optional[str] = Field(None, description="API key description")
    scopes: List[AuthScope] = Field(
        default_factory=list, description="API key scopes"
    )
    expires_at: Optional[datetime] = Field(None, description="Expiration date")


class APIKey(BaseModel):
    """API key information."""

    id: str = Field(..., description="API key ID")
    name: str = Field(..., description="API key name")
    description: Optional[str] = Field(None, description="API key description")
    key_preview: str = Field(..., description="Key preview (first few characters)")
    scopes: List[AuthScope] = Field(..., description="API key scopes")
    active: bool = Field(..., description="Whether key is active")
    
    # Usage statistics
    last_used: Optional[datetime] = Field(None, description="Last usage timestamp")
    usage_count: int = Field(0, description="Usage count")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")


class SessionInfo(BaseModel):
    """Session information."""

    session_id: str = Field(..., description="Session ID")
    user_id: str = Field(..., description="User ID")
    ip_address: str = Field(..., description="IP address")
    user_agent: str = Field(..., description="User agent")
    active: bool = Field(..., description="Whether session is active")
    
    # Timestamps
    created_at: datetime = Field(..., description="Session creation timestamp")
    last_activity: datetime = Field(..., description="Last activity timestamp")
    expires_at: datetime = Field(..., description="Session expiration timestamp")


class OAuthProvider(BaseModel):
    """OAuth provider configuration."""

    provider: AuthProvider = Field(..., description="Provider name")
    enabled: bool = Field(..., description="Whether provider is enabled")
    client_id: str = Field(..., description="OAuth client ID")
    scopes: List[str] = Field(..., description="OAuth scopes")
    authorize_url: str = Field(..., description="Authorization URL")
    token_url: str = Field(..., description="Token URL")
    user_info_url: str = Field(..., description="User info URL")


class UserProfile(BaseModel):
    """User profile information."""

    user: UserInfo = Field(..., description="User information")
    connected_providers: List[AuthProvider] = Field(
        ..., description="Connected OAuth providers"
    )
    api_keys: List[APIKey] = Field(..., description="User API keys")
    active_sessions: List[SessionInfo] = Field(
        ..., description="Active sessions"
    )
    
    # Statistics
    projects_count: int = Field(0, description="Number of projects")
    builds_count: int = Field(0, description="Number of builds")
    syncs_count: int = Field(0, description="Number of syncs")
    
    # Activity
    last_activity: Optional[datetime] = Field(None, description="Last activity")
    login_count: int = Field(0, description="Total login count")


class UserUpdate(BaseModel):
    """User profile update request."""

    full_name: Optional[str] = Field(None, description="Full name")
    bio: Optional[str] = Field(None, description="User biography")
    location: Optional[str] = Field(None, description="User location")
    website: Optional[str] = Field(None, description="Personal website")
    orcid: Optional[str] = Field(None, description="ORCID identifier")
    affiliation: Optional[str] = Field(None, description="Academic affiliation")
    preferences: Optional[Dict[str, Any]] = Field(
        None, description="User preferences"
    )


class AuthAuditLog(BaseModel):
    """Authentication audit log entry."""

    id: str = Field(..., description="Log entry ID")
    user_id: Optional[str] = Field(None, description="User ID (if authenticated)")
    action: str = Field(..., description="Action performed")
    provider: Optional[AuthProvider] = Field(None, description="Auth provider used")
    ip_address: str = Field(..., description="IP address")
    user_agent: str = Field(..., description="User agent")
    success: bool = Field(..., description="Whether action was successful")
    error: Optional[str] = Field(None, description="Error message if failed")
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )
    timestamp: datetime = Field(..., description="Action timestamp")


# Response schemas
class LoginResponse(APIResponse):
    """Response for login operations."""

    data: AuthToken


class RegisterResponse(APIResponse):
    """Response for registration."""

    data: UserInfo


class UserProfileResponse(APIResponse):
    """Response for user profile."""

    data: UserProfile


class APIKeyResponse(APIResponse):
    """Response for API key operations."""

    data: APIKey


class APIKeyListResponse(APIResponse):
    """Response for API key listing."""

    data: List[APIKey]


class SessionListResponse(APIResponse):
    """Response for session listing."""

    data: List[SessionInfo]


class OAuthProvidersResponse(APIResponse):
    """Response for OAuth providers."""

    data: List[OAuthProvider]


class AuthAuditLogResponse(APIResponse):
    """Response for auth audit logs."""

    data: List[AuthAuditLog]