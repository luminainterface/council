#!/usr/bin/env python3
"""
Enhanced Router with Conscious-Mirror Flag Integration
====================================================

Routes requests to appropriate executors based on detected flags
and content analysis. Integrates with Redis queues for execution.
"""

import asyncio
import json
import logging
import time
import uuid
from typing import Dict, List, Optional, Any
import redis

from router_flagging import get_flag_router, should_route_to_executor

logger = logging.getLogger(__name__)

class EnhancedRouter:
    """Router with flag-based intelligent routing"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.flag_router = get_flag_router()
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        
        # Initialize metrics (if available)
        try:
            from prometheus_client import Counter
            self.flag_counter = Counter(
                "swarm_router_flag_total", 
                "Flag routing hits", 
                ["flag", "executor"]
            )
            self.metrics_available = True
        except ImportError:
            self.metrics_available = False
            logger.warning("Prometheus metrics not available")
    
    async def route_request(self, prompt: str, explicit_flags: List[str] = None, 
                          context: Dict[str, Any] = None) -> Dict[str, Any]:
        """Route a request based on flags and content"""
        start_time = time.time()
        
        # Extract and route based on flags
        routing_result = self.flag_router.route_prompt(prompt, explicit_flags)
        
        detected_flags = routing_result['detected_flags']
        routing_info = routing_result['routing']
        
        # Update metrics
        if self.metrics_available:
            for flag in detected_flags:
                self.flag_counter.labels(
                    flag=flag, 
                    executor=routing_info['executor']
                ).inc()
        
        # GPU-aware routing decision
        gpu_routing = self._determine_gpu_routing(detected_flags, routing_info)
        
        # Determine if we need executor routing
        if should_route_to_executor(detected_flags):
            execution_result = await self._route_to_executor(
                prompt, routing_info, context or {}, gpu_routing
            )
        else:
            execution_result = await self._route_to_agent(
                prompt, routing_info, context or {}, gpu_routing
            )
        
        processing_time = (time.time() - start_time) * 1000
        
        return {
            'response': execution_result.get('response', 'Processing completed'),
            'agent_type': routing_info['executor'],
            'processing_time_ms': processing_time,
            'flags_triggered': detected_flags,
            'routing_info': routing_info,
            'metadata': {
                'confidence_scores': routing_result.get('confidence_scores', {}),
                'execution_details': execution_result.get('metadata', {})
            }
        }
    
    async def _route_to_executor(self, prompt: str, routing_info: Dict, 
                               context: Dict) -> Dict[str, Any]:
        """Route to specialized executor via Redis queue with GPU awareness"""
        job_id = str(uuid.uuid4())[:8]
        
        # GPU profile routing logic
        model_cfg = context.get('model_config', {})
        if model_cfg.get("gpu_profile") == "gpu_aux":
            target_queue = "gpu_aux:q"
            gpu_assignment = "gpu_aux"
        else:
            target_queue = "swarm:exec:q"
            gpu_assignment = "gpu_main"
        
        # Prepare job payload with GPU routing
        job_payload = {
            'job_id': job_id,
            'prompt': prompt,
            'context': context,
            'routing': routing_info,
            'gpu_profile': gpu_assignment,
            'timestamp': time.time(),
            'requires_sandbox': routing_info.get('requires_sandbox', False)
        }
        
        queue_name = target_queue
        
        try:
            # Push to Redis queue
            self.redis_client.rpush(queue_name, json.dumps(job_payload))
            
            logger.info(f"🚀 Routed to {routing_info['executor']} via {queue_name}")
            
            # For FLAG_SYSCALL, wait for execution result
            if "FLAG_SYSCALL" in routing_info.get('executor', ''):
                result = await self._wait_for_execution_result(job_id)
                return result
            
            # For other executors, return immediate acknowledgment
            return {
                'response': f"Request queued for {routing_info['executor']} processing",
                'job_id': job_id,
                'queue': queue_name,
                'metadata': {'queued_at': time.time()}
            }
            
        except Exception as e:
            logger.error(f"❌ Executor routing failed: {e}")
            return {
                'response': f"Routing failed: {str(e)}",
                'error': True,
                'metadata': {'error_type': 'routing_failure'}
            }
    
    async def _route_to_agent(self, prompt: str, routing_info: Dict, 
                            context: Dict) -> Dict[str, Any]:
        """Route to AI agent for processing"""
        executor_type = routing_info['executor']
        
        # Simulate different agent responses based on type
        agent_responses = {
            'math_specialist': self._handle_math_request,
            'code_analyzer': self._handle_analysis_request,
            'creative_agent': self._handle_creative_request,
            'default_agent': self._handle_general_request
        }
        
        handler = agent_responses.get(executor_type, self._handle_general_request)
        
        try:
            response = await handler(prompt, context)
            return {
                'response': response,
                'metadata': {
                    'agent_type': executor_type,
                    'processing_method': 'agent_handler'
                }
            }
        except Exception as e:
            logger.error(f"❌ Agent processing failed: {e}")
            return {
                'response': f"Agent processing failed: {str(e)}",
                'error': True,
                'metadata': {'error_type': 'agent_failure'}
            }
    
    async def _wait_for_execution_result(self, job_id: str, 
                                       timeout: int = 30) -> Dict[str, Any]:
        """Wait for execution result from Redis"""
        result_key = f"swarm:result:{job_id}"
        
        for _ in range(timeout):
            result = self.redis_client.get(result_key)
            if result:
                try:
                    return json.loads(result)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in result for {job_id}")
            
            await asyncio.sleep(1)
        
        return {
            'response': f"Execution timeout for job {job_id}",
            'error': True,
            'metadata': {'error_type': 'execution_timeout'}
        }
    
    async def _handle_math_request(self, prompt: str, context: Dict) -> str:
        """Handle mathematical computation requests"""
        # Extract mathematical expressions
        import re
        
        # Simple arithmetic evaluation
        math_pattern = r'(\d+(?:\.\d+)?)\s*([+\-*/])\s*(\d+(?:\.\d+)?)'
        match = re.search(math_pattern, prompt)
        
        if match:
            left, op, right = match.groups()
            left, right = float(left), float(right)
            
            if op == '+':
                result = left + right
            elif op == '-':
                result = left - right
            elif op == '*':
                result = left * right
            elif op == '/':
                result = left / right if right != 0 else "Error: Division by zero"
            else:
                result = "Error: Unknown operation"
            
            return f"Mathematical result: {result}"
        
        return "Mathematical analysis completed. No simple arithmetic detected."
    
    async def _handle_analysis_request(self, prompt: str, context: Dict) -> str:
        """Handle code analysis requests"""
        analysis_aspects = []
        
        if 'debug' in prompt.lower():
            analysis_aspects.append("debugging recommendations")
        if 'performance' in prompt.lower():
            analysis_aspects.append("performance optimization suggestions")
        if 'refactor' in prompt.lower():
            analysis_aspects.append("refactoring opportunities")
        
        if analysis_aspects:
            return f"Code analysis complete. Identified: {', '.join(analysis_aspects)}"
        
        return "Code analysis completed. General code quality assessment performed."
    
    async def _handle_creative_request(self, prompt: str, context: Dict) -> str:
        """Handle creative content generation"""
        if 'story' in prompt.lower():
            return "Creative story generated based on your requirements."
        elif 'poem' in prompt.lower():
            return "Original poem composed according to your specifications."
        elif 'marketing' in prompt.lower():
            return "Marketing content created with compelling messaging."
        
        return "Creative content generated successfully."
    
    async def _handle_general_request(self, prompt: str, context: Dict) -> str:
        """Handle general requests"""
        return f"General processing completed for: {prompt[:50]}..."
    
    def _determine_gpu_routing(self, flags: List[str], routing_info: Dict) -> Dict[str, str]:
        """Determine GPU assignment based on flags and model requirements"""
        
        # Complex models go to GPU-1 (aux)
        heavy_flags = {'FLAG_ANALYSIS', 'FLAG_CREATIVE', 'FLAG_NETWORK'}
        if any(flag in heavy_flags for flag in flags):
            return {
                'gpu_profile': 'gpu_aux',
                'queue': 'gpu_aux:q',
                'device_id': '1'
            }
        
        # Fast response models stay on GPU-0 (main)
        fast_flags = {'FLAG_MATH', 'FLAG_SYSCALL'}
        if any(flag in fast_flags for flag in flags):
            return {
                'gpu_profile': 'gpu_main', 
                'queue': 'swarm:exec:q',
                'device_id': '0'
            }
        
        # Default to main GPU
        return {
            'gpu_profile': 'gpu_main',
            'queue': 'swarm:exec:q', 
            'device_id': '0'
        }
    
    def get_routing_stats(self) -> Dict[str, Any]:
        """Get routing statistics"""
        stats = {
            'total_flags_processed': 0,
            'flag_distribution': {},
            'executor_usage': {},
            'gpu_usage': {'gpu_main': 0, 'gpu_aux': 0},
            'redis_connection': 'unknown'
        }
        
        try:
            # Test Redis connection
            self.redis_client.ping()
            stats['redis_connection'] = 'healthy'
        except:
            stats['redis_connection'] = 'failed'
        
        return stats

# Global router instance
_enhanced_router = None

def get_enhanced_router() -> EnhancedRouter:
    """Get global enhanced router instance"""
    global _enhanced_router
    if _enhanced_router is None:
        _enhanced_router = EnhancedRouter()
        logger.info("🎯 Enhanced router initialized with flag support")
    return _enhanced_router

# Integration functions for existing API
async def route_with_flags(prompt: str, flags: List[str] = None, 
                          context: Dict = None) -> Dict[str, Any]:
    """Main routing function with flag support"""
    router = get_enhanced_router()
    return await router.route_request(prompt, flags, context)

# Test function
async def test_flag_routing():
    """Test flag-based routing"""
    router = get_enhanced_router()
    
    test_cases = [
        ("Calculate 2+2", ["FLAG_MATH"]),
        ("Install nginx", ["FLAG_SYSCALL"]),
        ("Create file config.json", ["FLAG_FILE"]),
        ("Debug this code", ["FLAG_ANALYSIS"]),
        ("Write a story", ["FLAG_CREATIVE"])
    ]
    
    print("🎯 Testing Flag-Based Routing")
    print("=" * 50)
    
    for prompt, flags in test_cases:
        print(f"\n📝 Testing: {prompt}")
        print(f"🏁 Flags: {flags}")
        
        result = await router.route_request(prompt, flags)
        
        print(f"✅ Response: {result['response']}")
        print(f"🎯 Agent: {result['agent_type']}")
        print(f"⏱️ Time: {result['processing_time_ms']:.1f}ms")
        print(f"🏁 Triggered: {result['flags_triggered']}")

if __name__ == "__main__":
    asyncio.run(test_flag_routing()) 