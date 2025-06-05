#!/usr/bin/env python3
"""
Unit Tests for Flag Routing System
=================================

Tests the conscious-mirror flag layer including:
- Flag extraction from prompts
- Routing decisions 
- Executor integration
- Metrics collection
"""

import asyncio
import json
import unittest
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

# Import the modules we're testing
from router_flagging import FlagExtractor, FlagRouter, FlagType, get_flag_router
from router import EnhancedRouter, get_enhanced_router, route_with_flags
from metrics import get_router_metrics, RouterMetrics

class TestFlagExtractor(unittest.TestCase):
    """Test flag extraction from prompts"""
    
    def setUp(self):
        self.extractor = FlagExtractor()
    
    def test_math_flag_extraction(self):
        """Test FLAG_MATH extraction"""
        prompts = [
            "Calculate 2+2",
            "Solve this equation: x^2 + 5x = 30",
            "What's the derivative of x^3?",
            "Compute the probability of rolling a 6"
        ]
        
        for prompt in prompts:
            flags = self.extractor.extract_flags(prompt)
            math_flags = [f for f in flags if f.flag_type == FlagType.MATH]
            self.assertGreater(len(math_flags), 0, f"No MATH flag found in: {prompt}")
            self.assertGreater(math_flags[0].confidence, 0.5, "Low confidence for math flag")
    
    def test_syscall_flag_extraction(self):
        """Test FLAG_SYSCALL extraction"""
        prompts = [
            "Install nginx on the server",
            "Restart the Apache service",
            "Execute this command with sudo",
            "Kill the hanging process"
        ]
        
        for prompt in prompts:
            flags = self.extractor.extract_flags(prompt)
            syscall_flags = [f for f in flags if f.flag_type == FlagType.SYSCALL]
            self.assertGreater(len(syscall_flags), 0, f"No SYSCALL flag found in: {prompt}")
    
    def test_file_flag_extraction(self):
        """Test FLAG_FILE extraction"""
        prompts = [
            "Create a file called config.json",
            "Read the contents of data.txt",
            "Delete the old backup files",
            "Copy the logs to archive folder"
        ]
        
        for prompt in prompts:
            flags = self.extractor.extract_flags(prompt)
            file_flags = [f for f in flags if f.flag_type == FlagType.FILE]
            self.assertGreater(len(file_flags), 0, f"No FILE flag found in: {prompt}")
    
    def test_network_flag_extraction(self):
        """Test FLAG_NETWORK extraction"""
        prompts = [
            "Make an HTTP GET request to the API",
            "Fetch data from https://api.example.com",
            "Send a POST request with JSON data",
            "Check the server response status"
        ]
        
        for prompt in prompts:
            flags = self.extractor.extract_flags(prompt)
            network_flags = [f for f in flags if f.flag_type == FlagType.NETWORK]
            self.assertGreater(len(network_flags), 0, f"No NETWORK flag found in: {prompt}")
    
    def test_no_false_positives(self):
        """Test that normal text doesn't trigger flags incorrectly"""
        clean_prompts = [
            "Hello, how are you today?",
            "What's the weather like?",
            "Tell me about quantum physics",
            "What color is the sky?"
        ]
        
        for prompt in clean_prompts:
            flags = self.extractor.extract_flags(prompt)
            # These prompts should have very few or no flags
            self.assertLessEqual(len(flags), 1, f"Too many flags for clean prompt: {prompt}")
    
    def test_confidence_calculation(self):
        """Test confidence score calculation"""
        # High confidence prompt
        high_conf_prompt = "Calculate the sum of 25 + 37"
        flags = self.extractor.extract_flags(high_conf_prompt)
        
        if flags:
            self.assertGreater(flags[0].confidence, 0.7, "High confidence prompt should have high score")
        
        # Lower confidence prompt  
        low_conf_prompt = "The calculation seems wrong"
        flags = self.extractor.extract_flags(low_conf_prompt)
        
        # Should either have no flags or lower confidence
        if flags:
            self.assertLess(flags[0].confidence, 0.9, "Ambiguous prompt should have lower score")

