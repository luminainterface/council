# -*- coding: utf-8 -*-
"""
Voting Router with Quality Filters - Track ② Integration
========================================================

Enhanced voting system with P1 quality improvements:
- Duplicate-token detection with cloud fallback
- Confidence-weighted voting
- Quality post-processing
- Memory hooks for context-aware conversations
- LENGTH PENALTY: Prevents math head from dominating with short answers
"""

# 🚨 DEBUG MODE: Enable raw candidate dumping
DEBUG_DUMP = False

# 🎯 VOTING QUALITY CONFIGURATION
VOTING_CONFIG = {
    "min_confidence": 0.75,  # Raised from 0.50 to prevent choppy answers
    "stub_detection_enabled": True,
    "template_rejection_enabled": True,
    "agent0_confidence_gate": 0.65,  # Skip specialists if Agent-0 is confident
    "parallel_execution": True  # Run specialists in parallel
}

import asyncio
import time
import random
import re
from typing import List, Dict, Any, Optional
from loader.deterministic_loader import generate_response, get_loaded_models
from router.quality_filters import (
    check_duplicate_tokens, 
    apply_confidence_weighted_voting,
    get_optimal_decoding_params,
    post_process_response,
    calculate_quality_metrics,
    CloudRetryException
)

# Import global memory
from bootstrap import MEMORY

import logging
from router.selector import pick_specialist, load_models_config, should_use_cloud_fallback
from router_cascade import RouterCascade

logger = logging.getLogger(__name__)

