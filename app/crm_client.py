"""CRM API Client for 30apps integration."""

import httpx
from typing import Optional
from app.config import get_settings


class CRMClient:
    """Client for interacting with the CRM API."""
    
    def __init__(self):
        settings = get_settings()
        self.base_url = settings.crm_base_url
        self.api_key = settings.api_key
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
    
    async def get_contacts(
        self,
        company: Optional[str] = None,
        state: Optional[str] = None,
        industry: Optional[str] = None,
        per_page: int = 15,
        page: int = 1,
    ) -> dict:
        """
        List all contacts with optional filtering and pagination.
        
        Args:
            company: Filter by company name (partial match)
            state: Filter by state code (e.g., "CA", "NY")
            industry: Filter by industry (partial match)
            per_page: Number of results per page (default: 15, max: 100)
            page: Page number (default: 1)
            
        Returns:
            dict: API response with contacts data
        """
        params = {
            "per_page": min(per_page, 100),
            "page": page,
        }
        
        if company:
            params["company"] = company
        if state:
            params["state"] = state
        if industry:
            params["industry"] = industry
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/contacts",
                headers=self.headers,
                params=params,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
    
    async def get_contact(self, contact_id: int) -> dict:
        """
        Get detailed information about a specific contact.
        
        Args:
            contact_id: The contact's ID
            
        Returns:
            dict: Contact details with aggregated counts
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/contacts/{contact_id}",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
    
    async def get_contact_messages(self, contact_id: int) -> dict:
        """
        Get social media posts and blog posts for a specific contact.
        
        Args:
            contact_id: The contact's ID
            
        Returns:
            dict: Messages/posts data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/contacts/{contact_id}/messages",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()
    
    async def get_contact_events(self, contact_id: int) -> dict:
        """
        Get events attended by a specific contact.
        
        Args:
            contact_id: The contact's ID
            
        Returns:
            dict: Events data
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/contacts/{contact_id}/events",
                headers=self.headers,
                timeout=30.0,
            )
            response.raise_for_status()
            return response.json()


# Global client instance
crm_client = CRMClient()

