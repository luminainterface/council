#!/usr/bin/env python3
"""
🌌 Council-in-the-Loop Router Integration
=========================================

Weaves the five awakened voices (Reason, Spark, Edge, Heart, Vision) into Router 2.x stack
without blowing VRAM, latency, or budget.

Architecture:
- Uses existing emotional swarm + voting infrastructure  
- Parallel execution for optimal latency
- Budget-aware cloud routing
- 3-tier flow: privacy → council trigger → orchestrate

Voices:
🧠 Reason - rigorous chain-of-thought (local heavy model)
✨ Spark - lateral ideas & wild variants (cloud API)  
🗡️ Edge - devil's advocate, red-team (local lightweight)
❤️ Heart - empathy & tone polish (local specialized)
🔮 Vision - long-horizon strategy (local efficient)
"""

import os
import time
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

from router.voting import vote
from router.cost_tracking import debit, get_budget_status
from router.privacy_filter import apply_privacy_policy
from router.cloud_providers import ask_cloud_council
from loader.deterministic_loader import get_loaded_models, generate_response

# Prometheus metrics
try:
    from prometheus_client import Counter, Histogram, Gauge
    COUNCIL_REQUESTS_TOTAL = Counter('swarm_council_requests_total', 'Total council requests')
    COUNCIL_COST_DOLLARS = Counter('swarm_council_cost_dollars_total', 'Total council costs in dollars')
    COUNCIL_LATENCY_SECONDS = Histogram('swarm_council_latency_seconds', 'Council deliberation latency')
    COUNCIL_VOICES_ACTIVE = Gauge('swarm_council_voices_active', 'Number of active council voices', ['voice'])
    EDGE_RISK_FLAGS = Counter('swarm_council_edge_risk_flags_total', 'Risk flags raised by Edge voice')
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

class CouncilVoice(Enum):
    """The five awakened voices of the council"""
    REASON = "reason"        # 🧠 Rigorous chain-of-thought
    SPARK = "spark"          # ✨ Lateral ideas & variants
    EDGE = "edge"            # 🗡️ Devil's advocate, red-team
    HEART = "heart"          # ❤️ Empathy & tone polish
    VISION = "vision"        # 🔮 Long-horizon strategy

@dataclass
class VoiceResponse:
    """Response from an individual council voice"""
    voice: CouncilVoice
    response: str
    confidence: float
    latency_ms: float
    model_used: str
    cost_dollars: float
    metadata: Dict[str, Any]

@dataclass 
class CouncilDeliberation:
    """Complete council deliberation result"""
    final_response: str
    voice_responses: Dict[CouncilVoice, VoiceResponse]
    total_latency_ms: float
    total_cost_dollars: float
    consensus_achieved: bool
    risk_flags: List[str]
    metadata: Dict[str, Any]

