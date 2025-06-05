#!/usr/bin/env python3
"""
Router Flagging System - Conscious-Mirror Flag Layer
===================================================

Extracts and processes conscious-mirror flags from prompts for
intelligent routing to specialized executors and agents.

Flags processed:
- FLAG_SYSCALL: System operations requiring elevated permissions
- FLAG_MATH: Mathematical computations and calculations
- FLAG_FILE: File system operations
- FLAG_NETWORK: Network requests and API calls
- FLAG_ANALYSIS: Code analysis and debugging
- FLAG_CREATIVE: Creative writing and content generation
"""

import re
import logging
from typing import List, Dict, Tuple, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class FlagType(Enum):
    """Supported conscious-mirror flag types"""
    SYSCALL = "FLAG_SYSCALL"
    MATH = "FLAG_MATH"
    FILE = "FLAG_FILE"
    NETWORK = "FLAG_NETWORK"
    ANALYSIS = "FLAG_ANALYSIS"
    CREATIVE = "FLAG_CREATIVE"

@dataclass
class FlagMatch:
    """Represents a detected flag in the prompt"""
    flag_type: FlagType
    confidence: float
    trigger_phrase: str
    position: int

class FlagExtractor:
    """Extracts conscious-mirror flags from prompts using regex patterns"""
    
    def __init__(self):
        # Define regex patterns for each flag type
        self.patterns = {
            FlagType.SYSCALL: [
                r'\b(?:install|sudo|chmod|systemctl|service|restart|kill|ps|top)\b',
                r'\b(?:system|kernel|process|daemon|service)\s+(?:operation|command|call)\b',
                r'\b(?:elevated|admin|root|superuser)\s+(?:access|permission|privilege)\b',
                r'\b(?:execute|run)\s+(?:command|script|binary)\b'
            ],
            
            FlagType.MATH: [
                r'\b(?:calculate|compute|solve|evaluate)\b',
                r'\b(?:\d+\s*[+\-*/]\s*\d+|mathematical|arithmetic|algebra|calculus)\b',
                r'\b(?:equation|formula|derivative|integral|probability)\b',
                r'\b(?:statistics|regression|correlation|variance)\b'
            ],
            
            FlagType.FILE: [
                r'\b(?:create|write|read|delete|copy|move)\s+(?:file|directory|folder)\b',
                r'\b(?:save|load|import|export)\s+(?:data|content|document)\b',
                r'\b(?:file|path|filename|extension)\s+(?:operation|manipulation)\b',
                r'\b(?:upload|download|sync|backup)\b'
            ],
            
            FlagType.NETWORK: [
                r'\b(?:http|https|api|request|response|endpoint)\b',
                r'\b(?:fetch|get|post|put|delete)\s+(?:data|resource)\b',
                r'\b(?:url|uri|domain|server|client)\b',
                r'\b(?:network|internet|web|socket|tcp|udp)\b'
            ],
            
            FlagType.ANALYSIS: [
                r'\b(?:debug|analyze|review|inspect|examine)\s+(?:code|script|program)\b',
                r'\b(?:refactor|optimize|improve|fix)\s+(?:implementation|logic)\b',
                r'\b(?:syntax|semantic|logical)\s+(?:error|issue|problem)\b',
                r'\b(?:performance|memory|cpu)\s+(?:analysis|profiling|optimization)\b'
            ],
            
            FlagType.CREATIVE: [
                r'\b(?:write|compose|create|generate)\s+(?:story|poem|article|content)\b',
                r'\b(?:creative|artistic|imaginative|original)\s+(?:writing|work|piece)\b',
                r'\b(?:brainstorm|ideate|conceptualize|design)\b',
                r'\b(?:marketing|advertising|copywriting|branding)\b'
            ]
        }
        
        # Compile patterns for efficiency
        self.compiled_patterns = {}
        for flag_type, patterns in self.patterns.items():
            self.compiled_patterns[flag_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
    
    def extract_flags(self, prompt: str) -> List[FlagMatch]:
        """Extract all flags from a prompt"""
        flags = []
        
        for flag_type, patterns in self.compiled_patterns.items():
            for pattern in patterns:
                matches = list(pattern.finditer(prompt))
                
                for match in matches:
                    # Calculate confidence based on match strength
                    confidence = self._calculate_confidence(match, prompt)
                    
                    flag_match = FlagMatch(
                        flag_type=flag_type,
                        confidence=confidence,
                        trigger_phrase=match.group(),
                        position=match.start()
                    )
                    flags.append(flag_match)
        
        # Remove duplicates and sort by confidence
        flags = self._deduplicate_flags(flags)
        flags.sort(key=lambda x: x.confidence, reverse=True)
        
        return flags
    
    def _calculate_confidence(self, match: re.Match, prompt: str) -> float:
        """Calculate confidence score for a flag match"""
        base_confidence = 0.7
        
        # Boost confidence for exact keyword matches
        if match.group().lower() in ['calculate', 'execute', 'create file', 'api request']:
            base_confidence += 0.2
        
        # Boost confidence for longer matches
        if len(match.group()) > 10:
            base_confidence += 0.1
        
        # Reduce confidence if match is part of a larger word
        start, end = match.span()
        if start > 0 and prompt[start-1].isalnum():
            base_confidence -= 0.1
        if end < len(prompt) and prompt[end].isalnum():
            base_confidence -= 0.1
        
        return min(base_confidence, 1.0)
    
    def _deduplicate_flags(self, flags: List[FlagMatch]) -> List[FlagMatch]:
        """Remove duplicate flags of the same type"""
        seen_types = set()
        deduplicated = []
        
        for flag in flags:
            if flag.flag_type not in seen_types:
                deduplicated.append(flag)
                seen_types.add(flag.flag_type)
        
        return deduplicated

class FlagRouter:
    """Routes requests based on detected flags"""
    
    def __init__(self):
        self.extractor = FlagExtractor()
        
        # Define routing rules for each flag type
        self.routing_rules = {
            FlagType.SYSCALL: {
                'executor': 'os_executor',
                'queue': 'swarm:exec:q',
                'priority': 'high',
                'requires_sandbox': True
            },
            FlagType.MATH: {
                'executor': 'math_specialist',
                'queue': 'swarm:math:q',
                'priority': 'medium',
                'requires_sandbox': False
            },
            FlagType.FILE: {
                'executor': 'file_handler',
                'queue': 'swarm:file:q',
                'priority': 'medium',
                'requires_sandbox': True
            },
            FlagType.NETWORK: {
                'executor': 'network_handler',
                'queue': 'swarm:network:q',
                'priority': 'medium',
                'requires_sandbox': False
            },
            FlagType.ANALYSIS: {
                'executor': 'code_analyzer',
                'queue': 'swarm:analysis:q',
                'priority': 'low',
                'requires_sandbox': False
            },
            FlagType.CREATIVE: {
                'executor': 'creative_agent',
                'queue': 'swarm:creative:q',
                'priority': 'low',
                'requires_sandbox': False
            }
        }
    
    def route_prompt(self, prompt: str, explicit_flags: List[str] = None) -> Dict:
        """Route a prompt based on detected and explicit flags"""
        # Extract flags from prompt
        detected_flags = self.extractor.extract_flags(prompt)
        
        # Combine with explicit flags
        all_flags = set()
        for flag_match in detected_flags:
            all_flags.add(flag_match.flag_type.value)
        
        if explicit_flags:
            for flag in explicit_flags:
                try:
                    flag_type = FlagType(flag)
                    all_flags.add(flag_type.value)
                except ValueError:
                    logger.warning(f"Unknown flag type: {flag}")
        
        # Determine routing
        routing_decision = self._make_routing_decision(list(all_flags))
        
        return {
            'detected_flags': [f.flag_type.value for f in detected_flags],
            'all_flags': list(all_flags),
            'routing': routing_decision,
            'confidence_scores': {f.flag_type.value: f.confidence for f in detected_flags}
        }
    
    def _make_routing_decision(self, flags: List[str]) -> Dict:
        """Make routing decision based on flags"""
        if not flags:
            return {
                'executor': 'default_agent',
                'queue': 'swarm:general:q',
                'priority': 'medium',
                'requires_sandbox': False
            }
        
        # Priority order for conflicting flags
        priority_order = [
            FlagType.SYSCALL,  # Highest priority
            FlagType.FILE,
            FlagType.NETWORK,
            FlagType.MATH,
            FlagType.ANALYSIS,
            FlagType.CREATIVE   # Lowest priority
        ]
        
        # Find highest priority flag
        for flag_type in priority_order:
            if flag_type.value in flags:
                return self.routing_rules[flag_type]
        
        # Fallback to first flag
        try:
            first_flag = FlagType(flags[0])
            return self.routing_rules[first_flag]
        except (ValueError, KeyError):
            return {
                'executor': 'default_agent',
                'queue': 'swarm:general:q',
                'priority': 'medium',
                'requires_sandbox': False
            }

# Global router instance
_flag_router = None

def get_flag_router() -> FlagRouter:
    """Get global flag router instance"""
    global _flag_router
    if _flag_router is None:
        _flag_router = FlagRouter()
        logger.info("🏁 Flag router initialized")
    return _flag_router

# Utility functions for integration
def extract_flags_from_prompt(prompt: str) -> List[str]:
    """Quick utility to extract flag strings from prompt"""
    router = get_flag_router()
    detected = router.extractor.extract_flags(prompt)
    return [f.flag_type.value for f in detected]

def should_route_to_executor(flags: List[str]) -> bool:
    """Check if flags require special executor routing"""
    executor_flags = {
        FlagType.SYSCALL.value,
        FlagType.FILE.value,
        FlagType.NETWORK.value
    }
    return bool(set(flags) & executor_flags)

# Test function
def test_flag_extraction():
    """Test flag extraction with sample prompts"""
    router = get_flag_router()
    
    test_cases = [
        "Calculate 2+2 and show the result",
        "Install nginx and restart the service",
        "Create a file called config.json with default settings",
        "Make an HTTP request to the API endpoint",
        "Debug this Python code for performance issues",
        "Write a creative story about space exploration"
    ]
    
    print("🏁 Testing Flag Extraction")
    print("=" * 50)
    
    for prompt in test_cases:
        result = router.route_prompt(prompt)
        print(f"\nPrompt: {prompt}")
        print(f"Flags: {result['detected_flags']}")
        print(f"Executor: {result['routing']['executor']}")
        print(f"Queue: {result['routing']['queue']}")

if __name__ == "__main__":
    test_flag_extraction() 