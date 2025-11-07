"""String sanitization utilities for database operations."""

import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


def sanitize_string(value: str) -> str:
    """Remove NUL (0x00) characters from a string.
    
    PostgreSQL and other databases cannot store NUL characters in string fields.
    This function removes them while preserving other content.
    
    Args:
        value: The string to sanitize
        
    Returns:
        The sanitized string with NUL characters removed
    """
    if not isinstance(value, str):
        return value
    
    # Remove NUL characters
    sanitized = value.replace('\x00', '')
    
    if sanitized != value:
        logger.debug(f"Removed {value.count('\x00')} NUL character(s) from string")
    
    return sanitized


def sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize all string values in a dictionary.
    
    Args:
        data: The dictionary to sanitize
        
    Returns:
        A new dictionary with all strings sanitized
    """
    if not isinstance(data, dict):
        return data
    
    result = {}
    for key, value in data.items():
        # Sanitize the key itself
        sanitized_key = sanitize_string(key) if isinstance(key, str) else key
        
        # Sanitize the value based on its type
        if isinstance(value, str):
            result[sanitized_key] = sanitize_string(value)
        elif isinstance(value, dict):
            result[sanitized_key] = sanitize_dict(value)
        elif isinstance(value, list):
            result[sanitized_key] = sanitize_list(value)
        else:
            result[sanitized_key] = value
    
    return result


def sanitize_list(data: List[Any]) -> List[Any]:
    """Recursively sanitize all string values in a list.
    
    Args:
        data: The list to sanitize
        
    Returns:
        A new list with all strings sanitized
    """
    if not isinstance(data, list):
        return data
    
    result = []
    for item in data:
        if isinstance(item, str):
            result.append(sanitize_string(item))
        elif isinstance(item, dict):
            result.append(sanitize_dict(item))
        elif isinstance(item, list):
            result.append(sanitize_list(item))
        else:
            result.append(item)
    
    return result


def sanitize_file_data(file_data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize file data before database insertion.
    
    This function sanitizes all string fields in the file data dictionary,
    including metadata, keywords, and other nested structures.
    
    Args:
        file_data: The file data dictionary to sanitize
        
    Returns:
        A new dictionary with all strings sanitized
    """
    # Create a copy to avoid modifying the original
    sanitized = {}
    
    for key, value in file_data.items():
        if key == 'metadata' and isinstance(value, dict):
            # Recursively sanitize metadata
            sanitized[key] = sanitize_dict(value)
        elif key == 'keywords' and isinstance(value, list):
            # Sanitize keyword list
            sanitized[key] = sanitize_list(value)
        elif isinstance(value, str):
            # Sanitize string values
            sanitized[key] = sanitize_string(value)
        else:
            # Keep other values as-is
            sanitized[key] = value
    
    return sanitized
