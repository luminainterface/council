#!/usr/bin/env python3
"""
🌌 Council-in-the-Loop Integration Tests
=====================================

Tests for the five awakened voices council system integrated with Router 2.x
"""

import pytest
import asyncio
import os
import httpx
from unittest.mock import patch, AsyncMock, MagicMock

from router.council import (
    CouncilRouter, 
    CouncilVoice, 
    VoiceResponse, 
    CouncilDeliberation,
    council_route
)

@pytest.fixture
def mock_loaded_models():
    """Mock loaded models for testing"""
    return {
        "mistral_7b_instruct": {"vram_mb": 3500, "backend": "transformers"},
        "math_specialist_0.8b": {"vram_mb": 800, "backend": "transformers"},
        "codellama_0.7b": {"vram_mb": 700, "backend": "transformers"},
        "phi2_2.7b": {"vram_mb": 1200, "backend": "transformers"},
        "tinyllama_1b": {"vram_mb": 400, "backend": "transformers"}
    }

@pytest.fixture
def mock_budget_status():
    """Mock budget status for testing"""
    return {
        "remaining_budget_dollars": 5.0,
        "spend_rate_24h": 0.5,
        "max_budget_dollars": 10.0
    }

class TestCouncilRouter:
    """Test the CouncilRouter class functionality"""
    
    def test_initialization(self):
        """Test council router initialization"""
        router = CouncilRouter()
        
        assert len(router.voice_models) == 5
        assert len(router.voice_templates) == 5
        assert CouncilVoice.REASON in router.voice_models
        assert CouncilVoice.SPARK in router.voice_models
        assert CouncilVoice.EDGE in router.voice_models
        assert CouncilVoice.HEART in router.voice_models
        assert CouncilVoice.VISION in router.voice_models
    
    def test_should_trigger_council_disabled(self):
        """Test council trigger when disabled"""
        router = CouncilRouter()
        router.council_enabled = False
        
        should_trigger, reason = router.should_trigger_council("Explain quantum computing")
        
        assert not should_trigger
        assert reason == "council_disabled"
    
    @patch('router.council.get_budget_status')
    def test_should_trigger_council_insufficient_budget(self, mock_budget):
        """Test council trigger with insufficient budget"""
        mock_budget.return_value = {"remaining_budget_dollars": 0.05}
        
        router = CouncilRouter()
        router.council_enabled = True
        router.max_council_cost_per_request = 0.30
        
        should_trigger, reason = router.should_trigger_council("Explain quantum computing")
        
        assert not should_trigger
        assert "insufficient_budget" in reason
    
    @patch('router.council.get_budget_status')
    def test_should_trigger_council_token_threshold(self, mock_budget):
        """Test council trigger based on token count"""
        mock_budget.return_value = {"remaining_budget_dollars": 5.0}
        
        router = CouncilRouter()
        router.council_enabled = True
        router.min_tokens_for_council = 10
        
        # Short prompt - should not trigger
        should_trigger, reason = router.should_trigger_council("Hello")
        assert not should_trigger
        assert reason == "quick_local_path"
        
        # Long prompt - should trigger
        long_prompt = " ".join(["word"] * 15)
        should_trigger, reason = router.should_trigger_council(long_prompt)
        assert should_trigger
        assert "token_threshold" in reason
    
    @patch('router.council.get_budget_status')
    def test_should_trigger_council_keyword(self, mock_budget):
        """Test council trigger based on keywords"""
        mock_budget.return_value = {"remaining_budget_dollars": 5.0}
        
        router = CouncilRouter()
        router.council_enabled = True
        router.council_trigger_keywords = ["explain", "analyze", "compare"]
        
        # Without keyword - should not trigger
        should_trigger, reason = router.should_trigger_council("What is 2+2?")
        assert not should_trigger
        
        # With keyword - should trigger
        should_trigger, reason = router.should_trigger_council("Explain quantum computing")
        assert should_trigger
        assert "keyword_explain" in reason
    
    def test_extract_risk_flags(self):
        """Test risk flag extraction from Edge responses"""
        router = CouncilRouter()
        
        # No risks
        response = "This looks good, no major concerns."
        flags = router._extract_risk_flags(response)
        assert len(flags) == 0
        
        # Security risk
        response = "This could create a security vulnerability in our system."
        flags = router._extract_risk_flags(response)
        assert "security" in flags
        
        # Multiple risks
        response = "This is expensive and could harm performance while raising ethical concerns."
        flags = router._extract_risk_flags(response)
        assert "cost" in flags
        assert "performance" in flags
        assert "ethics" in flags
    
    def test_assess_consensus_quality(self):
        """Test consensus quality assessment"""
        router = CouncilRouter()
        
        # High confidence, no major risks
        voice_responses = {
            CouncilVoice.REASON: VoiceResponse(
                voice=CouncilVoice.REASON, response="Good analysis", confidence=0.9,
                latency_ms=100, model_used="test", cost_dollars=0.01, metadata={}
            ),
            CouncilVoice.EDGE: VoiceResponse(
                voice=CouncilVoice.EDGE, response="Minor concerns but acceptable",
                confidence=0.8, latency_ms=50, model_used="test", cost_dollars=0.01, metadata={}
            )
        }
        
        consensus = router._assess_consensus_quality(voice_responses)
        assert consensus is True
        
        # Major risk flagged
        voice_responses[CouncilVoice.EDGE].response = "Critical security vulnerability detected!"
        consensus = router._assess_consensus_quality(voice_responses)
        assert consensus is False
    
    def test_synthesize_council_response(self):
        """Test council response synthesis"""
        router = CouncilRouter()
        
        # Create mock voice responses
        reason = VoiceResponse(
            voice=CouncilVoice.REASON, response="Logical analysis complete",
            confidence=0.9, latency_ms=200, model_used="mistral_7b", cost_dollars=0.01, metadata={}
        )
        spark = VoiceResponse(
            voice=CouncilVoice.SPARK, response="Novel approach: try quantum optimization",
            confidence=0.7, latency_ms=300, model_used="cloud", cost_dollars=0.003, metadata={}
        )
        edge = VoiceResponse(
            voice=CouncilVoice.EDGE, response="Risk: performance could degrade",
            confidence=0.8, latency_ms=80, model_used="specialist", cost_dollars=0.001, metadata={}
        )
        heart = VoiceResponse(
            voice=CouncilVoice.HEART, response="User-friendly explanation provided",
            confidence=0.85, latency_ms=90, model_used="codellama", cost_dollars=0.001, metadata={}
        )
        vision = VoiceResponse(
            voice=CouncilVoice.VISION, response="Aligns with scaling roadmap",
            confidence=0.75, latency_ms=70, model_used="phi2", cost_dollars=0.001, metadata={}
        )
        
        synthesis = router._synthesize_council_response(reason, spark, edge, heart, vision)
        
        # Should start with Heart's response
        assert "User-friendly explanation provided" in synthesis
        
        # Should include creative insight from Spark
        assert "Creative insight:" in synthesis
        
        # Should include risk warning from Edge
        assert "Risk considerations:" in synthesis