class TestFlagRouter(unittest.TestCase):
    """Test flag-based routing decisions"""
    
    def setUp(self):
        self.router = FlagRouter()
    
    def test_math_routing(self):
        """Test routing for math requests"""
        result = self.router.route_prompt("Calculate 2+2")
        
        self.assertIn('FLAG_MATH', result['detected_flags'])
        self.assertEqual(result['routing']['executor'], 'math_specialist')
        self.assertEqual(result['routing']['queue'], 'swarm:math:q')
        self.assertFalse(result['routing']['requires_sandbox'])
    
    def test_syscall_routing(self):
        """Test routing for system calls"""
        result = self.router.route_prompt("Install nginx and restart it")
        
        self.assertIn('FLAG_SYSCALL', result['detected_flags'])
        self.assertEqual(result['routing']['executor'], 'os_executor')
        self.assertEqual(result['routing']['queue'], 'swarm:exec:q')
        self.assertTrue(result['routing']['requires_sandbox'])
    
    def test_explicit_flags(self):
        """Test routing with explicit flags"""
        result = self.router.route_prompt(
            "Some generic text", 
            explicit_flags=['FLAG_FILE']
        )
        
        self.assertIn('FLAG_FILE', result['all_flags'])
        self.assertEqual(result['routing']['executor'], 'file_handler')
    
    def test_priority_routing(self):
        """Test that SYSCALL has priority over other flags"""
        # Prompt that could trigger multiple flags
        result = self.router.route_prompt(
            "Install python and calculate 2+2 in a file"
        )
        
        # SYSCALL should win due to priority
        self.assertEqual(result['routing']['executor'], 'os_executor')
    
    def test_empty_prompt_routing(self):
        """Test routing for empty or generic prompts"""
        result = self.router.route_prompt("")
        
        self.assertEqual(result['routing']['executor'], 'default_agent')
        self.assertEqual(result['routing']['queue'], 'swarm:general:q')

class TestEnhancedRouter(unittest.TestCase):
    """Test the enhanced router with flag integration"""
    
    def setUp(self):
        # Mock Redis to avoid external dependencies
        self.redis_mock = Mock()
        self.router = EnhancedRouter()
        self.router.redis_client = self.redis_mock
    
    async def test_math_request_routing(self):
        """Test FLAG_MATH request handling"""
        result = await self.router.route_request("Calculate 2+2", ["FLAG_MATH"])
        
        self.assertIn('FLAG_MATH', result['flags_triggered'])
        self.assertEqual(result['agent_type'], 'math_specialist')
        self.assertIn('Mathematical result: 4', result['response'])
        self.assertGreater(result['processing_time_ms'], 0)
    
    async def test_syscall_request_routing(self):
        """Test FLAG_SYSCALL request routing to executor"""
        # Mock Redis operations
        self.redis_mock.rpush.return_value = True
        self.redis_mock.get.return_value = json.dumps({
            'response': 'Command executed successfully',
            'exit_code': 0
        })
        
        result = await self.router.route_request(
            "Install nginx", 
            ["FLAG_SYSCALL"]
        )
        
        self.assertIn('FLAG_SYSCALL', result['flags_triggered'])
        # Should queue for execution
        self.redis_mock.rpush.assert_called_once()
        
        # Check the queue name
        args = self.redis_mock.rpush.call_args[0]
        self.assertEqual(args[0], 'swarm:exec:q')
    
    async def test_file_request_routing(self):
        """Test FLAG_FILE request handling"""
        result = await self.router.route_request(
            "Create file config.json", 
            ["FLAG_FILE"]
        )
        
        self.assertIn('FLAG_FILE', result['flags_triggered'])
        self.assertEqual(result['agent_type'], 'file_handler')
    
    async def test_analysis_request_routing(self):
        """Test FLAG_ANALYSIS request handling"""
        result = await self.router.route_request(
            "Debug this code for performance issues", 
            ["FLAG_ANALYSIS"]
        )
        
        self.assertIn('FLAG_ANALYSIS', result['flags_triggered'])
        self.assertEqual(result['agent_type'], 'code_analyzer')
        self.assertIn('debugging recommendations', result['response'])
    
    async def test_creative_request_routing(self):
        """Test FLAG_CREATIVE request handling"""
        result = await self.router.route_request(
            "Write a story about space exploration", 
            ["FLAG_CREATIVE"]
        )
        
        self.assertIn('FLAG_CREATIVE', result['flags_triggered'])
        self.assertEqual(result['agent_type'], 'creative_agent')
        self.assertIn('story generated', result['response'])
    
    async def test_multiple_flags_priority(self):
        """Test that flag priority is respected"""
        result = await self.router.route_request(
            "Install software and calculate costs",
            ["FLAG_SYSCALL", "FLAG_MATH"]
        )
        
        # SYSCALL should have priority
        self.assertEqual(result['agent_type'], 'os_executor')
    
    async def test_error_handling(self):
        """Test error handling in routing"""
        # Mock Redis failure
        self.redis_mock.rpush.side_effect = Exception("Redis connection failed")
        
        result = await self.router.route_request(
            "Install nginx", 
            ["FLAG_SYSCALL"]
        )
        
        self.assertTrue(result.get('metadata', {}).get('error_type') == 'routing_failure')