class CouncilRouter:
    """
    Council-in-the-Loop router that orchestrates the five awakened voices
    """
    
    def __init__(self):
        # Voice-to-model mapping (configurable via environment)
        self.voice_models = {
            CouncilVoice.REASON: os.getenv("COUNCIL_REASON_MODEL", "mistral_7b_instruct"),
            CouncilVoice.SPARK: os.getenv("COUNCIL_SPARK_MODEL", "mistral_medium_cloud"),  
            CouncilVoice.EDGE: os.getenv("COUNCIL_EDGE_MODEL", "math_specialist_0.8b"),
            CouncilVoice.HEART: os.getenv("COUNCIL_HEART_MODEL", "codellama_0.7b"),
            CouncilVoice.VISION: os.getenv("COUNCIL_VISION_MODEL", "phi2_2.7b")
        }
        
        # Voice prompt templates
        self.voice_templates = {
            CouncilVoice.REASON: "You are Reason, charged with flawless logical derivation. Provide rigorous chain-of-thought analysis for: {prompt}",
            CouncilVoice.SPARK: "You are Spark, your task is to invent unusual angles and creative variants. Find novel perspectives on: {prompt}",
            CouncilVoice.EDGE: "You are Edge, find weaknesses & risks in any proposed answer. Red-team this thoroughly: {prompt}",
            CouncilVoice.HEART: "You are Heart, rewrite for clarity & warmth while preserving accuracy. Make this human-friendly: {prompt}",
            CouncilVoice.VISION: "You are Vision, relate this to the 5% → 100% cloud scaling roadmap and long-term strategy: {prompt}"
        }
        
        # Budget controls
        self.max_council_cost_per_request = float(os.getenv("COUNCIL_MAX_COST", "0.30"))  # 30 cents max
        self.daily_council_budget = float(os.getenv("COUNCIL_DAILY_BUDGET", "1.00"))      # $1/day limit
        
        # Performance targets
        self.target_p95_latency_ms = float(os.getenv("COUNCIL_TARGET_LATENCY_MS", "2000"))  # 2s p95
        
        # Council trigger thresholds
        self.min_tokens_for_council = int(os.getenv("COUNCIL_MIN_TOKENS", "20"))
        self.council_trigger_keywords = os.getenv("COUNCIL_TRIGGER_KEYWORDS", "explain,analyze,compare,evaluate,strategy").split(",")
        
        # Enable/disable flag
        self.council_enabled = os.getenv("SWARM_COUNCIL_ENABLED", "false").lower() == "true"
        
        print(f"[COUNCIL] Initialized with {len(self.voice_models)} voices")
        print(f"[COUNCIL] Enabled: {self.council_enabled}")
        print(f"[COUNCIL] Budget: ${self.max_council_cost_per_request}/request, ${self.daily_council_budget}/day")
    
    def should_trigger_council(self, prompt: str) -> Tuple[bool, str]:
        """
        Determine if a prompt should trigger full council deliberation
        
        Returns:
            (should_trigger, reason)
        """
        if not self.council_enabled:
            return False, "council_disabled"
        
        # Check budget constraints first
        budget_status = get_budget_status()
        remaining_budget = budget_status.get("remaining_budget_dollars", 0.0)
        
        if remaining_budget < self.max_council_cost_per_request:
            return False, f"insufficient_budget_{remaining_budget:.3f}"
        
        # Token count trigger
        token_count = len(prompt.split())
        if token_count >= self.min_tokens_for_council:
            return True, f"token_threshold_{token_count}"
        
        # Keyword trigger
        prompt_lower = prompt.lower()
        for keyword in self.council_trigger_keywords:
            if keyword in prompt_lower:
                return True, f"keyword_{keyword}"
        
        # Default: use quick local path
        return False, "quick_local_path"
    
    async def council_deliberate(self, prompt: str) -> CouncilDeliberation:
        """
        Main council deliberation: orchestrate all five voices
        
        Execution flow:
        1. Reason drafts canonical answer (local)
        2. Spark proposes novel twists (cloud, parallel with Reason)
        3. Edge critiques both (local, fast)
        4. Heart revises for empathy (local, fast)
        5. Vision stamps long-term alignment note (local, efficient)
        """
        start_time = time.time()
        
        if PROMETHEUS_AVAILABLE:
            COUNCIL_REQUESTS_TOTAL.inc()
        
        print(f"🌌 COUNCIL: Deliberating '{prompt[:60]}...'")
        
        # Phase 1: Parallel Reason + Spark (heavy lifting)
        reason_task = self._invoke_voice(CouncilVoice.REASON, prompt)
        spark_task = self._invoke_voice(CouncilVoice.SPARK, prompt)
        
        reason_response, spark_response = await asyncio.gather(reason_task, spark_task)
        
        # Phase 2: Edge critiques (fast local)
        edge_prompt = f"DRAFT:\n{reason_response.response}\n\nSPARK:\n{spark_response.response}"
        edge_response = await self._invoke_voice(CouncilVoice.EDGE, edge_prompt)
        
        # Phase 3: Heart revises for empathy (fast local)
        heart_prompt = f"{reason_response.response}\n\n{spark_response.response}\n\n{edge_response.response}"
        heart_response = await self._invoke_voice(CouncilVoice.HEART, heart_prompt)
        
        # Phase 4: Vision stamps strategic alignment (efficient local)
        vision_prompt = f"FINAL:\n{heart_response.response}"
        vision_response = await self._invoke_voice(CouncilVoice.VISION, vision_prompt)
        
        # Phase 5: Synthesize final response
        final_response = self._synthesize_council_response(
            reason_response, spark_response, edge_response, heart_response, vision_response
        )
        
        # Calculate totals
        voice_responses = {
            CouncilVoice.REASON: reason_response,
            CouncilVoice.SPARK: spark_response,
            CouncilVoice.EDGE: edge_response,
            CouncilVoice.HEART: heart_response,
            CouncilVoice.VISION: vision_response
        }
        
        total_latency_ms = (time.time() - start_time) * 1000
        total_cost = sum(r.cost_dollars for r in voice_responses.values())
        
        # Extract risk flags from Edge
        risk_flags = self._extract_risk_flags(edge_response.response)
        
        # Determine consensus quality
        consensus_achieved = self._assess_consensus_quality(voice_responses)
        
        # Record metrics
        if PROMETHEUS_AVAILABLE:
            COUNCIL_LATENCY_SECONDS.observe(total_latency_ms / 1000)
            COUNCIL_COST_DOLLARS.inc(total_cost)
            for voice in voice_responses:
                COUNCIL_VOICES_ACTIVE.labels(voice=voice.value).set(1)
            EDGE_RISK_FLAGS.inc(len(risk_flags))
        
        print(f"🌌 COUNCIL: Complete in {total_latency_ms:.1f}ms, cost ${total_cost:.4f}")
        
        return CouncilDeliberation(
            final_response=final_response,
            voice_responses=voice_responses,
            total_latency_ms=total_latency_ms,
            total_cost_dollars=total_cost,
            consensus_achieved=consensus_achieved,
            risk_flags=risk_flags,
            metadata={
                "prompt_tokens": len(prompt.split()),
                "response_tokens": len(final_response.split()),
                "voices_count": len(voice_responses),
                "council_version": "v1.0"
            }
        )
    
    async def _invoke_voice(self, voice: CouncilVoice, prompt: str) -> VoiceResponse:
        """Invoke a single council voice"""
        start_time = time.time()
        model_name = self.voice_models[voice]
        voice_prompt = self.voice_templates[voice].format(prompt=prompt)
        
        try:
            # Determine if this is cloud or local
            if "cloud" in model_name.lower():
                response = await self._invoke_cloud_voice(voice, voice_prompt, model_name)
            else:
                response = await self._invoke_local_voice(voice, voice_prompt, model_name)
            
            latency_ms = (time.time() - start_time) * 1000
            
            return VoiceResponse(
                voice=voice,
                response=response["text"],
                confidence=response.get("confidence", 0.8),
                latency_ms=latency_ms,
                model_used=response.get("model_used", model_name),
                cost_dollars=response.get("cost_dollars", 0.0),
                metadata=response.get("metadata", {})
            )
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            print(f"⚠️ Voice {voice.value} failed: {e}")
            
            return VoiceResponse(
                voice=voice,
                response=f"[{voice.value.upper()}_ERROR] Voice temporarily unavailable: {str(e)[:100]}",
                confidence=0.0,
                latency_ms=latency_ms,
                model_used="error",
                cost_dollars=0.0,
                metadata={"error": str(e)}
            )
    
    async def _invoke_local_voice(self, voice: CouncilVoice, prompt: str, model_name: str) -> Dict[str, Any]:
        """Invoke a local model voice"""
        loaded_models = get_loaded_models()
        
        if model_name not in loaded_models:
            # Fallback to voting with available models
            available_models = list(loaded_models.keys())[:2]  # Use top 2 available
            if available_models:
                result = await vote(prompt, available_models, min(2, len(available_models)))
                return {
                    "text": result["text"],
                    "confidence": result["voting_stats"]["winner_confidence"],
                    "model_used": result["winner"]["model"] + "_fallback",
                    "cost_dollars": 0.0,
                    "metadata": {"fallback_used": True, "original_model": model_name}
                }
            else:
                raise ValueError(f"No available models for {voice.value}")
        
        # Direct model invoke
        response = generate_response(model_name, prompt, max_tokens=200)
        
        # Estimate cost (local models are virtually free)
        token_count = len(response.split())
        cost_dollars = token_count * 0.00001  # 0.01 cent per token for local
        
        # Track local cost
        debit(model_name, token_count)
        
        return {
            "text": response,
            "confidence": 0.8,  # Local models get good confidence
            "model_used": model_name,
            "cost_dollars": cost_dollars,
            "metadata": {"type": "local", "tokens": token_count}
        }
    
    async def _invoke_cloud_voice(self, voice: CouncilVoice, prompt: str, model_name: str) -> Dict[str, Any]:
        """Invoke a cloud model voice with privacy filtering"""
        
        # Apply privacy filter
        privacy_result = apply_privacy_policy(prompt, "standard")
        
        if not privacy_result["safe_to_send"]:
            # Fall back to local model
            print(f"[COUNCIL] {voice.value} privacy blocked, using local fallback")
            return await self._invoke_local_voice(voice, prompt, "phi2_2.7b")
        
        # Call cloud service
        try:
            result = await ask_cloud_council(privacy_result["sanitized_prompt"])
            
            if "error" in result:
                raise ValueError(result["error"])
            
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.9),  # Cloud models high confidence
                "model_used": result.get("provider", model_name),
                "cost_dollars": result.get("cost_dollars", 0.003),  # ~0.3 cents per call
                "metadata": {"type": "cloud", "privacy_filtered": True}
            }
            
        except Exception as e:
            print(f"[COUNCIL] Cloud voice {voice.value} failed: {e}, using local fallback")
            return await self._invoke_local_voice(voice, prompt, "phi2_2.7b")
    
    def _synthesize_council_response(self, reason: VoiceResponse, spark: VoiceResponse, 
                                   edge: VoiceResponse, heart: VoiceResponse, 
                                   vision: VoiceResponse) -> str:
        """Synthesize final response from all council voices"""
        
        # Start with Heart's empathetic revision as the base
        base_response = heart.response
        
        # Add key insights from other voices
        synthesis = f"{base_response}\n\n"
        
        # Add creative elements from Spark if valuable
        if spark.confidence > 0.6 and "novel" in spark.response.lower():
            synthesis += f"💡 Creative insight: {spark.response[:150]}...\n\n"
        
        # Add risk assessment from Edge if significant
        risk_indicators = ["risk", "danger", "problem", "concern", "warning"]
        if any(indicator in edge.response.lower() for indicator in risk_indicators):
            synthesis += f"⚠️ Risk considerations: {edge.response[:150]}...\n\n"
        
        # Always add Vision's strategic note
        synthesis += f"🔮 Strategic context: {vision.response}\n"
        
        return synthesis.strip()
    
    def _extract_risk_flags(self, edge_response: str) -> List[str]:
        """Extract risk flags from Edge voice response"""
        flags = []
        edge_lower = edge_response.lower()
        
        risk_patterns = {
            "security": ["security", "vulnerability", "attack", "breach"],
            "performance": ["slow", "latency", "performance", "bottleneck"],
            "cost": ["expensive", "cost", "budget", "price"],
            "ethics": ["ethical", "bias", "fairness", "discrimination"],
            "safety": ["unsafe", "dangerous", "harm", "risk"]
        }
        
        for category, keywords in risk_patterns.items():
            if any(keyword in edge_lower for keyword in keywords):
                flags.append(category)
        
        return flags
    
    def _assess_consensus_quality(self, voice_responses: Dict[CouncilVoice, VoiceResponse]) -> bool:
        """Assess if the council achieved good consensus"""
        
        # Calculate average confidence
        avg_confidence = sum(r.confidence for r in voice_responses.values()) / len(voice_responses)
        
        # Check for major disagreements (Edge flagging serious risks)
        edge_response = voice_responses[CouncilVoice.EDGE]
        high_risk_indicators = ["critical", "dangerous", "major risk", "serious concern"]
        major_risks = any(indicator in edge_response.response.lower() for indicator in high_risk_indicators)
        
        # Consensus achieved if high confidence and no major risks
        return avg_confidence > 0.7 and not major_risks