# 📝 CASCADING KNOWLEDGE FUNCTIONS
def summarize_to_digest(text: str, max_tokens: int = 40) -> str:
    """Create a 40-token digest summary for cascading knowledge"""
    if not text or len(text.strip()) < 10:
        return ""
    
    # Simple truncation fallback (if no AI summarizer available)
    words = text.split()
    if len(words) <= max_tokens:
        return text
    
    # Take first and last portions for context preservation
    first_half = words[:max_tokens//2]
    last_half = words[-(max_tokens//2):]
    
    summary = " ".join(first_half) + " ... " + " ".join(last_half)
    return summary

def write_fusion_digest(final_answer: str, session_id: str, original_prompt: str):
    """Write a 40-token digest after successful fusion for cascading knowledge"""
    try:
        from common.scratchpad import write
        
        # Create digest
        digest = summarize_to_digest(final_answer, max_tokens=40)
        if digest:
            # Write to scratchpad with context
            write(
                session_id=session_id,
                agent="fusion_digest", 
                content=f"Q: {original_prompt[:100]} A: {digest}",
                tags=["turn", "digest", "fusion"],
                entry_type="digest"
            )
            logger.info(f"📝 Written fusion digest: {digest[:50]}...")
        
    except Exception as e:
        logger.debug(f"Failed to write digest: {e}")

def read_conversation_context(session_id: str, max_digests: int = 3) -> str:
    """Read last 3 digests for conversation context"""
    try:
        from common.scratchpad import read
        
        entries = read(session_id, limit=max_digests * 2)  # Get extra in case of non-digests
        digest_entries = [e for e in entries if e.entry_type == "digest"][:max_digests]
        
        if digest_entries:
            context_lines = [entry.content for entry in digest_entries]
            return "\n".join(reversed(context_lines))  # Chronological order
        
        return ""
        
    except Exception as e:
        logger.debug(f"Failed to read context: {e}")
        return ""

class SpecialistRunner:
    """Runs individual specialists with timeout and error handling"""
    
    def __init__(self):
        self.router = RouterCascade()
    
    async def run_specialist(self, specialist: str, prompt: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Run a single specialist with timeout protection"""
        start_time = time.time()
        
        try:
            # Map specialist names to router methods
            specialist_map = {
                "math_specialist": self._run_math,
                "code_specialist": self._run_code,
                "logic_specialist": self._run_logic, 
                "knowledge_specialist": self._run_knowledge,
                "mistral_general": self._run_general
            }
            
            if specialist not in specialist_map:
                raise ValueError(f"Unknown specialist: {specialist}")
            
            # Run specialist with timeout
            result = await asyncio.wait_for(
                specialist_map[specialist](prompt),
                timeout=timeout
            )
            
            # Add metadata
            result["specialist"] = specialist
            result["latency_ms"] = (time.time() - start_time) * 1000
            result["status"] = "success"
            
            return result
            
        except asyncio.TimeoutError:
            return {
                "specialist": specialist,
                "text": f"[TIMEOUT] {specialist} exceeded {timeout}s",
                "confidence": 0.0,
                "status": "timeout",
                "latency_ms": timeout * 1000
            }
        except Exception as e:
            return {
                "specialist": specialist,
                "text": f"[ERROR] {specialist}: {str(e)}",
                "confidence": 0.0, 
                "status": "error",
                "latency_ms": (time.time() - start_time) * 1000,
                "error": str(e)
            }
    
    async def _run_math(self, prompt: str) -> Dict[str, Any]:
        """Run math specialist (SymPy)"""
        try:
            # Force routing to math specialist
            result = await self.router.route_query(prompt, force_skill="math")
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.9),
                "model": "lightning-math-sympy",
                "skill_type": "math"
            }
        except Exception as e:
            # Fallback if math specialist fails
            raise Exception(f"Math specialist failed: {e}")
    
    async def _run_code(self, prompt: str) -> Dict[str, Any]:
        """Run code specialist (DeepSeek + Sandbox)"""
        try:
            result = await self.router.route_query(prompt, force_skill="code")
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.8),
                "model": "deepseek-coder-sandbox",
                "skill_type": "code"
            }
        except Exception as e:
            raise Exception(f"Code specialist failed: {e}")
    
    async def _run_logic(self, prompt: str) -> Dict[str, Any]:
        """Run logic specialist (SWI-Prolog)"""
        try:
            result = await self.router.route_query(prompt, force_skill="logic")
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.7),
                "model": "swi-prolog-engine",
                "skill_type": "logic"
            }
        except Exception as e:
            raise Exception(f"Logic specialist failed: {e}")
    
    async def _run_knowledge(self, prompt: str) -> Dict[str, Any]:
        """Run knowledge specialist (FAISS RAG)"""
        try:
            result = await self.router.route_query(prompt, force_skill="knowledge")
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.6),
                "model": "faiss-rag-retrieval",
                "skill_type": "knowledge"
            }
        except Exception as e:
            raise Exception(f"Knowledge specialist failed: {e}")
    
    async def _run_general(self, prompt: str) -> Dict[str, Any]:
        """Run general LLM (Mistral/OpenAI cloud fallback)"""
        try:
            result = await self.router.route_query(prompt, force_skill="agent0")
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.5),
                "model": result.get("model", "cloud-fallback"),
                "skill_type": "general"
            }
        except Exception as e:
            raise Exception(f"General LLM failed: {e}")

    async def run_specialist_with_conversation(self, specialist: str, conversation_prompt: str, timeout: float = 5.0) -> Dict[str, Any]:
        """Run a single specialist with natural conversation prompt"""
        start_time = time.time()
        
        try:
            # Map specialist names to router methods
            specialist_map = {
                "math_specialist": self._run_math_conversation,
                "code_specialist": self._run_code_conversation,
                "logic_specialist": self._run_logic_conversation, 
                "knowledge_specialist": self._run_knowledge_conversation,
                "mistral_general": self._run_general_conversation
            }
            
            if specialist not in specialist_map:
                raise ValueError(f"Unknown specialist: {specialist}")
            
            # Run specialist with conversation prompt and timeout
            result = await asyncio.wait_for(
                specialist_map[specialist](conversation_prompt),
                timeout=timeout
            )
            
            # Add metadata
            result["specialist"] = specialist
            result["latency_ms"] = (time.time() - start_time) * 1000
            result["status"] = "success"
            
            return result
            
        except asyncio.TimeoutError:
            return {
                "specialist": specialist,
                "text": f"[TIMEOUT] {specialist} exceeded {timeout}s",
                "confidence": 0.0,
                "status": "timeout",
                "latency_ms": timeout * 1000
            }
        except Exception as e:
            return {
                "specialist": specialist,
                "text": f"[ERROR] {specialist}: {str(e)}",
                "confidence": 0.0, 
                "status": "error",
                "latency_ms": (time.time() - start_time) * 1000,
                "error": str(e)
            }
    
    async def _run_math_conversation(self, conversation_prompt: str) -> Dict[str, Any]:
        """Run math specialist with conversation style"""
        try:
            # Extract the actual user query from conversation prompt
            user_query = conversation_prompt.split("User: ")[-1].split("\nCouncil:")[0] if "User: " in conversation_prompt else conversation_prompt
            result = await self.router.route_query(user_query, force_skill="math")
            
            # Make response more conversational for math
            response_text = result["text"]
            if response_text.replace(".", "").replace("-", "").isdigit() or any(op in user_query for op in ['+', '-', '*', '/', '=', 'sqrt', 'sin', 'cos']):
                response_text = f"The answer is {response_text}! 🧮"
            
            return {
                "text": response_text,
                "confidence": result.get("confidence", 0.9),
                "model": "lightning-math-sympy",
                "skill_type": "math"
            }
        except Exception as e:
            raise Exception(f"Math specialist failed: {e}")
    
    async def _run_code_conversation(self, conversation_prompt: str) -> Dict[str, Any]:
        """Run code specialist with conversation style"""
        try:
            user_query = conversation_prompt.split("User: ")[-1].split("\nCouncil:")[0] if "User: " in conversation_prompt else conversation_prompt
            result = await self.router.route_query(user_query, force_skill="code")
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.8),
                "model": "deepseek-coder-sandbox",
                "skill_type": "code"
            }
        except Exception as e:
            raise Exception(f"Code specialist failed: {e}")
    
    async def _run_logic_conversation(self, conversation_prompt: str) -> Dict[str, Any]:
        """Run logic specialist with conversation style"""
        try:
            user_query = conversation_prompt.split("User: ")[-1].split("\nCouncil:")[0] if "User: " in conversation_prompt else conversation_prompt
            result = await self.router.route_query(user_query, force_skill="logic")
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.7),
                "model": "swi-prolog-engine",
                "skill_type": "logic"
            }
        except Exception as e:
            raise Exception(f"Logic specialist failed: {e}")
    
    async def _run_knowledge_conversation(self, conversation_prompt: str) -> Dict[str, Any]:
        """Run knowledge specialist with conversation style"""
        try:
            user_query = conversation_prompt.split("User: ")[-1].split("\nCouncil:")[0] if "User: " in conversation_prompt else conversation_prompt
            result = await self.router.route_query(user_query, force_skill="knowledge")
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.6),
                "model": "faiss-rag-retrieval",
                "skill_type": "knowledge"
            }
        except Exception as e:
            raise Exception(f"Knowledge specialist failed: {e}")
    
    async def _run_general_conversation(self, conversation_prompt: str) -> Dict[str, Any]:
        """Run general LLM with conversation style"""
        try:
            user_query = conversation_prompt.split("User: ")[-1].split("\nCouncil:")[0] if "User: " in conversation_prompt else conversation_prompt
            result = await self.router.route_query(user_query, force_skill="agent0")
            return {
                "text": result["text"],
                "confidence": result.get("confidence", 0.5),
                "model": result.get("model", "cloud-fallback"),
                "skill_type": "general"
            }
        except Exception as e:
            raise Exception(f"General LLM failed: {e}")

async def vote(prompt: str, model_names: List[str] = None, top_k: int = 1, use_context: bool = True) -> Dict[str, Any]:
    """
    Run council voting with natural conversation style.
    
    Following o3plan.md: ALL messages go through 5-head Council with 
    friendly conversation prompts and memory context.
    """
    start_time = time.time()
    
    # 🚀 SURGICAL FIX: Template stub detection patterns (per get-green script)
    STUB = ["template", "todo", "custom_function", "unsupported number theory"]
    
    stub_markers = [
        'custom_function', 'TODO', 'pass', 'NotImplemented',
        'placeholder', 'your_code_here', '# Add implementation',
        'Processing', 'Transformers response', 'Mock response',
        'template', 'todo', 'unsupported number theory'  # Added per script
    ]
    
    # 🎯 ENHANCED STUB PATTERNS: Catch greeting stubs and UNSURE responses
    STUB_PATTERNS = [
        r"^hello! i'm your autogen council assistant",
        r"i can help with math, code, logic",
        r"^UNSURE$",  # Math specialist UNSURE responses
        r"let me analyze this.*problem",  # Generic analysis responses
        r"ready to solve.*step by step",  # Generic step-by-step responses
    ]
    
    # 🚨 GREETING FILTER: Stop ALL specialists from greeting
    GREETING_STUB_RE = re.compile(r"^\s*(hi|hello|hey)[!,. ]", re.I)
    
    def scrub_greeting_stub(candidate: Dict[str, Any]) -> Dict[str, Any]:
        """Filter out greeting responses from specialists - they should never greet"""
        text = candidate.get("text", "")
        if GREETING_STUB_RE.match(text):
            candidate["confidence"] = 0.0
            candidate["status"] = "greeting_filtered"
            candidate["original_text"] = text
            candidate["text"] = f"[GREETING_FILTERED] {candidate.get('specialist', 'unknown')} tried to greet"
            logger.info(f"🚫 Filtered greeting from {candidate.get('specialist', 'unknown')}: '{text[:30]}...'")
        return candidate
    
    def is_stub_response(text: str) -> bool:
        """Detect if response is a template stub that should be rejected"""
        if not text or len(text.strip()) < 10:
            # Import CloudRetryException here to avoid circular imports
            from router.quality_filters import CloudRetryException
            raise CloudRetryException("Template stub detected - response too short")
        
        text_lower = text.lower()
        
        # Check original stub markers
        for marker in stub_markers:
            if marker.lower() in text_lower:
                from router.quality_filters import CloudRetryException
                raise CloudRetryException(f"Template stub detected - contains marker: {marker}")
            
        # 🎯 Check enhanced stub patterns (regex-based)
        for pattern in STUB_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                from router.quality_filters import CloudRetryException
                raise CloudRetryException(f"Template stub detected - matches pattern: {pattern}")
                
        return False
    
    def looks_stub(text: str) -> bool:
        """Alias for is_stub_response for compatibility"""
        return is_stub_response(text)
    
    def score_with_stub_filter(candidate: Dict[str, Any]) -> float:
        """Apply stub filtering to candidate scoring"""
        text = candidate.get("text", "")
        confidence = candidate.get("confidence", 0)
        
        if looks_stub(text):
            logger.debug(f"🚫 Stub detected: '{text[:50]}...' → confidence nuked to 0.0")
            return 0.0  # Nuke confidence for stubs
        
        return confidence
    
    # Build natural conversation prompt (o3plan.md recipe)
    conversation_prompt = build_conversation_prompt(prompt)
    
    # 🚀 SIMPLE GREETING DETECTOR: Handle basic greetings directly without model calls
    def is_simple_greeting(prompt: str) -> bool:
        prompt_lower = prompt.strip().lower()
        simple_greetings = ['hi', 'hello', 'hey', 'hi there', 'hello there', 'good morning', 'good afternoon']
        # Don't treat math expressions or queries with numbers as greetings
        if any(char in prompt for char in ['+', '-', '*', '/', '=', '?']) or any(char.isdigit() for char in prompt):
            return False
        return prompt_lower in simple_greetings
    
    if is_simple_greeting(prompt):
        logger.info("🎯 Simple greeting detected - direct response")
        return {
            "winner": {
                "specialist": "greeting_handler",
                "text": "Hi! How can I help you today?",
                "confidence": 1.0,
                "status": "greeting"
            },
            "text": "Hi! How can I help you today?",
            "specialist": "greeting_handler",
            "confidence": 1.0,
            "status": "greeting_shortcut",
            "latency_ms": (time.time() - start_time) * 1000,
            "voting_stats": {
                "total_specialists": 0,
                "successful_specialists": 0,
                "winner_confidence": 1.0,
                "total_latency_ms": (time.time() - start_time) * 1000,
                "specialists_tried": [],
                "greeting_shortcut": True,
                "first_token_latency_ms": (time.time() - start_time) * 1000,
                "perceived_speed": "instant"
            }
        }
    
    # Determine specialists to try
    if model_names is None:
        # 🎯 FIXED: Always try multiple specialists for proper voting
        # The original logic only tried one specialist with high confidence,
        # which prevented length penalty from working since there was no comparison
        config = load_models_config()
        primary_specialist, confidence, tried = pick_specialist(prompt, config)
        
        # 🎯 INTENT GATE: Exclude math head from non-math queries
        is_math_query = any(pattern in prompt.lower() for pattern in [
            'calculate', 'solve', 'math', '+', '-', '*', '/', '=', 'sqrt',
            'factorial', 'equation', 'algebra', 'geometry'
        ]) or bool(re.search(r'\d+\s*[\+\-\*/\^%]\s*\d+', prompt))
        
        # Always include multiple specialists for voting comparison
        specialists_to_try = [primary_specialist]
        
        # 🎯 ALWAYS add other specialists for comparison, not just when confidence is low
        # This ensures length penalty can compare responses and rebalance
        other_specialists = [s for s in config["specialists_order"] if s != primary_specialist]
        
        # 🔧 INTENT GATE: Filter out math specialist for non-math queries
        if not is_math_query and primary_specialist == "math_specialist":
            # Replace primary with non-math specialist
            non_math_specialists = [s for s in other_specialists if s != "math_specialist"]
            if non_math_specialists:
                primary_specialist = non_math_specialists[0]
                specialists_to_try = [primary_specialist]
                other_specialists = [s for s in non_math_specialists[1:]]
        
        # Filter math from other specialists if not a math query
        if not is_math_query:
            other_specialists = [s for s in other_specialists if s != "math_specialist"]
            
        specialists_to_try.extend(other_specialists[:3])  # Try 3 other specialists
        
        # 🚨 GENERALIST PENALTY: Prevent silent fallback to cloud (Triage Step 1)
        def apply_generalist_penalty(specialists: List[str]) -> List[str]:
            """Apply penalty to generalist/cloud providers to prefer specialists"""
            specialists_only = []
            generalists = []
            
            for specialist in specialists:
                # Identify generalist/cloud providers
                if ("mistral" in specialist.lower() and "specialist" not in specialist.lower()) or \
                   ("general" in specialist.lower()) or ("cloud" in specialist.lower()):
                    logger.warning(f"🚨 Generalist {specialist} demoted to fallback position")
                    generalists.append(specialist)
                else:
                    # Keep real specialists in priority order
                    specialists_only.append(specialist)
            
            # Return specialists first, generalists last
            return specialists_only + generalists
        
        # Apply generalist penalty to prevent cloud jumps
        specialists_to_try = apply_generalist_penalty(specialists_to_try)
        
        logger.info(f"🗳️ Vote candidates: {specialists_to_try[:4]}... (primary: {primary_specialist}, is_math: {is_math_query})")
    else:
        specialists_to_try = model_names
    
    # Run specialists in priority order with conversation-style prompts
    runner = SpecialistRunner()
    results = []
    
    # 🚀 AGENT-0 CONFIDENCE GATE: Skip specialists if Agent-0 is confident enough
    # Quick Agent-0 check for simple queries (optimization #4)
    try:
        logger.info("🔬 Quick Agent-0 confidence check...")
        agent0_result = await runner.run_specialist_with_conversation("mistral_general", conversation_prompt, timeout=2.0)
        agent0_confidence = agent0_result.get("confidence", 0.0)
        
        # If Agent-0 is confident (>= 0.65), skip specialists and return immediately
        # 🚀 LOWERED THRESHOLD: Was 0.90, now 0.65 for more shortcuts on simple queries
        if agent0_confidence >= 0.65:
            logger.info(f"🚀 Agent-0 confident ({agent0_confidence:.2f} ≥ 0.65) - skipping specialists")
            
            # 🚀 CRITICAL: Apply token limits to Agent-0 responses too
            agent0_text = agent0_result.get("text", "")
            if len(agent0_text) > 80:  # ~20 tokens whisper-size
                agent0_text = agent0_text[:80] + "..."
                logger.info(f"🔧 Truncated Agent-0 response to 20 tokens")
            
            agent0_result["text"] = agent0_text
            agent0_result["agent0_shortcut"] = True
            agent0_result["specialists_skipped"] = specialists_to_try
            return {
                "winner": agent0_result,
                "text": agent0_result.get("text", ""),
                "specialist": agent0_result.get("specialist", "mistral_general"),
                "confidence": agent0_confidence,
                "status": "agent0_shortcut",
                "latency_ms": (time.time() - start_time) * 1000,
                "voting_stats": {
                    "total_specialists": 1,
                    "successful_specialists": 1,
                    "winner_confidence": agent0_confidence,
                    "total_latency_ms": (time.time() - start_time) * 1000,
                    "specialists_tried": ["mistral_general"],
                    "agent0_shortcut": True,
                    "first_token_latency_ms": agent0_result.get("latency_ms", (time.time() - start_time) * 1000),
                    "perceived_speed": "fast"
                }
            }
    except Exception as e:
        logger.debug(f"🔬 Agent-0 confidence check failed: {e} - proceeding with specialists")
    
    # 🚀 PARALLEL EXECUTION: Run specialists concurrently (optimization #1)
    # Replace sequential loop with asyncio.gather for massive speedup
    logger.info(f"🚀 Running {len(specialists_to_try)} specialists in parallel...")
    
    try:
        # Create parallel tasks with 4-second timeout each
        tasks = [
            runner.run_specialist_with_conversation(specialist, conversation_prompt, timeout=4.0)
            for specialist in specialists_to_try
        ]
        
        # Run all specialists in parallel - wall time = slowest specialist instead of sum
        parallel_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and exceptions
        results = []
        for i, result in enumerate(parallel_results):
            specialist = specialists_to_try[i]
            logger.info(f"🎯 Council member: {specialist}")
            
            if isinstance(result, Exception):
                # Handle exceptions from parallel execution
                logger.warning(f"⚠️ {specialist} failed: {result}")
                error_result = {
                    "specialist": specialist,
                    "text": f"[ERROR] {specialist}: {str(result)}",
                    "confidence": 0.0,
                    "status": "error",
                    "latency_ms": 4000,  # Timeout value
                    "error": str(result)
                }
                results.append(error_result)
            else:
                # 🚀 SURGICAL FIX: Filter out stub responses
                if is_stub_response(result.get("text", "")):
                    logger.warning(f"🚫 {specialist} returned stub response - filtering out")
                    result["confidence"] = 0.0  # Mark as unusable
                    result["status"] = "stub_filtered"
                    result["text"] = f"[STUB_FILTERED] {specialist} returned template response"
                
                # 🚨 GREETING FILTER: Stop specialists from greeting
                result = scrub_greeting_stub(result)
                
                results.append(result)
                logger.info(f"✅ {specialist} completed: confidence={result['confidence']:.2f}, status={result.get('status', 'unknown')}")
        
        logger.info(f"🚀 Parallel execution completed in {(time.time() - start_time)*1000:.0f}ms")
        
    except Exception as e:
        logger.error(f"🚀 Parallel execution failed: {e} - falling back to sequential")
        
        # Fallback to original sequential execution if parallel fails
        results = []
        for specialist in specialists_to_try:
            logger.info(f"🎯 Council member: {specialist} (sequential fallback)")
            
            try:
                # Pass the natural conversation prompt to specialists
                result = await runner.run_specialist_with_conversation(specialist, conversation_prompt, timeout=4.0)
                
                # 🚀 SURGICAL FIX: Filter out stub responses
                if is_stub_response(result.get("text", "")):
                    logger.warning(f"🚫 {specialist} returned stub response - filtering out")
                    result["confidence"] = 0.0  # Mark as unusable
                    result["status"] = "stub_filtered"
                    result["text"] = f"[STUB_FILTERED] {specialist} returned template response"
                
                # 🚨 GREETING FILTER: Stop specialists from greeting  
                result = scrub_greeting_stub(result)
                
                results.append(result)
                logger.info(f"✅ {specialist} completed: confidence={result['confidence']:.2f}, status={result.get('status', 'unknown')}")
                    
            except Exception as e:
                logger.warning(f"⚠️ {specialist} failed: {e}")
                
                # Check if we should try cloud fallback
                if should_use_cloud_fallback(specialist, str(e)):
                    logger.info("☁️ Triggering cloud fallback")
                    try:
                        cloud_result = await runner.run_specialist_with_conversation("mistral_general", conversation_prompt)
                        results.append(cloud_result)
                    except Exception as cloud_error:
                        logger.error(f"☁️ Cloud fallback also failed: {cloud_error}")
    
    # After all specialists have generated responses, apply UNSURE penalty
    # 🎯 VOTE GUARD: Apply UNSURE confidence penalty to fix math head domination
    for result in results:
        response_text = result.get("text", "").strip()
        
        # 🚨 GREETING FILTER: Apply to any missed greeting responses
        result = scrub_greeting_stub(result)
        
        # 🚀 CRITICAL FIX: Hard penalty for UNSURE and short responses
        if response_text == "UNSURE" or len(response_text) < 10:
            result["confidence"] = 0.05  # Can't win - hard penalty
            result["unsure_penalty_applied"] = True
            specialist_name = result.get('specialist', 'unknown')
            logger.debug(f"🎯 Applied UNSURE/short penalty to {specialist_name}: confidence = 0.05 (text: '{response_text}')")
        elif response_text == "UNSURE":
            # Extra logging for pure UNSURE responses
            result["confidence"] = 0.05
            result["unsure_penalty_applied"] = True
            specialist_name = result.get('specialist', 'unknown')
            logger.info(f"🚫 {specialist_name} properly returned UNSURE for off-topic query - confidence = 0.05")
    
    # If no results, emergency fallback
    if not results:
        emergency_result = {
            "specialist": "emergency_fallback",
            "text": f"I apologize, but all specialists are currently unavailable. Please try again later.",
            "confidence": 0.05,  # Very low confidence for emergency fallback
            "status": "emergency",
            "latency_ms": (time.time() - start_time) * 1000
        }
        results.append(emergency_result)
    
    # 🚨 DEBUG DUMP: Print every raw candidate before any filtering
    if DEBUG_DUMP:
        print("\n=== RAW CANDIDATES DEBUG ===")
        for i, result in enumerate(results):
            specialist = result.get("specialist", f"unknown_{i}")
            confidence = result.get("confidence", 0)
            text = result.get("text", "")
            status = result.get("status", "unknown")
            print(f"[{specialist}] conf={confidence:.2f} status={status}")
            print(f"TEXT: {text[:300]}...")  # First 300 chars
            print("---")
        print("=== END RAW CANDIDATES ===\n")
    
    # Vote for best result
    successful_results = [r for r in results if r["status"] == "success"]
    if not successful_results:
        successful_results = results  # Use whatever we have
    
    # 🚀 PHASE A PATCH #2: Kill Mixtral on "UNSURE" - don't let it win
    viable_candidates = []
    for result in successful_results:
        response_text = result.get("text", "").strip()
        if response_text.startswith('UNSURE') or response_text == "UNSURE":
            logger.info(f"🚫 Filtering out UNSURE candidate: {result.get('specialist', 'unknown')}")
            continue  # Skip UNSURE responses completely
        viable_candidates.append(result)
    
    # Use viable candidates for voting, fallback to all if none viable
    if viable_candidates:
        successful_results = viable_candidates
        logger.info(f"🎯 Using {len(viable_candidates)} viable candidates (filtered out UNSURE)")
    else:
        logger.warning(f"⚠️ No viable candidates after UNSURE filter - using all results")
    
    # 🚀 PHASE A PATCH #3: Return after first confident specialist (≥ 0.8)
    confident_specialist = None
    for result in successful_results:
        if result.get("confidence", 0) >= 0.8:
            confident_specialist = result
            logger.info(f"🚀 Found confident specialist: {result.get('specialist', 'unknown')} ({result.get('confidence', 0):.2f})")
            break
    
    if confident_specialist:
        # Return immediately without fusion
        logger.info(f"🎯 Returning confident specialist without fusion for speed")
        return {
            "text": confident_specialist["text"],
            "model": confident_specialist.get("model", confident_specialist["specialist"]),
            "winner": confident_specialist,
            "voting_stats": {
                "total_specialists": len(results),
                "successful_specialists": len(successful_results),
                "winner_confidence": confident_specialist["confidence"],
                "total_latency_ms": (time.time() - start_time) * 1000,
                "specialists_tried": [r["specialist"] for r in results],
                "confident_shortcut": True,
                "first_token_latency_ms": confident_specialist.get("latency_ms", (time.time() - start_time) * 1000),
                "perceived_speed": "fast"
            },
            "specialists_tried": [r["specialist"] for r in results],
            "council_decision": True,
            "confident_shortcut": True,
            "timestamp": time.time()
        }
    
    # 🗳️ ENHANCED VOTING: Apply length penalty to prevent math head domination
    if len(successful_results) > 1:
        # Apply both length penalty AND stub filtering to all candidates
        for result in successful_results:
            original_confidence = result.get("confidence", 0)
            
            # 🎯 FIRST: Apply stub filtering (sets confidence to 0 for stubs)
            stub_filtered_confidence = score_with_stub_filter(result)
            
            # 🎯 SECOND: Apply length penalty only if not a stub
            if stub_filtered_confidence > 0:
                penalty_multiplier = length_penalty(result.get("text", ""), prompt)
                final_confidence = stub_filtered_confidence * penalty_multiplier
            else:
                penalty_multiplier = 0.0
                final_confidence = 0.0
            
            # Store all confidence transformations for transparency
            result["original_confidence"] = original_confidence
            result["stub_filtered_confidence"] = stub_filtered_confidence
            result["length_penalty"] = penalty_multiplier
            result["confidence"] = final_confidence
            
            # 📊 Track length penalty metrics
            try:
                from monitoring.hardening_metrics import track_length_penalty
                track_length_penalty(
                    result.get("specialist", "unknown"),
                    original_confidence,
                    final_confidence
                )
            except Exception as e:
                logger.debug(f"Metrics tracking failed: {e}")
            
            logger.debug(f"📏 {result.get('specialist', 'unknown')}: "
                        f"confidence {original_confidence:.3f} → {stub_filtered_confidence:.3f} (stub) → {final_confidence:.3f} (final) "
                        f"(penalty: {penalty_multiplier:.2f})")
        
        # Re-sort after applying length penalties
        top_candidates = sorted(successful_results, key=lambda r: r.get("confidence", 0), reverse=True)[:5]
        
        # 🗳️ CONSENSUS FUSION: Fuse top candidates after length penalty
        try:
            # 🚀 FUSION FILTER: Remove Agent-0 drafts to prevent bloat, keep only specialists
            specialist_candidates = [c for c in top_candidates if c.get("specialist") not in ["mistral_general", "agent0_fallback", "emergency_fallback"]]
            
            if not specialist_candidates:
                # Fallback: if no specialists, use all candidates
                specialist_candidates = top_candidates
                logger.debug("🚀 No specialists found - using all candidates for fusion")
            else:
                logger.info(f"🚀 Fusion filter: Using {len(specialist_candidates)} specialists, excluding Agent-0 drafts")
            
            fused_answer = await consensus_fuse(specialist_candidates, prompt)
            logger.info(f"🤝 Consensus fusion: {len(specialist_candidates)} specialists → unified answer")
            
            # 🎯 CRITICAL: Check if fusion returned a stub - if so, use best individual answer
            if looks_stub(fused_answer) or "Hello! I'm your AutoGen Council assistant" in fused_answer:
                logger.warning("🚫 Consensus fusion returned stub - falling back to best individual answer")
                winner = max(successful_results, key=lambda r: r.get("confidence", 0))
                winner["fusion_attempted"] = True
                winner["fusion_failed"] = "stub_detected"
                # 🎯 FIXED: Set specialist to true source
                winner["true_source"] = winner.get("specialist", "unknown")
            else:
                # Create consensus winner
                winner = {
                    "specialist": "council_consensus", 
                    "text": fused_answer,
                    "confidence": sum(r["confidence"] for r in specialist_candidates) / len(specialist_candidates),
                    "status": "consensus",
                    "model": "council-fusion",
                    "candidates": specialist_candidates,  # Only specialist candidates for transparency
                    "fusion_method": "specialist_only",   # 🚀 NEW: Track that we filtered Agent-0
                    "length_penalty_applied": True,
                    "true_source": "consensus_fusion",    # Track true source
                    "agent0_filtered": len(top_candidates) != len(specialist_candidates)  # Track if Agent-0 was filtered
                }
        except Exception as e:
            logger.warning(f"Consensus fusion failed: {e}, falling back to top candidate")
            winner = max(successful_results, key=lambda r: r.get("confidence", 0))
            winner["candidates"] = top_candidates  # Still provide candidates
            winner["length_penalty_applied"] = True
            winner["fusion_attempted"] = True
            winner["fusion_failed"] = str(e)
            # 🎯 FIXED: Set specialist to true source
            winner["true_source"] = winner.get("specialist", "unknown")
    else:
        # Single answer - still apply both stub filtering and length penalty
        if successful_results:
            result = successful_results[0]
            original_confidence = result.get("confidence", 0)
            
            # 🎯 FIRST: Apply stub filtering
            stub_filtered_confidence = score_with_stub_filter(result)
            
            # 🎯 SECOND: Apply length penalty only if not a stub
            if stub_filtered_confidence > 0:
                penalty_multiplier = length_penalty(result.get("text", ""), prompt)
                final_confidence = stub_filtered_confidence * penalty_multiplier
            else:
                penalty_multiplier = 0.0
                final_confidence = 0.0
            
            result["original_confidence"] = original_confidence
            result["stub_filtered_confidence"] = stub_filtered_confidence
            result["length_penalty"] = penalty_multiplier
            result["confidence"] = final_confidence
            result["length_penalty_applied"] = True
            result["true_source"] = result.get("specialist", "unknown")  # Track true source
            
            # 📊 Track length penalty metrics for single result
            try:
                from monitoring.hardening_metrics import track_length_penalty
                track_length_penalty(
                    result.get("specialist", "unknown"),
                    original_confidence,
                    final_confidence
                )
            except Exception as e:
                logger.debug(f"Metrics tracking failed: {e}")
            
            logger.debug(f"📏 Single result {result.get('specialist', 'unknown')}: "
                        f"confidence {original_confidence:.3f} → {stub_filtered_confidence:.3f} (stub) → {final_confidence:.3f} (final)")
        
            winner = max(successful_results, key=lambda r: r.get("confidence", 0))
            # 🎯 FIXED: Ensure specialist tag reflects true source
            winner["true_source"] = winner.get("specialist", "unknown")
    
    # 📊 Track specialist win for rebalancing monitoring
    try:
        from monitoring.hardening_metrics import track_specialist_win
        track_specialist_win(winner.get("specialist", "unknown"))
    except Exception as e:
        logger.debug(f"Win tracking failed: {e}")

    # Voting statistics (enhanced for consensus)
    voting_stats = {
        "total_specialists": len(results),
        "successful_specialists": len(successful_results),
        "winner_confidence": winner["confidence"],
        "total_latency_ms": (time.time() - start_time) * 1000,
        "specialists_tried": [r["specialist"] for r in results],
        "consensus_fusion": winner.get("specialist") == "council_consensus",
        "candidates_count": len(winner.get("candidates", [])),
        # 🏁 FIRST-TOKEN LATENCY: For honest "Fast response" metrics
        "first_token_latency_ms": min([r.get("latency_ms", 999999) for r in successful_results], default=(time.time() - start_time) * 1000),
        "perceived_speed": "fast" if min([r.get("latency_ms", 999999) for r in successful_results], default=9999) < 500 else "normal"
    }
    
    logger.info(f"🏆 Council decision: {winner['specialist']} wins with {winner['confidence']:.2f} confidence")
    logger.info(f"⚡ Performance: first-token {voting_stats['first_token_latency_ms']:.0f}ms, total {voting_stats['total_latency_ms']:.0f}ms")
    
    # 🧠 Log Q&A to memory with success flags (required for Phase 3 self-improvement)
    try:
        # Use singleton memory instead of creating new instance
        
        # Determine success based on confidence and status
        success_flag = (winner["confidence"] > 0.5 and 
                       winner.get("status", "success") == "success" and
                       "ERROR" not in winner["text"] and
                       "TIMEOUT" not in winner["text"])
        
        # Log the conversation pair for Agent-0 learning
        original_prompt = prompt.split("\nUser query: ")[-1] if "\nUser query: " in prompt else prompt
        MEMORY.add(original_prompt, {
            "role": "user", 
            "timestamp": time.time(),
            "session_id": f"council_{int(time.time())}"
        })
        MEMORY.add(winner["text"], {
            "role": "assistant", 
            "timestamp": time.time(),
            "success": success_flag,  # Critical for Phase 3 failure harvesting
            "confidence": winner["confidence"],
            "specialist": winner["specialist"],
            "latency_ms": voting_stats["total_latency_ms"],
            "council_decision": True
        })
        
        logger.debug(f"💾 Logged Q&A to memory: success={success_flag}, confidence={winner['confidence']:.2f}")
        
    except Exception as e:
        logger.warning(f"Memory logging failed: {e}")
    
    # 📝 CASCADING KNOWLEDGE: Write fusion digest for next conversation
    try:
        # Extract original prompt and create session ID
        original_prompt = prompt.split("\nUser query: ")[-1] if "\nUser query: " in prompt else prompt
        session_id = f"council_{int(time.time())}"
        
        # Write 40-token digest
        write_fusion_digest(winner["text"], session_id, original_prompt)
        
    except Exception as e:
        logger.debug(f"Failed to write fusion digest: {e}")

    return {
        "text": winner["text"],
        "model": winner.get("model", winner["specialist"]),
        "winner": winner,
        "voting_stats": voting_stats,
        "specialists_tried": [r["specialist"] for r in results],
        "council_decision": True,
        "timestamp": time.time(),
        # 🗳️ Consensus transparency
        "consensus_fusion": winner.get("specialist") == "council_consensus",
        "candidates": winner.get("candidates", []),  # All head votes for transparency
        "fusion_method": winner.get("fusion_method", "single_winner"),
        "length_penalty_applied": winner.get("length_penalty_applied", False),
        # 🏁 PERFORMANCE METRICS: Honest latency reporting
        "first_token_latency_ms": voting_stats["first_token_latency_ms"],
        "perceived_speed": voting_stats["perceived_speed"],
        "total_latency_ms": voting_stats["total_latency_ms"]
    }

def smart_select(prompt: str, model_names: List[str]) -> str:
    """
    Smart single-model selection for simple prompts (Track ① fast path)
    
    Selects the best model for a given prompt without running inference.
    Enhanced with quality considerations.
    """
    if not model_names:
        return model_names[0] if model_names else "unknown"
    
    # Simple heuristic-based selection with quality focus
    prompt_lower = prompt.lower()
    
    # Math-related prompts → prefer math specialist
    if any(math_word in prompt_lower for math_word in ['math', 'calculate', 'add', 'subtract', '+', '-', '*', '/', 'equals']):
        for model in model_names:
            if 'math' in model.lower():
                return model
    
    # Code-related prompts → prefer code specialist  
    if any(code_word in prompt_lower for code_word in ['code', 'python', 'def ', 'function', 'import', 'class']):
        for model in model_names:
            if 'code' in model.lower():
                return model
    
    # Logic prompts → prefer logic specialist
    if any(logic_word in prompt_lower for logic_word in ['if ', 'then', 'logic', 'reasoning', 'true', 'false']):
        for model in model_names:
            if 'logic' in model.lower():
                return model
    
    # For general prompts, prefer models known for quality
    # Priority order: phi2 > tinyllama > mistral > others
    quality_priority = ['phi2', 'tinyllama', 'mistral']
    
    for priority_model in quality_priority:
        for model in model_names:
            if priority_model in model.lower():
                return model
    
    # Fallback to first available model
    return model_names[0] 

def handle_simple_greeting(prompt: str, start_time: float) -> Dict[str, Any]:
    """Handle simple greetings with memory-aware, contextual responses"""
    
    import time  # Add missing import
    
    # Still use memory context for greetings - check for user name, preferences, etc.
    contextual_greeting = prompt
    memory_context = ""
    
    try:
        # 🚀 HARDENING FIX: Use singleton memory instead of re-instantiating
        from bootstrap import MEMORY
        context_results = MEMORY.query(prompt, k=2)  # Get recent context
        
        if context_results:
            # Look for user name or preferences in memory
            names = []
            recent_topics = []
            
            for result in context_results:
                text = result.get("text", "")
                # Extract potential names (simple heuristic)
                if "my name is" in text.lower() or "i'm " in text.lower():
                    names.extend([word.strip(".,!") for word in text.split() if word[0].isupper() and len(word) > 2])
                # Extract recent topics
                if len(text) > 10:
                    recent_topics.append(text[:50] + "..." if len(text) > 50 else text)
            
            # Build personalized greeting
            if names:
                user_name = names[-1]  # Use most recent name
                contextual_greetings = [
                    f"Hi {user_name}! How can I help today?",
                    f"Hello {user_name}! What would you like to explore?", 
                    f"Hey {user_name}! 👋 Ask me anything.",
                ]
                import random
                response_text = random.choice(contextual_greetings)
            elif recent_topics:
                # Reference recent conversation
                response_text = f"Hello! Welcome back. I see we were discussing {recent_topics[0]}. What would you like to explore now?"
            else:
                # Standard but context-aware greeting
                contextual_greetings = [
                    "Hi! How can I help today?",
                    "Hello again — what would you like to explore?", 
                    "Hey there! Ask me anything.",
                ]
                import random
                response_text = random.choice(contextual_greetings)
                
            memory_context = f"Found {len(context_results)} relevant memories"
        else:
            # First-time greeting
            response_text = "Hello! What would you like to explore?"
            
        # Log this greeting interaction to memory (just like the full system)
        MEMORY.add(prompt, {"role": "user", "timestamp": time.time(), "greeting": True})
        MEMORY.add(response_text, {"role": "assistant", "timestamp": time.time(), "greeting_response": True, "success": True})
        
    except Exception as e:
        logger.warning(f"Memory lookup failed for greeting: {e}")
        # Fallback greeting
        response_text = "Hello! I'm your AutoGen Council assistant. How can I help you today?"
    
    return {
        "text": response_text,
        "model": "memory_aware_greeting_handler",
        "winner": {
            "specialist": "memory_aware_greeting_handler", 
            "text": response_text,
            "confidence": 1.0,
            "model": "contextual-greeting-handler",
            "memory_context": memory_context
        },
        "voting_stats": {
            "total_specialists": 1,
            "successful_specialists": 1,
            "winner_confidence": 1.0,
            "total_latency_ms": (time.time() - start_time) * 1000,
            "specialists_tried": ["memory_aware_greeting_handler"],
            "memory_used": True
        },
        "specialists_tried": ["memory_aware_greeting_handler"],
        "council_decision": False,  # Fast path but still memory-aware
        "memory_context_applied": True,
        "timestamp": time.time()
    }

def build_conversation_prompt(user_msg: str) -> str:
    """
    Build natural conversation prompt with memory context.
    
    🧠 PHASE B: Enhanced with conversation summarizer for smart context retrieval.
    
    Following o3plan.md recipe: 
    - Fetch 3 most relevant memories
    - Add conversation summary (≤ 80 tokens)
    - Make Council sound conversational
    """
    try:
        # 📝 CASCADING KNOWLEDGE: Read conversation digests
        session_id = f"council_{int(time.time())}"
        digest_context = read_conversation_context(session_id, max_digests=3)
        
        # 🧠 PHASE B PATCH #2: Retrieval before every draft
        from common.summarizer import SUMMARIZER
        
        # Use singleton memory instead of creating new instance
        ctx = MEMORY.query(user_msg, k=3)
        ctx_block = "\n".join(f"- {m['text']}" for m in ctx) if ctx else "- none"
        
        # 🧠 PHASE B: Add conversation summary for context
        session_id = "default_session"  # Could be passed in future
        try:
            # Get recent conversation summary (≤ 80 tokens)
            recent_entries = MEMORY.get_recent(limit=5)  # Get last 5 turns
            if recent_entries:
                conversation_text = "\n".join([
                    f"{'User' if entry.get('role') == 'user' else 'Assistant'}: {entry.get('text', '')}"
                    for entry in recent_entries
                ])
                
                # Generate compressed summary
                summary = SUMMARIZER.summarize_conversation(conversation_text, max_tokens=60)
                conversation_summary = f"Recent conversation: {summary.summary_text}"
                
                logger.debug(f"🧠 Context enriched: {summary.original_length} → {summary.token_count} tokens")
            else:
                conversation_summary = "New conversation"
                
        except Exception as e:
            logger.debug(f"🧠 Conversation summary failed: {e} - using basic context")
            conversation_summary = "Conversation context unavailable"
        
        # Guard rails: truncate to 1000 chars total
        full_context = f"{ctx_block}\n{conversation_summary}"
        
        # Add digest context if available
        if digest_context:
            full_context += f"\nPrevious turns:\n{digest_context}"
            
        if len(full_context) > 1000:
            full_context = full_context[:1000] + "..."
        
    except Exception as e:
        logger.warning(f"Memory context failed: {e}")
        full_context = "- none\nNew conversation"
    
    # 2) Build conversation-style system prompt with enriched context
    system_prompt = f"""You are the **Council**, a collective of five specialist heads.
Be concise, helpful, and keep a friendly tone.

Relevant context:
{full_context}
—
Answer the user:"""

    # 3) Return formatted conversation prompt
    return f"{system_prompt}\n\nUser: {user_msg}\nCouncil:"

async def consensus_fuse(candidates: List[Dict[str, Any]], original_prompt: str) -> str:
    """
    Consensus fusion: merge multiple specialist answers into unified response.
    
    Uses local LLM to synthesize all candidate answers into a single,
    comprehensive, non-repetitive answer.
    """
    from prometheus_client import Summary
    import time
    
    # Prometheus metric for fusion latency
    try:
        FUSE_LAT = Summary("swarm_consensus_latency_seconds", "Consensus fusion step")
        with FUSE_LAT.time():
            return await _perform_fusion(candidates, original_prompt)
    except:
        # Fallback without metrics if prometheus not available
        return await _perform_fusion(candidates, original_prompt)

async def _perform_fusion(candidates: List[Dict[str, Any]], original_prompt: str) -> str:
    """Perform the actual fusion of candidate answers"""
    
    # Build bullet list of all candidate answers
    bullet_list = []
    for i, candidate in enumerate(candidates):
        specialist = candidate.get("specialist", f"head_{i}")
        text = candidate.get("text", "").strip()
        confidence = candidate.get("confidence", 0)
        
        if text and text not in [c.get("text", "") for c in candidates[:i]]:  # Avoid duplicates
            bullet_list.append(f"- **{specialist}** ({confidence:.2f}): {text}")
    
    bullet_text = "\n".join(bullet_list)
    
    # Extract user query from conversation prompt if needed
    user_query = original_prompt
    if "User: " in original_prompt:
        user_query = original_prompt.split("User: ")[-1].split("\nCouncil:")[0]
    
    # Consensus fusion prompt
    fusion_prompt = f"""As the Council Scribe, merge these specialist answers into a single, comprehensive response.

User asked: {user_query}

Specialist answers:
{bullet_text}

Instructions:
- Combine the best insights from each specialist
- Remove redundancy and contradictions
- Keep the response concise but complete
- Maintain a helpful, friendly tone
- Don't mention the specialists or fusion process

Unified Council answer:"""

    try:
        # Use the router to get a local LLM response for fusion
        from router_cascade import RouterCascade
        router = RouterCascade()
        
        # Force use of agent0 (general) for fusion
        result = await router.route_query(fusion_prompt, force_skill="agent0")
        fused_text = result.get("text", "").strip()
        
        # Clean up the response
        if fused_text.startswith("Unified Council answer:"):
            fused_text = fused_text.replace("Unified Council answer:", "").strip()
        
        # Fallback if fusion is empty or too short
        if len(fused_text) < 20:
            # Simple rule-based fusion as fallback
            best_answer = max(candidates, key=lambda c: c.get("confidence", 0))
            return best_answer.get("text", "I apologize, but I couldn't process your request.")
        
        return fused_text
        
    except Exception as e:
        logger.warning(f"LLM fusion failed: {e}, using rule-based fusion")
        
        # Rule-based fallback fusion
        if candidates:
            best_answer = max(candidates, key=lambda c: c.get("confidence", 0))
            other_answers = [c for c in candidates if c != best_answer]
            
            if other_answers:
                # Simple merge: best answer + additional insights
                additional_insights = []
                for candidate in other_answers[:2]:  # Top 2 additional insights
                    text = candidate.get("text", "").strip()
                    if text and len(text) > 10 and text not in best_answer.get("text", ""):
                        additional_insights.append(text)
                
                if additional_insights:
                    return f"{best_answer.get('text', '')} Additionally, {' '.join(additional_insights)}"
            
            return best_answer.get("text", "I apologize, but I couldn't process your request.")
        
        return "I apologize, but I couldn't process your request."

def length_penalty(text: str, query: str) -> float:
    """
    🎯 LENGTH PENALTY: Prevent math head from dominating with ultra-short answers
    
    Args:
        text: The response text
        query: Original query to check if scalar answer is expected
        
    Returns:
        Penalty multiplier (0.4-1.0)
    """
    if not text:
        return 0.4
    
    # Tokenize response (simple word-based tokenization)
    tokens = text.strip().split()
    token_count = len(tokens)
    
    # 🎯 ENHANCED: Check if prompt is obviously numeric/mathematical
    query_lower = query.lower()
    is_numeric_prompt = any(pattern in query_lower for pattern in [
        'what is', 'how much', 'calculate', 'solve', 'equals', '=',
        'add', 'subtract', 'multiply', 'divide', '+', '-', '*', '/',
        'sqrt', 'square root', 'factorial', 'prime'
    ]) or bool(re.search(r'\d+\s*[\+\-\*/\^%]\s*\d+', query))
    
    # 🔧 SIMPLE 3-LINE PENALTY: Penalize very short replies unless obviously numeric
    if is_numeric_prompt:
        # For math queries, allow shorter answers with mild penalty
        penalty = 0.7 + min(0.3, 0.04 * token_count)  # 1-token → 0.7, 8+ tokens → 1.0
    else:
        # For non-numeric queries, heavily penalize short answers
        penalty = 0.4 + min(0.6, 0.04 * token_count)  # 1-token → 0.4, 15+ tokens → 1.0
    
    return penalty

def score_answer(tokens: list, mean_logprob: float, query: str) -> float:
    """
    🎯 ENHANCED SCORING: Apply length penalty to prevent short answer domination
    
    Args:
        tokens: Response tokens (for length calculation)
        mean_logprob: Mean log probability of the response
        query: Original query for context
        
    Returns:
        Adjusted score with length penalty applied
    """
    # Convert tokens to text for penalty calculation
    text = " ".join(tokens) if isinstance(tokens, list) else str(tokens)
    
    # Apply length penalty
    penalty = length_penalty(text, query)
    
    return mean_logprob * penalty

def expect_scalar_answer(query: str) -> bool:
    """Check if query expects a scalar/numerical answer"""
    query_lower = query.lower()
    
    # Math calculation patterns
    math_patterns = [
        r'\d+\s*[\+\-\*/\^%]\s*\d+',  # 2+2, 5*7
        r'what\s+is\s+\d+',           # what is 5+3
        r'calculate\s+\d+',           # calculate 15*3
        r'solve\s+for\s+\w+',         # solve for x
        r'equals?\s*\?',              # equals?
    ]
    
    return any(re.search(pattern, query_lower) for pattern in math_patterns) 