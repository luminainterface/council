#!/usr/bin/env python3
"""
Router Cascade - AutoGen Integration
====================================

Fast query routing system that directs queries to the right specialist skill
in ~1ms using lightweight pattern matching and confidence scoring.
"""

import asyncio
import time
import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

# Import all our skill modules
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'skills'))

from lightning_math import solve_math, LightningMathAgent
from prolog_logic import solve_logic, PrologLogicAgent
from deepseek_coder import generate_code, DeepSeekCoderAgent
from faiss_rag import retrieve_knowledge, FAISSRAGAgent

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import AutoGen (optional)
try:
    from autogen_core import Agent, MessageContext
    AUTOGEN_AVAILABLE = True
except ImportError:
    AUTOGEN_AVAILABLE = False

class SkillType(Enum):
    MATH = "math"
    LOGIC = "logic"
    CODE = "code"
    KNOWLEDGE = "knowledge"
    UNKNOWN = "unknown"

class MockResponseError(Exception):
    """Raised when a mock/template response is detected instead of real AI generation"""
    def __init__(self, response_text: str, skill_type: str):
        self.response_text = response_text
        self.skill_type = skill_type
        super().__init__(f"Mock response detected in {skill_type}: {response_text[:100]}...")

class CloudRetry(Exception):
    """Raised when cloud fallback is needed due to template stubs or failures"""
    def __init__(self, reason: str):
        self.reason = reason
        super().__init__(f"Cloud retry needed: {reason}")

@dataclass
class RoutingDecision:
    skill_type: SkillType
    confidence: float
    reasoning: str
    route_time_ms: float

@dataclass
class QueryRoute:
    skill_type: str
    confidence: float
    patterns_matched: list

