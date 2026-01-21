"""
In-memory cache for AI lead analysis results.
Caches analysis results by contact_id to avoid redundant API calls.
"""
from typing import Optional, Dict, Any
import hashlib
import json

# In-memory cache: {contact_id: analysis_data}
_analysis_cache: Dict[int, Dict[str, Any]] = {}


def get_cached_analysis(contact_id: int) -> Optional[Dict[str, Any]]:
    """
    Get cached analysis for a contact if it exists.
    
    Args:
        contact_id: The contact ID to look up
        
    Returns:
        Cached analysis data or None if not found
    """
    return _analysis_cache.get(contact_id)


def cache_analysis(contact_id: int, analysis_data: Dict[str, Any]) -> None:
    """
    Cache analysis results for a contact.
    
    Args:
        contact_id: The contact ID
        analysis_data: The analysis data to cache
    """
    _analysis_cache[contact_id] = analysis_data


def clear_cache(contact_id: Optional[int] = None) -> None:
    """
    Clear cached analysis.
    
    Args:
        contact_id: If provided, clear only this contact's cache.
                   If None, clear all cached analyses.
    """
    if contact_id is not None:
        _analysis_cache.pop(contact_id, None)
    else:
        _analysis_cache.clear()


def get_cache_size() -> int:
    """Get the number of cached analyses."""
    return len(_analysis_cache)