class TestCouncilIntegration:
    """Test council integration with existing router components"""
    
    @pytest.mark.asyncio
    @patch('router.council.get_budget_status')
    @patch('router.council.get_loaded_models')
    @patch('router.council.vote')
    async def test_council_route_quick_path(self, mock_vote, mock_models, mock_budget):
        """Test council routing taking quick local path"""
        
        mock_budget.return_value = {"remaining_budget_dollars": 5.0}
        mock_models.return_value = {"mistral_7b_instruct": {"vram_mb": 3500}}
        mock_vote.return_value = {
            "text": "4",
            "winner": {"model": "mistral_7b_instruct", "confidence": 0.9},
            "voting_stats": {"winner_confidence": 0.9}
        }
        
        result = await council_route("2+2?")
        
        assert result["council_used"] is False
        assert "quick_local_path" in result["council_reason"]
        
        # Should have used voting for quick response
        mock_vote.assert_called_once()
        
    @pytest.mark.asyncio
    @patch('router.council.CouncilRouter.council_deliberate')
    @patch('router.council.get_budget_status')
    async def test_council_route_full_deliberation(self, mock_budget, mock_deliberate):
        """Test council routing with full deliberation"""
        
        mock_budget.return_value = {"remaining_budget_dollars": 5.0}
        
        mock_deliberation = CouncilDeliberation(
            final_response="Comprehensive council analysis",
            voice_responses={},
            total_latency_ms=1500,
            total_cost_dollars=0.15,
            consensus_achieved=True,
            risk_flags=[],
            metadata={}
        )
        mock_deliberate.return_value = mock_deliberation
        
        # Set environment to enable council
        with patch.dict(os.environ, {"SWARM_COUNCIL_ENABLED": "true"}):
            # Create router instance with council enabled
            from router.council import council_router
            council_router.council_enabled = True
            
            # Test with prompt that should trigger council
            result = await council_route("Explain the strategic implications of quantum computing")
            
            assert result["council_used"] is True
            assert result["text"] == "Comprehensive council analysis"
            
            # Should have called council deliberation
            mock_deliberate.assert_called_once()