class TestRouterMetrics(unittest.TestCase):
    """Test metrics collection for flag routing"""
    
    def setUp(self):
        self.metrics = RouterMetrics()
    
    def test_flag_hit_recording(self):
        """Test flag hit metrics recording"""
        # This should not raise exceptions
        self.metrics.record_flag_hit("FLAG_MATH", "math_specialist")
        self.metrics.record_flag_hit("FLAG_SYSCALL", "os_executor")
        
        # In mock implementation, just verify no exceptions
        self.assertTrue(True)
    
    def test_latency_recording(self):
        """Test latency metrics recording"""
        self.metrics.record_routing_latency(15.5)
        self.metrics.record_routing_latency(22.1)
        
        # Should not raise exceptions
        self.assertTrue(True)
    
    def test_execution_metrics(self):
        """Test execution success/error metrics"""
        self.metrics.record_execution_success("math_specialist", "FLAG_MATH")
        self.metrics.record_execution_error("os_executor", "permission_denied")
        
        # Should not raise exceptions
        self.assertTrue(True)
    
    def test_metrics_summary(self):
        """Test metrics summary generation"""
        # Record some test metrics
        self.metrics.record_flag_hit("FLAG_MATH", "math_specialist")
        self.metrics.record_execution_success("math_specialist", "FLAG_MATH")
        
        summary = self.metrics.get_metrics_summary()
        
        self.assertIn('flag_routing', summary)
        self.assertIn('execution', summary)
        self.assertIn('week3_integration', summary)
    
    def test_prometheus_export(self):
        """Test Prometheus metrics export"""
        export = self.metrics.export_prometheus_metrics()
        
        # Should return a string (even if mock)
        self.assertIsInstance(export, str)
        self.assertGreater(len(export), 0)

class TestIntegrationScenarios(unittest.TestCase):
    """Integration tests for complete flag routing scenarios"""
    
    def setUp(self):
        # Use real instances but mock external dependencies
        self.router = get_enhanced_router()
        self.router.redis_client = Mock()
    
    async def test_complete_math_workflow(self):
        """Test complete math request workflow"""
        # Test the main integration function
        result = await route_with_flags(
            "Calculate 2+2", 
            flags=["FLAG_MATH"],
            context={"user_id": "test_user"}
        )
        
        self.assertEqual(result['agent_type'], 'math_specialist')
        self.assertIn('Mathematical result: 4', result['response'])
        self.assertIn('FLAG_MATH', result['flags_triggered'])
        self.assertGreater(result['processing_time_ms'], 0)
    
    async def test_auto_flag_detection(self):
        """Test automatic flag detection without explicit flags"""
        result = await route_with_flags(
            "Install docker and restart the service"
        )
        
        # Should auto-detect SYSCALL flag
        self.assertIn('FLAG_SYSCALL', result['flags_triggered'])
        self.assertEqual(result['agent_type'], 'os_executor')
    
    async def test_context_preservation(self):
        """Test that context is preserved through routing"""
        context = {
            "user_id": "test_user",
            "session_id": "session_123",
            "preferences": {"verbose": True}
        }
        
        result = await route_with_flags(
            "Analyze code performance",
            context=context
        )
        
        # Context should be preserved in metadata
        self.assertIn('metadata', result)

# Async test runner
async def run_async_tests():
    """Run async tests"""
    test_cases = [
        TestEnhancedRouter(),
        TestIntegrationScenarios()
    ]
    
    all_passed = True
    
    for test_case in test_cases:
        for method_name in dir(test_case):
            if method_name.startswith('test_') and asyncio.iscoroutinefunction(getattr(test_case, method_name)):
                try:
                    print(f"🧪 Running {test_case.__class__.__name__}.{method_name}")
                    await getattr(test_case, method_name)()
                    print(f"   ✅ PASS")
                except Exception as e:
                    print(f"   ❌ FAIL: {e}")
                    all_passed = False
    
    return all_passed

# Main test execution
def run_all_tests():
    """Run all flag routing tests"""
    print("🧪 Running Flag Routing Tests")
    print("=" * 50)
    
    # Run synchronous tests
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add sync test cases
    suite.addTests(loader.loadTestsFromTestCase(TestFlagExtractor))
    suite.addTests(loader.loadTestsFromTestCase(TestFlagRouter))
    suite.addTests(loader.loadTestsFromTestCase(TestRouterMetrics))
    
    runner = unittest.TextTestRunner(verbosity=2)
    sync_result = runner.run(suite)
    
    # Run async tests
    print(f"\n🔄 Running Async Tests...")
    async_result = asyncio.run(run_async_tests())
    
    # Summary
    sync_success = sync_result.wasSuccessful()
    overall_success = sync_success and async_result
    
    print(f"\n📊 Test Results:")
    print(f"   Sync Tests: {'✅ PASS' if sync_success else '❌ FAIL'}")
    print(f"   Async Tests: {'✅ PASS' if async_result else '❌ FAIL'}")
    print(f"   Overall: {'🎯 SUCCESS' if overall_success else '❌ FAILURE'}")
    
    return overall_success

if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1) 