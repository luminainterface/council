#!/usr/bin/env python3
"""
Router 2.0: Confidence-Weighted Voting System

Fan a prompt to N model heads, score responses by log-probability and quality metrics,
then return the highest-confidence answer. This boosts quality without always paying
the computational cost of large models.
"""

import asyncio
import time
import math
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from loader.deterministic_loader import get_loaded_models, generate_response

# Prometheus metrics for voting
try:
    from prometheus_client import Counter, Histogram, Gauge
    VOTE_RESULTS = Counter('swarm_vote_results_total', 'Voting results by selected model', ['model'])
    VOTE_LATENCY = Histogram('swarm_vote_latency_seconds', 'Voting operation latency')
    VOTE_HEADS_USED = Gauge('swarm_vote_heads_used', 'Number of heads in voting pool')
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

@dataclass
class VoteCandidate:
    """Individual voting candidate with response and confidence metrics"""
    head_name: str
    response_text: str
    log_probability: float
    response_time_ms: float
    token_count: int
    quality_score: float
    confidence_score: float

class ConfidenceVoter:
    """Manages confidence-weighted voting across multiple model heads"""
    
    def __init__(self):
        self.loaded_models = {}
        self.refresh_models()
    
    def refresh_models(self):
        """Refresh the available model registry"""
        self.loaded_models = get_loaded_models()
    
    def calculate_log_probability(self, response: str, model_name: str) -> float:
        """
        Estimate log probability for a response (simplified heuristic)
        In production, this would use actual model logits
        """
        # Simple heuristics for confidence estimation
        base_score = -5.0  # Start with reasonable log prob
        
        # Longer, more detailed responses tend to be more confident
        length_bonus = min(len(response) / 100, 2.0)
        
        # Penalize very short or very long responses
        if len(response) < 10:
            length_penalty = -2.0
        elif len(response) > 500:
            length_penalty = -1.0
        else:
            length_penalty = 0.0
        
        # Model-specific confidence adjustments
        model_bonus = 0.0
        if "7b" in model_name.lower():
            model_bonus = 1.0  # Larger models get confidence boost
        elif "specialist" in model_name.lower():
            model_bonus = 0.5  # Specialists get moderate boost
        
        return base_score + length_bonus + length_penalty + model_bonus
    
    def calculate_quality_score(self, response: str, prompt: str) -> float:
        """
        Calculate quality score based on response characteristics
        """
        quality = 0.0
        
        # Response relevance (simple keyword matching)
        prompt_words = set(prompt.lower().split())
        response_words = set(response.lower().split())
        relevance = len(prompt_words & response_words) / max(len(prompt_words), 1)
        quality += relevance * 2.0
        
        # Response completeness
        if len(response) > 20:
            quality += 1.0
        
        # Avoid clearly broken responses
        if "error" in response.lower() or len(response) < 5:
            quality -= 5.0
        
        # Bonus for structured responses
        if any(marker in response for marker in ["```", "1.", "2.", "•", "-"]):
            quality += 0.5
        
        return max(quality, 0.0)
    
    def calculate_confidence_score(self, candidate: VoteCandidate) -> float:
        """
        Calculate overall confidence score combining multiple factors
        """
        # Normalize log probability (higher is better)
        log_prob_normalized = (candidate.log_probability + 10) / 10  # Scale to 0-1
        
        # Normalize quality score
        quality_normalized = min(candidate.quality_score / 5.0, 1.0)
        
        # Speed bonus (faster responses get slight boost)
        speed_bonus = max(0, (1000 - candidate.response_time_ms) / 1000) * 0.1
        
        # Weighted combination
        confidence = (
            log_prob_normalized * 0.4 +      # 40% log probability
            quality_normalized * 0.5 +       # 50% quality
            speed_bonus * 0.1               # 10% speed
        )
        
        return max(min(confidence, 1.0), 0.0)  # Clamp to [0, 1]
    
    async def generate_with_candidate(self, head_name: str, prompt: str) -> Optional[VoteCandidate]:
        """Generate response from a single head and create voting candidate"""
        if head_name not in self.loaded_models:
            return None
        
        start_time = time.time()
        
        try:
            # Generate response using our existing infrastructure
            response = generate_response(head_name, prompt, max_tokens=150)
            response_time_ms = (time.time() - start_time) * 1000
            
            # Calculate metrics
            log_prob = self.calculate_log_probability(response, head_name)
            quality = self.calculate_quality_score(response, prompt)
            token_count = len(response.split())
            
            # Create candidate
            candidate = VoteCandidate(
                head_name=head_name,
                response_text=response,
                log_probability=log_prob,
                response_time_ms=response_time_ms,
                token_count=token_count,
                quality_score=quality,
                confidence_score=0.0  # Will be calculated
            )
            
            # Calculate final confidence score
            candidate.confidence_score = self.calculate_confidence_score(candidate)
            
            return candidate
            
        except Exception as e:
            print(f"⚠️ Voting candidate {head_name} failed: {e}")
            return None
    
    async def vote(self, prompt: str, choices: List[str], top_k: int = 2) -> Dict[str, Any]:
        """
        Fan prompt to multiple heads and return the best response via voting
        
        Args:
            prompt: Input prompt to route
            choices: List of model head names to vote with
            top_k: Number of top candidates to consider
            
        Returns:
            Dict with winning response and voting metadata
        """
        start_time = time.time()
        
        # Refresh model registry
        self.refresh_models()
        
        # Filter to available heads
        available_choices = [c for c in choices if c in self.loaded_models]
        if not available_choices:
            raise ValueError(f"No available models from choices: {choices}")
        
        if PROMETHEUS_AVAILABLE:
            VOTE_HEADS_USED.set(len(available_choices))
        
        # Generate responses in parallel
        print(f"🗳️ Voting: {len(available_choices)} heads for '{prompt[:50]}...'")
        
        # Use asyncio.gather for parallel execution
        tasks = [self.generate_with_candidate(head, prompt) for head in available_choices]
        candidates = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful candidates
        valid_candidates = [c for c in candidates if isinstance(c, VoteCandidate)]
        
        if not valid_candidates:
            raise ValueError("No successful candidate responses")
        
        # Sort by confidence score (highest first)
        valid_candidates.sort(key=lambda c: c.confidence_score, reverse=True)
        
        # Select top candidates
        top_candidates = valid_candidates[:top_k]
        winner = top_candidates[0]
        
        # Record metrics
        if PROMETHEUS_AVAILABLE:
            VOTE_RESULTS.labels(model=winner.head_name).inc()
            VOTE_LATENCY.observe(time.time() - start_time)
        
        # Prepare voting results
        result = {
            "text": winner.response_text,
            "winner": {
                "model": winner.head_name,
                "confidence": winner.confidence_score,
                "log_probability": winner.log_probability,
                "quality_score": winner.quality_score,
                "response_time_ms": winner.response_time_ms,
                "token_count": winner.token_count
            },
            "all_candidates": [
                {
                    "model": c.head_name,
                    "confidence": c.confidence_score,
                    "response_snippet": c.response_text[:100] + "..." if len(c.response_text) > 100 else c.response_text
                }
                for c in valid_candidates
            ],
            "voting_stats": {
                "total_heads": len(available_choices),
                "successful_responses": len(valid_candidates),
                "voting_time_ms": (time.time() - start_time) * 1000,
                "top_k": top_k
            }
        }
        
        print(f"🏆 Winner: {winner.head_name} (confidence: {winner.confidence_score:.3f})")
        
        return result

