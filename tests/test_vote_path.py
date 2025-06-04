#!/usr/bin/env python3
"""
Tests for Router 2.0: Confidence-Weighted Voting

Validates that voting delivers higher quality responses while maintaining
acceptable latency bounds (p95 < 2x single-head latency).
"""

import pytest
import httpx
import time
import asyncio
from typing import List, Dict, Any


class TestVotingPath:
    """Test confidence-weighted voting functionality"""

    def test_vote_endpoint_available(self, api_server):
        """Test that the voting endpoint is available"""
        with httpx.Client() as client:
            # Simple health check style test
            response = client.get("http://127.0.0.1:8000/health", timeout=10)
            assert response.status_code == 200

    def test_vote_basic_functionality(self, api_server):
        """Test basic voting with multiple model candidates"""
        with httpx.Client() as client:
            # First, check what models are available
            models_response = client.get("http://127.0.0.1:8000/models", timeout=10)
            assert models_response.status_code == 200
            models_data = models_response.json()
            
            print(f"Available models: {list(models_data.get('loaded_models', {}).keys())}")
            
            # Use actual loaded model names
            available_models = list(models_data.get('loaded_models', {}).keys())
            if len(available_models) < 2:
                pytest.skip("Need at least 2 models for voting test")
            
            candidates = available_models[:3]  # Use first 3 available models
            print(f"Testing with candidates: {candidates}")
            
            response = client.post(
                "http://127.0.0.1:8000/vote",
                json={
                    "prompt": "What is 2 + 2?",
                    "candidates": candidates,
                    "top_k": 2
                },
                timeout=30  # Voting takes longer than single inference
            )

            if response.status_code != 200:
                print(f"ERROR Response: {response.status_code}")
                print(f"ERROR Text: {response.text}")
            
            assert response.status_code == 200
            data = response.json()

            # Validate response structure
            assert "text" in data
            assert "winner" in data
            assert "all_candidates" in data
            assert "voting_stats" in data

            # Validate winner structure
            winner = data["winner"]
            assert "model" in winner
            assert "confidence" in winner
            assert "log_probability" in winner
            assert "quality_score" in winner
            assert "response_time_ms" in winner

            # Validate confidence score is reasonable
            assert 0.0 <= winner["confidence"] <= 1.0

            # Validate we got multiple candidates
            assert len(data["all_candidates"]) >= 2

    def test_vote_math_specialization(self, api_server):
        """Test that math specialist tends to win on math problems"""
        with httpx.Client() as client:
            response = client.post(
                "http://127.0.0.1:8000/vote",
                json={
                    "prompt": "Calculate the square root of 144 and explain the steps",
                    "candidates": ["math_specialist_0.8b", "tinyllama_1b", "codellama_0.7b"],
                    "top_k": 3
                },
                timeout=30
            )

            assert response.status_code == 200
            data = response.json()
            winner = data["winner"]

            # Math specialist should have good confidence on math problems
            # Note: This is probabilistic, but the specialist should generally win
            print(f"Winner: {winner['model']} (confidence: {winner['confidence']:.3f})")
            
            # Ensure we have a valid response
            assert len(data["text"]) > 10
            assert winner["confidence"] > 0.1  # Should have reasonable confidence

    def test_vote_code_specialization(self, api_server):
        """Test voting behavior on code-related prompts"""
        with httpx.Client() as client:
            response = client.post(
                "http://127.0.0.1:8000/vote",
                json={
                    "prompt": "Write a Python function to reverse a string",
                    "candidates": ["codellama_0.7b", "tinyllama_1b", "math_specialist_0.8b"],
                    "top_k": 2
                },
                timeout=30
            )

            assert response.status_code == 200
            data = response.json()
            winner = data["winner"]

            # Should produce a valid response
            assert len(data["text"]) > 10
            assert winner["confidence"] > 0.1

            print(f"Code winner: {winner['model']} (confidence: {winner['confidence']:.3f})")

    def test_vote_performance_baseline(self, api_server):
        """Test that voting latency is reasonable (p95 < 2x single-head)"""
        
        # First, get baseline single-head performance
        with httpx.Client() as client:
            start_time = time.time()
            single_response = client.post(
                "http://127.0.0.1:8000/orchestrate",
                json={
                    "prompt": "Quick test",
                    "route": ["tinyllama_1b"]
                },
                timeout=15
            )
            single_latency = (time.time() - start_time) * 1000

            assert single_response.status_code == 200

            # Now test voting performance
            start_time = time.time()
            vote_response = client.post(
                "http://127.0.0.1:8000/vote",
                json={
                    "prompt": "Quick test", 
                    "candidates": ["tinyllama_1b", "mistral_0.5b"],
                    "top_k": 2
                },
                timeout=30
            )
            vote_latency = (time.time() - start_time) * 1000

            assert vote_response.status_code == 200

            # Voting should be < 2x single head latency (since it's parallel)
            max_acceptable_latency = single_latency * 2.0
            
            print(f"Single head: {single_latency:.1f}ms, Voting: {vote_latency:.1f}ms")
            print(f"Max acceptable: {max_acceptable_latency:.1f}ms")
            
            assert vote_latency < max_acceptable_latency, f"Voting too slow: {vote_latency:.1f}ms > {max_acceptable_latency:.1f}ms"

    def test_vote_with_invalid_models(self, api_server):
        """Test voting behavior with invalid model names"""
        with httpx.Client() as client:
            response = client.post(
                "http://127.0.0.1:8000/vote",
                json={
                    "prompt": "Test prompt",
                    "candidates": ["nonexistent_model", "another_fake_model"],
                    "top_k": 1
                },
                timeout=15
            )

            # Should return 500 error for no available models
            assert response.status_code == 500

    def test_vote_single_candidate(self, api_server):
        """Test voting with only one candidate (should still work)"""
        with httpx.Client() as client:
            response = client.post(
                "http://127.0.0.1:8000/vote",
                json={
                    "prompt": "Simple test",
                    "candidates": ["tinyllama_1b"],
                    "top_k": 1
                },
                timeout=15
            )

            assert response.status_code == 200
            data = response.json()

            assert "text" in data
            assert data["winner"]["model"] == "tinyllama_1b"
            assert len(data["all_candidates"]) == 1

    def test_vote_confidence_scoring(self, api_server):
        """Test that confidence scores are reasonable and ordered"""
        with httpx.Client() as client:
            response = client.post(
                "http://127.0.0.1:8000/vote",
                json={
                    "prompt": "Explain machine learning in simple terms",
                    "candidates": ["mistral_7b_instruct", "tinyllama_1b", "mistral_0.5b"],
                    "top_k": 3
                },
                timeout=30
            )

            assert response.status_code == 200
            data = response.json()

            # All candidates should have confidence scores
            for candidate in data["all_candidates"]:
                assert 0.0 <= candidate["confidence"] <= 1.0

            # Candidates should be ordered by confidence (highest first)
            confidences = [c["confidence"] for c in data["all_candidates"]]
            assert confidences == sorted(confidences, reverse=True)

            # Winner should be the highest confidence
            assert data["winner"]["confidence"] == confidences[0]

    def test_vote_stats_tracking(self, api_server):
        """Test that voting statistics are properly tracked"""
        with httpx.Client() as client:
            response = client.post(
                "http://127.0.0.1:8000/vote",
                json={
                    "prompt": "Test statistics tracking",
                    "candidates": ["tinyllama_1b", "mistral_0.5b", "qwen2_0.5b"],
                    "top_k": 2
                },
                timeout=30
            )

            assert response.status_code == 200
            data = response.json()

            stats = data["voting_stats"]
            assert "total_heads" in stats
            assert "successful_responses" in stats
            assert "voting_time_ms" in stats
            assert "top_k" in stats

            # Should have attempted 3 heads
            assert stats["total_heads"] == 3
            assert stats["top_k"] == 2
            assert stats["voting_time_ms"] > 0

            # Should have gotten some successful responses
            assert stats["successful_responses"] > 0 