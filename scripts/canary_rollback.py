#!/usr/bin/env python3
"""
🔄 Automated Canary Rollback Script
Responds to Prometheus alerts and automatically rolls back failing canaries
"""

import asyncio
import json
import logging
import time
import sys
from datetime import datetime
from pathlib import Path

import aiohttp
import requests

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CanaryController:
    def __init__(self):
        self.traefik_api = "http://traefik:8080/api"
        self.api_endpoint = "http://api:9000"
        self.pushgateway_url = "http://pushgateway:9091"
        
    async def get_current_weights(self):
        """Get current traffic weights from Traefik"""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.traefik_api}/http/services/api-weighted") as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        weights = {}
                        for service in data.get("weighted", {}).get("services", []):
                            weights[service["name"]] = service["weight"]
                        return weights
                    return {}
        except Exception as e:
            logger.error(f"❌ Failed to get Traefik weights: {e}")
            return {}

    async def set_canary_weight(self, weight: int):
        """Set canary traffic weight (0-100)"""
        try:
            config = {
                "http": {
                    "services": {
                        "api-weighted": {
                            "weighted": {
                                "services": [
                                    {"name": "api-production", "weight": 100 - weight},
                                    {"name": "api-canary", "weight": weight}
                                ]
                            }
                        }
                    }
                }
            }
            
            # Write new config
            config_path = Path("traefik/dynamic/canary.yml")
            config_path.parent.mkdir(exist_ok=True)
            
            with open(config_path, "w") as f:
                import yaml
                yaml.dump(config, f, default_flow_style=False)
            
            logger.info(f"🎛️ Updated canary weight to {weight}%")
            
            # Push metric
            self.push_metric("canary_weight_percent", weight)
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to set canary weight: {e}")
            return False

    async def rollback_canary(self, reason: str = "regression_detected"):
        """Execute emergency rollback to production"""
        logger.warning(f"🚨 CANARY ROLLBACK INITIATED: {reason}")
        
        try:
            # Set weight to 0 (full production)
            success = await self.set_canary_weight(0)
            
            if success:
                # Log rollback event
                self.push_metric("canary_rollback_total", 1)
                
                # Notify API
                await self.notify_api("rollback", {
                    "reason": reason,
                    "timestamp": time.time(),
                    "action": "emergency_rollback"
                })
                
                # Slack notification (if configured)
                await self.send_slack_notification(
                    f"🚨 CANARY ROLLBACK COMPLETE\n"
                    f"Reason: {reason}\n"
                    f"Traffic restored to production\n"
                    f"Time: {datetime.now().isoformat()}"
                )
                
                logger.info("✅ Canary rollback completed successfully")
                return True
            else:
                logger.error("❌ Canary rollback failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
            return False

    async def promote_canary(self, target_weight: int = 25):
        """Promote canary to higher traffic percentage"""
        logger.info(f"📈 CANARY PROMOTION: {target_weight}%")
        
        try:
            success = await self.set_canary_weight(target_weight)
            
            if success:
                self.push_metric("canary_promotion_total", 1)
                
                await self.notify_api("promote", {
                    "weight": target_weight,
                    "timestamp": time.time()
                })
                
                await self.send_slack_notification(
                    f"📈 CANARY PROMOTED\n"
                    f"New weight: {target_weight}%\n"
                    f"Performance: Healthy\n"
                    f"Time: {datetime.now().isoformat()}"
                )
                
                logger.info(f"✅ Canary promoted to {target_weight}%")
                return True
            else:
                logger.error("❌ Canary promotion failed")
                return False
                
        except Exception as e:
            logger.error(f"❌ Promotion failed: {e}")
            return False

    async def notify_api(self, event: str, data: dict):
        """Notify API of canary events"""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.api_endpoint}/admin/canary/webhook/{event}"
                async with session.post(url, json=data) as resp:
                    if resp.status == 200:
                        logger.debug(f"📡 API notified: {event}")
                    else:
                        logger.warning(f"⚠️ API notification failed: {resp.status}")
        except Exception as e:
            logger.warning(f"⚠️ API notification error: {e}")

    async def send_slack_notification(self, message: str):
        """Send Slack notification (if webhook configured)"""
        try:
            import os
            webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
            if not webhook_url:
                return
                
            payload = {
                "text": f"🌀 Spiral Canary Alert\n{message}",
                "username": "canary-bot",
                "channel": "#alerts"
            }
            
            response = requests.post(webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.debug("📱 Slack notification sent")
                
        except Exception as e:
            logger.warning(f"📱 Slack notification failed: {e}")

    def push_metric(self, name: str, value: float):
        """Push metric to Pushgateway"""
        try:
            metric_data = f"# TYPE {name} counter\n{name} {value}\n"
            
            response = requests.post(
                f"{self.pushgateway_url}/metrics/job/canary_controller/instance/main",
                data=metric_data,
                headers={"Content-Type": "text/plain"},
                timeout=5
            )
            
            if response.status_code == 200:
                logger.debug(f"📊 Metric pushed: {name}={value}")
                
        except Exception as e:
            logger.warning(f"📊 Metric push failed: {e}")

    async def handle_alert(self, alert_data: dict):
        """Handle incoming Prometheus alert"""
        try:
            alert_name = alert_data.get("commonLabels", {}).get("alertname", "unknown")
            action = alert_data.get("commonLabels", {}).get("action", "")
            
            logger.info(f"🚨 Alert received: {alert_name} (action: {action})")
            
            if action == "rollback":
                await self.rollback_canary(f"alert_{alert_name}")
            elif action == "promote":
                await self.promote_canary()
            else:
                logger.info(f"ℹ️ No action defined for alert: {alert_name}")
                
        except Exception as e:
            logger.error(f"❌ Alert handling failed: {e}")

async def main():
    """Main entry point for webhook server mode"""
    controller = CanaryController()
    
    if len(sys.argv) > 1:
        # Command line mode
        action = sys.argv[1]
        
        if action == "rollback":
            reason = sys.argv[2] if len(sys.argv) > 2 else "manual"
            await controller.rollback_canary(reason)
        elif action == "promote":
            weight = int(sys.argv[2]) if len(sys.argv) > 2 else 25
            await controller.promote_canary(weight)
        elif action == "weights":
            weights = await controller.get_current_weights()
            print(json.dumps(weights, indent=2))
        else:
            print("Usage: python canary_rollback.py [rollback|promote|weights] [args...]")
            sys.exit(1)
    else:
        # Webhook server mode (future enhancement)
        logger.info("🎛️ Canary controller ready")
        print("Run with arguments for direct control:")
        print("  python canary_rollback.py rollback [reason]")
        print("  python canary_rollback.py promote [weight]")
        print("  python canary_rollback.py weights")

if __name__ == "__main__":
    asyncio.run(main()) 