# Global voter instance
voter = ConfidenceVoter()

def smart_select(prompt: str, choices: List[str]) -> str:
    """
    Smart O(1) model selection based on prompt characteristics
    Returns the single best model for the prompt without running inference
    """
    # Get available models
    loaded_models = get_loaded_models()
    available_choices = [c for c in choices if c in loaded_models]
    
    if not available_choices:
        raise ValueError(f"No available models from choices: {choices}")
    
    # Quick heuristic-based model selection
    prompt_lower = prompt.lower()
    
    # Math/calculation prompts
    if any(keyword in prompt_lower for keyword in ["calculate", "math", "*", "+", "-", "/", "equation", "solve"]):
        math_models = [m for m in available_choices if "math" in m.lower() or "specialist" in m.lower()]
        if math_models:
            return math_models[0]
    
    # Code-related prompts
    if any(keyword in prompt_lower for keyword in ["code", "python", "function", "programming", "debug", "```"]):
        code_models = [m for m in available_choices if "code" in m.lower() or "llama" in m.lower()]
        if code_models:
            return code_models[0]
    
    # Long/complex prompts - use larger models
    if len(prompt) > 200:
        large_models = [m for m in available_choices if "7b" in m.lower() or "mistral" in m.lower()]
        if large_models:
            return large_models[0]
    
    # Default: return the first available model (usually fastest)
    return available_choices[0]

async def vote(prompt: str, choices: List[str], top_k: int = 2) -> Dict[str, Any]:
    """Main voting function - facade for the ConfidenceVoter"""
    return await voter.vote(prompt, choices, top_k) 