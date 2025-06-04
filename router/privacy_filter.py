# -*- coding: utf-8 -*-
"""
Privacy Filter Module for SwarmAI Router
"""

import re
from typing import Dict, Any, List, Tuple


def apply_privacy_policy(prompt: str, response: str = None) -> Tuple[str, Dict[str, Any]]:
    """
    Apply privacy policies to filter out sensitive information
    
    Args:
        prompt: The input prompt to filter
        response: Optional response text to filter
        
    Returns:
        (filtered_text, metadata): Filtered text and metadata about what was filtered
    """
    metadata = {
        "patterns_found": [],
        "redacted_count": 0,
        "privacy_score": 1.0
    }
    
    # Define privacy patterns to detect and filter
    privacy_patterns = [
        (r'\b\d{3}-\d{2}-\d{4}\b', '[SSN_REDACTED]', 'ssn'),  # Social Security Numbers
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]', 'email'),  # Email addresses
        (r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b', '[CREDIT_CARD_REDACTED]', 'credit_card'),  # Credit card numbers
        (r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE_REDACTED]', 'phone'),  # Phone numbers
        (r'\b(?:API|api)[_\s]*(?:KEY|key)[_\s]*:?\s*[A-Za-z0-9_-]{20,}\b', '[API_KEY_REDACTED]', 'api_key'),  # API keys
        (r'\b[A-Z]{2}\d{9}\b', '[ID_NUMBER_REDACTED]', 'id_number'),  # Government ID patterns
    ]
    
    filtered_prompt = prompt
    
    # Apply privacy filters to prompt
    for pattern, replacement, pattern_type in privacy_patterns:
        matches = re.findall(pattern, filtered_prompt)
        if matches:
            metadata["patterns_found"].append(pattern_type)
            metadata["redacted_count"] += len(matches)
            filtered_prompt = re.sub(pattern, replacement, filtered_prompt)
    
    # Apply same filters to response if provided
    filtered_response = response
    if response:
        for pattern, replacement, pattern_type in privacy_patterns:
            matches = re.findall(pattern, filtered_response)
            if matches:
                if pattern_type not in metadata["patterns_found"]:
                    metadata["patterns_found"].append(pattern_type)
                metadata["redacted_count"] += len(matches)
                filtered_response = re.sub(pattern, replacement, filtered_response)
    
    # Calculate privacy score (lower if more patterns found)
    if metadata["redacted_count"] > 0:
        metadata["privacy_score"] = max(0.1, 1.0 - (metadata["redacted_count"] * 0.1))
    
    # Return filtered prompt if no response, otherwise return filtered response
    result_text = filtered_response if response else filtered_prompt
    
    return result_text, metadata


def check_privacy_compliance(text: str) -> Dict[str, Any]:
    """
    Check if text complies with privacy policies without modifying it
    
    Args:
        text: Text to check for privacy compliance
        
    Returns:
        Dict with compliance status and details
    """
    _, metadata = apply_privacy_policy(text)
    
    compliance_status = {
        "is_compliant": len(metadata["patterns_found"]) == 0,
        "risk_level": "low" if len(metadata["patterns_found"]) == 0 else "high",
        "detected_patterns": metadata["patterns_found"],
        "redacted_count": metadata["redacted_count"],
        "privacy_score": metadata["privacy_score"]
    }
    
    return compliance_status


def get_privacy_summary() -> Dict[str, Any]:
    """
    Get summary of privacy filter capabilities
    
    Returns:
        Dict with privacy filter information
    """
    return {
        "version": "1.0.0",
        "supported_patterns": [
            "social_security_numbers",
            "email_addresses", 
            "credit_card_numbers",
            "phone_numbers",
            "api_keys",
            "government_ids"
        ],
        "redaction_enabled": True,
        "compliance_mode": "strict"
    } 