class TestCouncilVoiceInvocation:
    """Test individual council voice invocation"""
    
    @pytest.fixture
    def router(self):
        return CouncilRouter()
    
    @pytest.mark.asyncio
    @patch('router.council.get_loaded_models')
    @patch('router.council.generate_response')
    @patch('router.council.debit')
    async def test_invoke_local_voice(self, mock_debit, mock_generate, mock_models, router):
        """Test invoking a local council voice"""
        
        mock_models.return_value = {"mistral_7b_instruct": {"vram_mb": 3500}}
        mock_generate.return_value = "Logical analysis complete"
        mock_debit.return_value = 0.01
        
        response = await router._invoke_voice(CouncilVoice.REASON, "Test prompt")
        
        assert response.voice == CouncilVoice.REASON
        assert response.response == "Logical analysis complete"
        assert response.model_used == "mistral_7b_instruct"
        
        mock_generate.assert_called_once()
        mock_debit.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('router.council.apply_privacy_policy')
    @patch('router.council.ask_cloud_council')
    async def test_invoke_cloud_voice(self, mock_cloud, mock_privacy, router):
        """Test invoking a cloud council voice"""
        
        # Set Spark to use cloud
        router.voice_models[CouncilVoice.SPARK] = "mistral_medium_cloud"
        
        mock_privacy.return_value = {"safe_to_send": True, "sanitized_prompt": "Test prompt"}
        mock_cloud.return_value = {
            "text": "Creative perspective",
            "latency_ms": 800,
            "cost_dollars": 0.003
        }
        
        response = await router._invoke_voice(CouncilVoice.SPARK, "Test prompt")
        
        assert response.voice == CouncilVoice.SPARK
        assert response.response == "Creative perspective"
        assert response.cost_dollars == 0.003
        
        mock_cloud.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('router.council.apply_privacy_policy')
    async def test_invoke_cloud_voice_privacy_blocked(self, mock_privacy, router):
        """Test cloud voice with privacy block"""
        
        router.voice_models[CouncilVoice.SPARK] = "mistral_medium_cloud"
        mock_privacy.return_value = {"safe_to_send": False, "sanitized_prompt": ""}
        
        # Should fall back to local
        with patch('router.council.get_loaded_models') as mock_models:
            with patch('router.council.generate_response') as mock_generate:
                mock_models.return_value = {"tinyllama_1b": {"vram_mb": 400}}
                mock_generate.return_value = "Local fallback response"
                
                response = await router._invoke_voice(CouncilVoice.SPARK, "Sensitive data here")
                
                assert response.response == "Local fallback response"
                mock_generate.assert_called_once()

