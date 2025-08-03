"""
Author data model for Paperflow.

This module defines the Author model with proper validation and
serialization capabilities for academic paper authors.
"""

from typing import Optional
from pydantic import BaseModel, Field, HttpUrl, EmailStr, validator
import re


class Author(BaseModel):
    """
    Model representing a paper author.
    
    Contains all relevant information about an author including
    contact details, affiliations, and identifiers.
    """
    
    name: str = Field(..., description="Author's full name")
    affiliation: str = Field(..., description="Author's institutional affiliation") 
    email: Optional[EmailStr] = Field(default=None, description="Author's email address")
    url: Optional[HttpUrl] = Field(default=None, description="Author's personal or academic webpage")
    orcid: Optional[str] = Field(default=None, description="Author's ORCID identifier")
    
    class Config:
        """Pydantic configuration."""
        validate_assignment = True
        str_strip_whitespace = True
        
    @validator("name")
    def validate_name(cls, v):
        """Validate author name format."""
        if not v or len(v.strip()) < 2:
            raise ValueError("Author name must be at least 2 characters long")
        
        # Basic check for valid name characters
        if not re.match(r"^[a-zA-Z\s\.\-'áéíóúàèìòùâêîôûäëïöüñç]+$", v):
            raise ValueError("Author name contains invalid characters")
        
        return v.strip()
    
    @validator("affiliation")
    def validate_affiliation(cls, v):
        """Validate affiliation format."""
        if not v or len(v.strip()) < 2:
            raise ValueError("Affiliation must be at least 2 characters long")
        
        return v.strip()
    
    @validator("orcid")
    def validate_orcid(cls, v):
        """Validate ORCID format."""
        if v is None:
            return v
        
        # Remove any ORCID URL prefix if present
        orcid_id = v.replace("https://orcid.org/", "").replace("http://orcid.org/", "")
        
        # ORCID format: 0000-0000-0000-0000
        orcid_pattern = r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"
        
        if not re.match(orcid_pattern, orcid_id):
            raise ValueError(
                "ORCID must be in format 0000-0000-0000-0000 or 0000-0000-0000-000X"
            )
        
        return orcid_id
    
    def get_orcid_url(self) -> Optional[str]:
        """Get the full ORCID URL."""
        if self.orcid:
            return f"https://orcid.org/{self.orcid}"
        return None
    
    def get_display_name(self) -> str:
        """Get formatted display name."""
        return self.name
    
    def get_citation_name(self) -> str:
        """
        Get name formatted for citations.
        
        Returns name in "Last, First" format for bibliography entries.
        """
        parts = self.name.split()
        if len(parts) <= 1:
            return self.name
        
        # Assume last part is surname, everything else is given names
        given_names = " ".join(parts[:-1])
        surname = parts[-1]
        
        return f"{surname}, {given_names}"
    
    def to_bibtex_author(self) -> str:
        """Convert to BibTeX author format."""
        return self.get_citation_name()
    
    def to_dict(self) -> dict:
        """Convert to dictionary with all fields."""
        data = self.dict(exclude_none=True)
        
        # Add computed fields
        if self.orcid:
            data["orcid_url"] = self.get_orcid_url()
        
        data["citation_name"] = self.get_citation_name()
        
        return data