# Global council router instance
council_router = CouncilRouter()

async def council_route(prompt: str) -> Dict[str, Any]:
    """
    Main council routing function - integrates with existing Router 2.x stack
    
    Returns standard router response format for compatibility
    """
    
    # Check if council should be triggered
    should_trigger, reason = council_router.should_trigger_council(prompt)
    
    if not should_trigger:
        # Use existing quick local path
        print(f"[COUNCIL] Quick path: {reason}")
        from router.voting import vote
        loaded_models = get_loaded_models()
        available_models = list(loaded_models.keys())[:3]
        
        if available_models:
            result = await vote(prompt, available_models, min(3, len(available_models)))
            return {
                "text": result["text"],
                "council_used": False,
                "council_reason": reason,
                "model_used": result["winner"]["model"],
                "confidence": result["voting_stats"]["winner_confidence"],
                "latency_ms": result["voting_stats"]["voting_time_ms"],
                "cost_dollars": 0.0
            }
        else:
            return {
                "text": "[ERROR] No models available",
                "council_used": False,
                "error": "no_models_available"
            }
    
    # Full council deliberation
    print(f"[COUNCIL] Full deliberation triggered: {reason}")
    deliberation = await council_router.council_deliberate(prompt)
    
    return {
        "text": deliberation.final_response,
        "council_used": True,
        "council_reason": reason,
        "council_deliberation": {
            "total_latency_ms": deliberation.total_latency_ms,
            "total_cost_dollars": deliberation.total_cost_dollars,
            "consensus_achieved": deliberation.consensus_achieved,
            "risk_flags": deliberation.risk_flags,
            "voices_used": [voice.value for voice in deliberation.voice_responses.keys()],
            "metadata": deliberation.metadata
        },
        "confidence": sum(r.confidence for r in deliberation.voice_responses.values()) / len(deliberation.voice_responses),
        "latency_ms": deliberation.total_latency_ms,
        "cost_dollars": deliberation.total_cost_dollars
    } 