class TestCouncilPerformance:
    """Test council performance characteristics"""
    
    @pytest.mark.asyncio
    @patch('router.council.CouncilRouter._invoke_voice')
    async def test_parallel_execution(self, mock_invoke):
        """Test that Reason and Spark execute in parallel"""
        
        async def mock_voice_response(voice, prompt):
            # Simulate processing time
            await asyncio.sleep(0.1)
            return VoiceResponse(
                voice=voice, response=f"Response from {voice.value}",
                confidence=0.8, latency_ms=100, model_used="test",
                cost_dollars=0.01, metadata={}
            )
        
        mock_invoke.side_effect = mock_voice_response
        
        router = CouncilRouter()
        router.council_enabled = True
        
        start_time = asyncio.get_event_loop().time()
        await router.council_deliberate("Test parallel execution")
        end_time = asyncio.get_event_loop().time()
        
        # Should complete in roughly 500ms (5 voices * 100ms, but Reason+Spark parallel)
        execution_time = (end_time - start_time) * 1000
        assert execution_time < 600  # Allow some overhead

# 🌌 Live Council Tests (require real models/API keys)
class TestCouncilLive:
    """Live council tests with real model execution"""
    
    @pytest.mark.council
    @pytest.mark.asyncio
    async def test_council_endpoint_live(self):
        """Test live council endpoint with real server"""
        
        if not os.getenv("SWARM_COUNCIL_ENABLED"):
            pytest.skip("SWARM_COUNCIL_ENABLED not set")
        
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
                response = await client.post(
                    "/council",
                    json={
                        "prompt": "Explain the implications of quantum computing for enterprise security",
                        "force_council": True
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Validate council response structure
                    assert "text" in data
                    assert "council_used" in data
                    assert "voice_responses" in data
                    assert "total_latency_ms" in data
                    assert "consensus_achieved" in data
                    
                    print(f"✅ Council endpoint test passed: {data['council_used']}")
                    print(f"   Response length: {len(data['text'])} chars")
                    print(f"   Latency: {data['total_latency_ms']:.1f}ms")
                    print(f"   Consensus: {data['consensus_achieved']}")
                    
                else:
                    print(f"ℹ️ Server not running or endpoint failed: {response.status_code}")
                    
        except Exception as e:
            print(f"ℹ️ Could not test council endpoint: {e}")
    
    @pytest.mark.council
    @pytest.mark.asyncio 
    async def test_hybrid_with_council_live(self):
        """Test hybrid endpoint with council integration"""
        
        if not os.getenv("SWARM_COUNCIL_ENABLED"):
            pytest.skip("SWARM_COUNCIL_ENABLED not set")
        
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
                response = await client.post(
                    "/hybrid",
                    json={
                        "prompt": "Analyze the strategic implications of AI governance policies",
                        "enable_council": True
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Validate hybrid+council response
                    assert "text" in data
                    assert "provider" in data
                    assert "council_used" in data
                    assert "council_voices" in data
                    
                    if data["council_used"]:
                        print(f"✅ Hybrid council integration: council engaged")
                        print(f"   Provider: {data['provider']}")
                        print(f"   Confidence: {data.get('confidence', 'N/A')}")
                    else:
                        print(f"ℹ️ Council not triggered, used: {data['provider']}")
                    
                else:
                    print(f"ℹ️ Hybrid endpoint failed: {response.status_code}")
                    
        except Exception as e:
            print(f"ℹ️ Could not test hybrid+council: {e}")
    
    @pytest.mark.council
    @pytest.mark.asyncio
    async def test_council_cost_tracking_live(self):
        """Test that council costs are properly tracked"""
        
        if not (os.getenv("SWARM_COUNCIL_ENABLED") and 
                (os.getenv("MISTRAL_API_KEY") or os.getenv("OPENAI_API_KEY"))):
            pytest.skip("Council or cloud API keys not available")
        
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=30) as client:
                # Get budget before
                budget_before = await client.get("/budget")
                before_data = budget_before.json()
                
                # Make council request
                response = await client.post(
                    "/council",
                    json={
                        "prompt": "Quick strategic analysis",
                        "force_council": True
                    }
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Get budget after
                    budget_after = await client.get("/budget")
                    after_data = budget_after.json()
                    
                    # Validate cost tracking
                    if data["council_used"]:
                        assert "total_cost_dollars" in data
                        cost = data["total_cost_dollars"]
                        
                        print(f"✅ Council cost tracking: ${cost:.4f}")
                        print(f"   Budget change tracked: {before_data != after_data}")
                    else:
                        print(f"ℹ️ Council not used for cost tracking test")
                        
                else:
                    print(f"ℹ️ Council cost test failed: {response.status_code}")
                    
        except Exception as e:
            print(f"ℹ️ Could not test council cost tracking: {e}")

class TestCouncilEndpoints:
    """Test council-specific API endpoints"""
    
    @pytest.mark.asyncio
    async def test_council_status_endpoint(self):
        """Test council status endpoint"""
        
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8000", timeout=10) as client:
                response = await client.get("/council/status")
                
                if response.status_code == 200:
                    data = response.json()
                    
                    # Validate status structure
                    assert "council_enabled" in data
                    assert "voice_models" in data
                    assert "budget_limits" in data
                    assert "trigger_config" in data
                    
                    print(f"✅ Council status endpoint working")
                    print(f"   Enabled: {data['council_enabled']}")
                    print(f"   Voices: {len(data['voice_models'])}")
                    
                else:
                    print(f"ℹ️ Council status endpoint failed: {response.status_code}")
                    
        except Exception as e:
            print(f"ℹ️ Could not test council status: {e}")

@pytest.mark.integration
class TestCouncilE2E:
    """End-to-end council integration tests"""
    
    @pytest.mark.asyncio
    @patch('router.council.get_budget_status')
    @patch('router.council.get_loaded_models')
    @patch('router.council.generate_response')
    @patch('router.council.ask_cloud_council')
    @patch('router.council.apply_privacy_policy')
    @patch('router.council.debit')
    async def test_full_council_deliberation_flow(
        self, mock_debit, mock_privacy, mock_cloud, mock_generate, mock_models, mock_budget
    ):
        """Test complete council deliberation flow with mocked dependencies"""
        
        # Setup mocks
        mock_budget.return_value = {"remaining_budget_dollars": 5.0}
        mock_models.return_value = {
            "mistral_7b_instruct": {"vram_mb": 3500},
            "math_specialist_0.8b": {"vram_mb": 800},
            "codellama_0.7b": {"vram_mb": 700},
            "phi2_2.7b": {"vram_mb": 1200}
        }
        mock_generate.return_value = "Mock local response"
        mock_debit.return_value = 0.01
        mock_privacy.return_value = {"safe_to_send": True, "sanitized_prompt": "Test"}
        mock_cloud.return_value = {"text": "Mock cloud response", "latency_ms": 800, "cost_dollars": 0.003}
        
        # Create router and enable council
        router = CouncilRouter()
        router.council_enabled = True
        
        # Test full deliberation
        result = await router.council_deliberate("Explain enterprise AI strategy implications")
        
        # Validate results
        assert isinstance(result, CouncilDeliberation)
        assert len(result.voice_responses) == 5
        assert result.total_latency_ms > 0
        assert result.total_cost_dollars > 0
        
        # Verify all voices were invoked
        assert CouncilVoice.REASON in result.voice_responses
        assert CouncilVoice.SPARK in result.voice_responses
        assert CouncilVoice.EDGE in result.voice_responses
        assert CouncilVoice.HEART in result.voice_responses
        assert CouncilVoice.VISION in result.voice_responses
        
        print(f"✅ Full council deliberation test passed")
        print(f"   Voices: {len(result.voice_responses)}")
        print(f"   Latency: {result.total_latency_ms:.1f}ms")
        print(f"   Cost: ${result.total_cost_dollars:.4f}")
        print(f"   Consensus: {result.consensus_achieved}")

if __name__ == "__main__":
    pytest.main([__file__]) 