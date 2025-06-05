from locust import HttpUser, task, between
import json
import random

class Agent0User(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when a simulated user starts"""
        self.test_messages = [
            "Hello, how are you?",
            "What's the weather like?",
            "Can you help me with a quick question?",
            "Tell me a short joke",
            "What time is it?",
            "Ping",
            "Test message",
            "Hello Agent-0"
        ]
    
    @task(3)
    def health_check(self):
        """Health endpoint - frequent calls"""
        self.client.get("/health")
    
    @task(2)
    def metrics_check(self):
        """Metrics endpoint - moderate calls"""
        self.client.get("/metrics")
    
    @task(1)
    def chat_exchange(self):
        """Chat endpoint - less frequent but more important"""
        message = random.choice(self.test_messages)
        response = self.client.post(
            "/chat",
            json={"message": message},
            headers={"Content-Type": "application/json"}
        )
        
        # Validate response structure
        if response.status_code == 200:
            try:
                data = response.json()
                if "response" not in data:
                    self.client.log.warning(f"Missing 'response' field in chat response")
            except json.JSONDecodeError:
                self.client.log.warning(f"Invalid JSON in chat response")
    
    @task(1)
    def memory_check(self):
        """Memory endpoint - occasional calls"""
        self.client.get("/memory")