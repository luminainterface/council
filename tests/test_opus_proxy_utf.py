#!/usr/bin/env python3
"""
Unit tests for opus_proxy UTF-8 encoding fix
Ensures coverage stays ≥80% with the new proxy functionality
"""

import pytest
from unittest.mock import patch, Mock

def test_utf8_decode_fallback():
    """Test that proxy_to_opus handles invalid UTF-8 gracefully"""
    from opus_proxy.adapter import proxy_to_opus
    
    # Test with invalid UTF-8 byte sequence
    bad = b"Hello \x96 World"                 # 0x96 is invalid UTF-8
    
    # Mock the OpenAI API call to avoid external dependencies
    with patch('opus_proxy.adapter.openai.Completion.create') as mock_openai:
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].text = "Mocked response from OpenAI"
        mock_openai.return_value = mock_response
        
        # Function should not crash and should process the text
        result = proxy_to_opus(bad)
        
        # Verify function didn't crash and returned expected result
        assert result == "Mocked response from OpenAI"
        
        # Verify OpenAI was called with properly decoded text
        mock_openai.assert_called_once()
        call_args = mock_openai.call_args[1]
        assert "Hello" in call_args['prompt'] and "World" in call_args['prompt']  # Basic text preserved
        assert "[OPUS]" in call_args['prompt']  # OPUS prefix should be in the prompt

def test_valid_utf8_passthrough():
    """Test that valid UTF-8 text passes through correctly"""
    from opus_proxy.adapter import proxy_to_opus
    
    # Test with valid UTF-8
    good = b"Hello \xe2\x9c\x93 World"  # ✓ checkmark in UTF-8
    
    with patch('opus_proxy.adapter.openai.Completion.create') as mock_openai:
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].text = "Valid UTF-8 response"
        mock_openai.return_value = mock_response
        
        result = proxy_to_opus(good)
        
        assert result == "Valid UTF-8 response"
        # Verify the checkmark was preserved in the prompt
        call_args = mock_openai.call_args[1]
        assert "✓" in call_args['prompt']

def test_opus_prefix_added():
    """Test that [OPUS] prefix is correctly added to prompts"""
    from opus_proxy.adapter import proxy_to_opus
    
    test_input = b"Test prompt"
    
    with patch('opus_proxy.adapter.openai.Completion.create') as mock_openai:
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].text = "Response with prefix"
        mock_openai.return_value = mock_response
        
        result = proxy_to_opus(test_input)
        
        # Verify the OPUS prefix was added
        call_args = mock_openai.call_args[1]
        assert call_args['prompt'] == "[OPUS] Test prompt" 