#!/usr/bin/env python3
"""
🚦 Council Traffic Controller
===========================

Gradual rollout controller for Council-in-the-Loop system.
Enables canary deployment with percentage-based traffic routing.
"""

import os
import hashlib
import time
from typing import Tuple

class CouncilTrafficController:
    """Controls what percentage of traffic gets council deliberation"""
    
    def __init__(self):
        self.traffic_percent = float(os.getenv("COUNCIL_TRAFFIC_PERCENT", "0"))
        self.council_enabled = os.getenv("SWARM_COUNCIL_ENABLED", "false").lower() == "true"
        self.deployment_id = os.getenv("DEPLOYMENT_ID", "default")
        
    def should_use_council(self, user_id: str = None, session_id: str = None) -> Tuple[bool, str]:
        """
        Determine if this request should use council based on traffic percentage
        
        Uses consistent hashing to ensure same user always gets same experience
        """
        
        if not self.council_enabled:
            return False, "council_disabled"
        
        if self.traffic_percent >= 100:
            return True, "full_rollout"
        
        if self.traffic_percent <= 0:
            return False, "canary_disabled"
        
        # Create consistent hash for user/session
        identifier = user_id or session_id or f"request_{int(time.time() * 1000)}"
        hash_input = f"{identifier}:{self.deployment_id}".encode()
        hash_value = int(hashlib.md5(hash_input).hexdigest()[:8], 16)
        
        # Convert to percentage (0-100)
        user_bucket = (hash_value % 100) + 1
        
        use_council = user_bucket <= self.traffic_percent
        reason = f"canary_{self.traffic_percent}%_bucket_{user_bucket}"
        
        return use_council, reason
    
    def get_status(self) -> dict:
        """Get current traffic controller status"""
        return {
            "council_enabled": self.council_enabled,
            "traffic_percent": self.traffic_percent,
            "deployment_id": self.deployment_id,
            "controller_active": self.traffic_percent > 0 and self.council_enabled
        }

# Global traffic controller
traffic_controller = CouncilTrafficController() 