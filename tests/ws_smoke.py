#!/usr/bin/env python3
"""
WebSocket Smoke Test for Agent-0 Chat Interface
Quick connectivity test for localhost:8765
"""

import websocket
import json
import time
import sys

def test_websocket_chat():
    """Test basic WebSocket connectivity and response"""
    try:
        # Connect to WebSocket endpoint
        ws = websocket.create_connection("ws://localhost:8765", timeout=10)
        print("✅ WebSocket connection established")
        
        # Send test message
        test_message = {"message": "hello"}
        ws.send(json.dumps(test_message))
        print(f"📤 Sent: {test_message}")
        
        # Receive response with timeout
        ws.settimeout(10)
        response = ws.recv()
        print(f"📥 Received: {response}")
        
        # Verify response contains agent0 reference
        if "agent0" in response.lower():
            print("✅ Response contains 'agent0' - test passed")
            result = True
        else:
            print("❌ Response missing 'agent0' reference")
            result = False
            
        # Clean close
        ws.close()
        return result
        
    except websocket.WebSocketTimeoutException:
        print("❌ WebSocket timeout - service may not be ready")
        return False
    except ConnectionRefusedError:
        print("❌ Connection refused - WebSocket service not running on port 8765")
        return False
    except Exception as e:
        print(f"❌ WebSocket test failed: {e}")
        return False

if __name__ == "__main__":
    success = test_websocket_chat()
    sys.exit(0 if success else 1) 