class RouterCascade:
    """Fast cascade router for AutoGen skills"""
    
    def __init__(self):
        self.agents = {}
        self.routing_patterns = self._build_routing_patterns()
        self._initialize_agents()
        
        # Performance tracking
        self.route_count = 0
        self.total_route_time = 0.0
        
        # Enhanced routing patterns with better coverage and FIXED PRIORITY
        self.routing_patterns = {
            "math": [
                # Strong math indicators - ⚡ ENHANCED factorial routing
                {"pattern": r"\d+\s*factorial|\d+!|factorial", "confidence": 0.95, "keywords": ["factorial"]},
                {"pattern": r"implement.*factorial.*function|factorial.*function|create.*factorial|write.*factorial", "confidence": 0.99, "keywords": ["factorial function"]},  # ⚡ FIX: Maximum confidence for factorial functions
                {"pattern": r"factorial.*implementation|factorial.*calculation", "confidence": 0.98, "keywords": ["factorial implementation"]},  # ⚡ FIX: Factorial implementation
                {"pattern": r"calculate.*factorial|compute.*factorial|find.*factorial", "confidence": 0.97, "keywords": ["factorial calculation"]},  # ⚡ FIX: Factorial calculation
                {"pattern": r"what.*factorial|factorial.*of", "confidence": 0.96, "keywords": ["factorial question"]},  # ⚡ FIX: Factorial questions
                {"pattern": r"\d+\s*\^\s*\d+|\d+\s*\*\*\s*\d+", "confidence": 0.95, "keywords": ["exponent", "power"]},
                {"pattern": r"calculate|compute|solve", "confidence": 0.90, "keywords": ["calculate", "compute", "solve"]},
                {"pattern": r"\d+\s*%\s*of\s*\d+|percentage", "confidence": 0.90, "keywords": ["percentage", "percent"]},
                {"pattern": r"gcd|lcm|greatest common divisor|least common multiple", "confidence": 0.95, "keywords": ["gcd", "lcm"]},
                {"pattern": r"area|perimeter|circumference|radius", "confidence": 0.85, "keywords": ["area", "perimeter", "geometry"]},
                {"pattern": r"square root|sqrt", "confidence": 0.90, "keywords": ["sqrt", "root"]},
                {"pattern": r"\blog\b|\blogarithm\b|\bln\b", "confidence": 0.90, "keywords": ["logarithm"]},  # Word boundaries for logarithm
                {"pattern": r"what\s+is\s+\d+", "confidence": 0.80, "keywords": ["arithmetic"]},
                {"pattern": r"\d+\s*[\+\-\*\/]\s*\d+", "confidence": 0.85, "keywords": ["arithmetic"]},
                {"pattern": r"triangle|circle|rectangle", "confidence": 0.75, "keywords": ["geometry"]},
                {"pattern": r"what\s+is.*\b(square root|sqrt|factorial|gcd|lcm|\blog\b|\blogarithm\b)\b", "confidence": 0.95, "keywords": ["specific math"]},  # Specific math questions
            ],
            "logic": [
                r'\b(if\s+.*\s+then|implies|therefore)\b',
                r'\b(south|north|east|west|above|below|left|right)\b',
                r'\b(spatial|relation|family|parent|child)\b',
                r'\b(all\s+.*\s+are|some\s+.*\s+are)\b',
                r'\b(syllogism|premise|conclusion)\b',
            ],
            "code": [
                r'\b(function|def|class|import|return)\b',
                r'\b(algorithm|sort|search|recursive)\b',
                r'\b(write\s+.*\s+code|implement|program)\b',
                r'\b(python|javascript|java|c\+\+|api)\b',
                r'\b(list|tuple|array|dictionary|data structure)\b',
                r'\b(version control|git|rest|restful)\b',
            ],
            "knowledge": [
                # Knowledge queries - MORE RESTRICTIVE to avoid conflicts
                {"pattern": r"what\s+is\s+(?!.*\b(square root|sqrt|factorial|gcd|lcm|\blog\b|\blogarithm\b|\d+.*[\+\-\*\/\^]))", "confidence": 0.50, "keywords": ["definition"]},  # Very restrictive
                {"pattern": r"who\s+wrote|who\s+is|who\s+was", "confidence": 0.80, "keywords": ["person"]},
                {"pattern": r"speed\s+of\s+light|machine\s+learning|photosynthesis", "confidence": 0.85, "keywords": ["scientific facts"]},
                {"pattern": r"explain.*(?!.*(square root|sqrt|factorial|algorithm))", "confidence": 0.40, "keywords": ["explanation"]},  # Exclude math/code terms
                {"pattern": r"capital\s+of|history\s+of", "confidence": 0.75, "keywords": ["geography", "history"]},
                {"pattern": r"dna|quantum|internet|artificial intelligence", "confidence": 0.80, "keywords": ["science", "technology"]},
            ]
        }
        
        # Mock response detection patterns
        self.mock_patterns = [
            r"I'm not sure which specialist",
            r"unknown\.\.\.",
            r"Unsupported.*problem",
            r"Based on the knowledge base: The human brain",  # Wrong knowledge retrieval
            r"According to the available information: DNA.*carries genetic", # Wrong knowledge
        ]
        
    def _build_routing_patterns(self) -> Dict[SkillType, List[Dict[str, Any]]]:
        """Build routing patterns with better math detection"""
        return {
            SkillType.MATH: [
                # Strong math indicators - ⚡ ENHANCED factorial routing
                {"pattern": r"\d+\s*factorial|\d+!|factorial", "confidence": 0.95, "keywords": ["factorial"]},
                {"pattern": r"implement.*factorial.*function|factorial.*function|create.*factorial|write.*factorial", "confidence": 0.99, "keywords": ["factorial function"]},  # ⚡ FIX: Maximum confidence for factorial functions
                {"pattern": r"factorial.*implementation|factorial.*calculation", "confidence": 0.98, "keywords": ["factorial implementation"]},  # ⚡ FIX: Factorial implementation
                {"pattern": r"calculate.*factorial|compute.*factorial|find.*factorial", "confidence": 0.97, "keywords": ["factorial calculation"]},  # ⚡ FIX: Factorial calculation
                {"pattern": r"what.*factorial|factorial.*of", "confidence": 0.96, "keywords": ["factorial question"]},  # ⚡ FIX: Factorial questions
                {"pattern": r"\d+\s*\^\s*\d+|\d+\s*\*\*\s*\d+", "confidence": 0.95, "keywords": ["exponent", "power"]},
                {"pattern": r"calculate|compute|solve", "confidence": 0.90, "keywords": ["calculate", "compute", "solve"]},
                {"pattern": r"\d+\s*%\s*of\s*\d+|percentage", "confidence": 0.90, "keywords": ["percentage", "percent"]},
                {"pattern": r"gcd|lcm|greatest common divisor|least common multiple", "confidence": 0.95, "keywords": ["gcd", "lcm"]},
                {"pattern": r"area|perimeter|circumference|radius", "confidence": 0.85, "keywords": ["area", "perimeter", "geometry"]},
                {"pattern": r"square root|sqrt", "confidence": 0.90, "keywords": ["sqrt", "root"]},
                {"pattern": r"\blog\b|\blogarithm\b|\bln\b", "confidence": 0.90, "keywords": ["logarithm"]},  # Word boundaries for logarithm
                {"pattern": r"what\s+is\s+\d+", "confidence": 0.80, "keywords": ["arithmetic"]},
                {"pattern": r"\d+\s*[\+\-\*\/]\s*\d+", "confidence": 0.85, "keywords": ["arithmetic"]},
                {"pattern": r"triangle|circle|rectangle", "confidence": 0.75, "keywords": ["geometry"]},
                {"pattern": r"what\s+is.*\b(square root|sqrt|factorial|gcd|lcm|\blog\b|\blogarithm\b)\b", "confidence": 0.95, "keywords": ["specific math"]},  # Specific math questions
            ],
            SkillType.CODE: [
                # Strong code indicators
                {"pattern": r"write.*function|create.*function|implement.*function", "confidence": 0.95, "keywords": ["function"]},
                {"pattern": r"function to.*|function.*calculate|function.*compute", "confidence": 0.98, "keywords": ["function generation"]},  # Very high for function requests
                {"pattern": r"python.*gcd|python.*function|python.*algorithm", "confidence": 0.97, "keywords": ["python code"]},  # Python-specific requests
                {"pattern": r"create.*function.*for|function.*for.*", "confidence": 0.96, "keywords": ["function creation"]},  # Create function for X
                {"pattern": r"implement.*algorithm", "confidence": 0.95, "keywords": ["algorithm implementation"]},  # Implement algorithm
                {"pattern": r"algorithm|sort|search", "confidence": 0.90, "keywords": ["algorithm", "sort", "search"]},
                {"pattern": r"function to|def |class ", "confidence": 0.85, "keywords": ["code", "programming"]},
                {"pattern": r"python|javascript|java|c\+\+", "confidence": 0.80, "keywords": ["programming language"]},
                {"pattern": r"binary search|bubble sort|quicksort|mergesort", "confidence": 0.95, "keywords": ["algorithm"]},
                {"pattern": r"fibonacci|palindrome|prime", "confidence": 0.80, "keywords": ["programming problem"]},
                {"pattern": r"reverse|count|check if", "confidence": 0.70, "keywords": ["string manipulation"]},
            ],
            SkillType.LOGIC: [
                # ⚡ FIX: Stronger logic indicators with higher weights
                {"pattern": r"if.*then|if all.*are|if some.*are", "confidence": 0.95, "keywords": ["logical reasoning"]},
                {"pattern": r"\b(therefore|thus|hence|consequently)\b", "confidence": 0.90, "keywords": ["logical conclusion"]},
                {"pattern": r"\b(syllogism|premise|conclusion|implies)\b", "confidence": 0.85, "keywords": ["formal logic"]},
                {"pattern": r"\b(either\s+.*\s+or|neither\s+.*\s+nor)\b", "confidence": 0.80, "keywords": ["logical operators"]},
                {"pattern": r"north|south|east|west|above|below", "confidence": 0.85, "keywords": ["spatial reasoning"]},
                {"pattern": r"true|false|yes|no.*question", "confidence": 0.75, "keywords": ["boolean logic"]},
                {"pattern": r"all.*are|some.*are|no.*are", "confidence": 0.80, "keywords": ["categorical logic"]},
                {"pattern": r"taller than|older than|younger than", "confidence": 0.85, "keywords": ["comparative logic"]},  # Boost comparative
                {"pattern": r"parent|child|family", "confidence": 0.70, "keywords": ["relationship"]},
                {"pattern": r"who.*tallest|who.*oldest|who.*youngest", "confidence": 0.85, "keywords": ["comparative questions"]},  # Who is tallest
            ],
            SkillType.KNOWLEDGE: [
                # Knowledge queries - MORE RESTRICTIVE to avoid conflicts
                {"pattern": r"what\s+is\s+(?!.*\b(square root|sqrt|factorial|gcd|lcm|\blog\b|\blogarithm\b|\d+.*[\+\-\*\/\^]))", "confidence": 0.50, "keywords": ["definition"]},  # Very restrictive
                {"pattern": r"who\s+wrote|who\s+is|who\s+was", "confidence": 0.80, "keywords": ["person"]},
                {"pattern": r"speed\s+of\s+light|machine\s+learning|photosynthesis", "confidence": 0.85, "keywords": ["scientific facts"]},
                {"pattern": r"explain.*(?!.*(square root|sqrt|factorial|algorithm))", "confidence": 0.40, "keywords": ["explanation"]},  # Exclude math/code terms
                {"pattern": r"capital\s+of|history\s+of", "confidence": 0.75, "keywords": ["geography", "history"]},
                {"pattern": r"dna|quantum|internet|artificial intelligence", "confidence": 0.80, "keywords": ["science", "technology"]},
            ]
        }
    
    def _initialize_agents(self):
        """Initialize AutoGen skill agents"""
        if not AUTOGEN_AVAILABLE:
            print("⚠️ Skills not available, router will use mock responses")
            return
            
        try:
            # Initialize all specialist agents
            self.agents[SkillType.MATH] = LightningMathAgent()
            self.agents[SkillType.LOGIC] = PrologLogicAgent()
            self.agents[SkillType.CODE] = DeepSeekCoderAgent()
            self.agents[SkillType.KNOWLEDGE] = FAISSRAGAgent()
            
            print(f"✅ Router initialized with {len(self.agents)} specialist agents")
            
        except Exception as e:
            print(f"⚠️ Agent initialization failed: {e}")
            self.agents = {}
    
    def classify_query(self, query: str) -> QueryRoute:
        """Classify query using weighted pattern matching"""
        query_lower = query.lower()
        skill_scores = {}
        matched_patterns = {}
        
        # ⚡ FIX: Use weighted scoring instead of simple counting
        for skill_type in SkillType:
            if skill_type == SkillType.UNKNOWN:
                continue
                
            patterns = self._build_routing_patterns().get(skill_type, [])
            total_confidence = 0.0
            matches = []
            
            for pattern_info in patterns:
                pattern = pattern_info["pattern"]
                confidence = pattern_info["confidence"]
                
                if re.search(pattern, query_lower, re.IGNORECASE):
                    total_confidence += confidence
                    matches.append(pattern)
            
            if total_confidence > 0:
                skill_scores[skill_type.value] = total_confidence
                matched_patterns[skill_type.value] = matches
        
        if not skill_scores:
            return QueryRoute("knowledge", 0.1, [])  # Default fallback
        
        # Get the skill with highest weighted score
        best_skill = max(skill_scores.items(), key=lambda x: x[1])
        return QueryRoute(
            skill_type=best_skill[0],
            confidence=best_skill[1], 
            patterns_matched=matched_patterns.get(best_skill[0], [])
        )
    
    def _check_for_mock_response(self, response_text: str, skill_type: str) -> None:
        """Check if response is a mock/template and raise error if so"""
        for pattern in self.mock_patterns:
            if re.search(pattern, response_text, re.IGNORECASE):
                raise MockResponseError(response_text, skill_type)
        
        # Additional checks for specific skill types
        if skill_type == "math" and "DNA" in response_text:
            raise MockResponseError(response_text, skill_type)
        
        if skill_type == "code" and "DNA" in response_text:
            raise MockResponseError(response_text, skill_type)
            
        if response_text.strip() == "unknown...":
            raise MockResponseError(response_text, skill_type)
    
    async def route_query(self, query: str) -> Dict[str, Any]:
        """Route query to appropriate specialist with mock detection"""
        start_time = time.time()
        
        # Classify the query
        route = self.classify_query(query)
        logger.info(f"🎯 Routing to {route.skill_type} (confidence: {route.confidence:.2f})")
        
        try:
            # Route to appropriate skill
            if route.skill_type == "math":
                logger.info(f"📊 Calling solve_math with query: {query}")
                result = await solve_math(query)
                logger.info(f"📊 solve_math returned: {result}")
                response_text = result.get("answer", str(result))
                logger.info(f"📊 Extracted response_text: {response_text}")
                
                # ⚡ FIX: Check for "unsupported" responses from math and trigger cloud retry
                if ("unsupported" in response_text.lower() or 
                    "unknown" in response_text.lower() or
                    response_text.startswith("Unsupported")):
                    raise CloudRetry(f"Math skill returned unsupported response: {response_text}")
                
            elif route.skill_type == "logic":
                result = await solve_logic(query)
                response_text = result.get("answer", str(result))
                
            elif route.skill_type == "code":
                result = await generate_code(query)
                response_text = result.get("code", str(result))
                
            elif route.skill_type == "knowledge":
                # Call knowledge skill
                print(f"📚 Calling retrieve_knowledge with query: {query}")
                response_data = await retrieve_knowledge(query)
                print(f"📚 retrieve_knowledge returned: {response_data}")
                
                # ⚡ FIX: Extract the actual response text from the knowledge result
                if isinstance(response_data, dict):
                    response_text = response_data.get("response", str(response_data))
                else:
                    response_text = str(response_data)
                
                print(f"📚 Extracted response_text: {response_text}")
                
                # Check for mock responses
                self._check_for_mock_response(response_text, "knowledge")
                
                return {
                    "text": response_text,
                    "skill_type": "knowledge", 
                    "model": "faiss-rag",
                    "confidence": response_data.get("confidence", 0.5) if isinstance(response_data, dict) else 0.5
                }
            else:
                raise ValueError(f"Unknown skill type: {route.skill_type}")
            
            latency_ms = (time.time() - start_time) * 1000
            
            return {
                "text": response_text,
                "skill_type": route.skill_type,
                "confidence": route.confidence,
                "latency_ms": latency_ms,
                "patterns_matched": route.patterns_matched,
                "model": f"autogen-{route.skill_type}",
                "timestamp": time.time()
            }
            
        except MockResponseError as e:
            logger.error(f"🚨 Mock response detected: {e}")
            # Re-raise to trigger cloud fallback or proper error handling
            raise
            
        except CloudRetry as e:
            logger.error(f"☁️ Cloud retry triggered: {e}")
            # Re-raise to trigger cloud fallback
            raise
            
        except Exception as e:
            logger.error(f"❌ Error in {route.skill_type} skill: {e}")
            # Don't mask real errors as successes
            raise
    
    async def execute_query(self, query: str) -> Dict[str, Any]:
        """Route and execute query with the appropriate specialist"""
        # Route the query
        routing = self.route_query(query)
        
        if routing.skill_type == SkillType.UNKNOWN:
            return {
                "answer": "I'm not sure which specialist can best handle this query.",
                "confidence": 0.1,
                "skill_type": "unknown",
                "route_time_ms": routing.route_time_ms,
                "reasoning": routing.reasoning
            }
        
        # Execute with appropriate specialist
        try:
            start_time = time.time()
            
            if routing.skill_type == SkillType.MATH:
                result = await solve_math(query)
                answer = result.get("answer", "Math calculation failed")
                confidence = result.get("confidence", 0.5)
                
            elif routing.skill_type == SkillType.LOGIC:
                result = await solve_logic(query)
                answer = result.get("answer", "Logic reasoning failed")
                confidence = result.get("confidence", 0.5)
                
            elif routing.skill_type == SkillType.CODE:
                result = await generate_code(query)
                answer = result.get("code", "Code generation failed")
                confidence = result.get("confidence", 0.5)
                
            elif routing.skill_type == SkillType.KNOWLEDGE:
                result = await retrieve_knowledge(query)
                answer = result.get("response", "Knowledge retrieval failed")
                confidence = result.get("confidence", 0.5)
                
            else:
                answer = "Unknown skill type"
                confidence = 0.1
            
            execution_time = (time.time() - start_time) * 1000
            
            return {
                "answer": answer,
                "confidence": confidence,
                "skill_type": routing.skill_type.value,
                "route_time_ms": routing.route_time_ms,
                "execution_time_ms": execution_time,
                "total_time_ms": routing.route_time_ms + execution_time,
                "reasoning": routing.reasoning
            }
            
        except Exception as e:
            return {
                "answer": f"Execution failed: {e}",
                "confidence": 0.0,
                "skill_type": routing.skill_type.value,
                "route_time_ms": routing.route_time_ms,
                "execution_time_ms": 0.0,
                "total_time_ms": routing.route_time_ms,
                "reasoning": f"Error: {e}",
                "error": str(e)
            }
    
    def get_performance_stats(self) -> Dict[str, float]:
        """Get router performance statistics"""
        if self.route_count == 0:
            return {"avg_route_time_ms": 0.0, "total_routes": 0}
        
        return {
            "avg_route_time_ms": self.total_route_time / self.route_count,
            "total_routes": self.route_count,
            "total_route_time_ms": self.total_route_time
        }

# Singleton router instance
_router_instance = None

def get_router() -> RouterCascade:
    """Get singleton router instance"""
    global _router_instance
    if _router_instance is None:
        _router_instance = RouterCascade()
    return _router_instance

async def route_and_execute(query: str) -> Dict[str, Any]:
    """Main interface for routing and executing queries"""
    router = get_router()
    return await router.execute_query(query)

# Test function
async def test_router_cascade():
    """Test the router cascade functionality"""
    print("🚦 Testing Router Cascade")
    print("=" * 50)
    
    test_cases = [
        ("What is 8 factorial?", SkillType.MATH),
        ("Write a function to add two numbers", SkillType.CODE),
        ("If A is south of B and B south of C, where is A?", SkillType.LOGIC),
        ("What is the speed of light?", SkillType.KNOWLEDGE),
        ("Hello world", SkillType.UNKNOWN),  # Should route to unknown
    ]
    
    router = RouterCascade()
    
    for i, (query, expected_skill) in enumerate(test_cases, 1):
        print(f"\n🔸 Test {i}: {query}")
        
        # Test routing decision
        routing = router.route_query(query)
        print(f"   Routed to: {routing.skill_type}")
        print(f"   Confidence: {routing.confidence:.2f}")
        print(f"   Route time: {routing.route_time_ms:.2f}ms")
        print(f"   Reasoning: {routing.reasoning}")
        
        # Verify expected routing
        route_correct = "✅" if routing.skill_type == expected_skill else "❌"
        print(f"   Expected: {expected_skill.value} {route_correct}")
        
        # Test full execution (for first few)
        if i <= 3:
            print(f"   Executing...")
            result = await router.execute_query(query)
            print(f"   Answer: {result['answer'][:60]}...")
            print(f"   Total time: {result['total_time_ms']:.2f}ms")
    
    # Performance stats
    stats = router.get_performance_stats()
    print(f"\n📊 Performance Stats:")
    print(f"   Average route time: {stats['avg_route_time_ms']:.2f}ms")
    print(f"   Total routes: {stats['total_routes']}")
    
    target_time = 1.0  # 1ms target
    meets_target = "✅" if stats['avg_route_time_ms'] <= target_time else "❌"
    print(f"   Meets 1ms target: {meets_target}")

if __name__ == "__main__":
    asyncio.run(test_router_cascade()) 