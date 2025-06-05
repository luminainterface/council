#!/usr/bin/env python3
"""
Intent-to-Action Mapper - Week 2 Final Push
===========================================

Maps classified intents to specific action handlers.
Implements the INTENT_TO_ACTION pattern from the grab-and-go kit.
"""

import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# ===== ACTION CLASSES =====

class BaseAction(ABC):
    """Base class for all actions"""
    
    @abstractmethod
    async def run(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute the action"""
        pass

class FileCreateAction(BaseAction):
    """Create a new file with content"""
    
    async def run(self, filename: str, content: str = "", permissions: str = "644") -> Dict[str, Any]:
        try:
            from action_handlers.os_executor_fixed import get_executor
            executor = get_executor()
            
            # Send file creation job to Redis queue
            import redis
            import json
            import uuid
            
            job_id = str(uuid.uuid4())
            code = f"""
import os
with open({repr(filename)}, 'w') as f:
    f.write({repr(content)})
os.chmod({repr(filename)}, 0o{permissions})
print(f"Created {{repr(filename)}} with {{len(content)}} chars")
"""
            
            job = {"id": job_id, "code": code}
            r = redis.Redis()
            r.lpush("swarm:exec:q", json.dumps(job))
            
            # Wait for response
            import time
            for _ in range(30):  # 30 second timeout
                result = r.blpop("swarm:exec:resp", timeout=1)
                if result:
                    response = json.loads(result[1])
                    if response["id"] == job_id:
                        return {
                            "success": response["ok"],
                            "output": response["stdout"],
                            "error": response.get("stderr", ""),
                            "action": "file_create"
                        }
                        
            return {"success": False, "error": "Timeout waiting for file creation"}
            
        except Exception as e:
            logger.error(f"File creation failed: {e}")
            return {"success": False, "error": str(e)}

class FileWriteAction(BaseAction):
    """Write content to an existing file"""
    
    async def run(self, filename: str, content: str, mode: str = "w") -> Dict[str, Any]:
        try:
            from action_handlers.os_executor_fixed import get_executor
            import redis, json, uuid
            
            job_id = str(uuid.uuid4())
            code = f"""
with open({repr(filename)}, {repr(mode)}) as f:
    f.write({repr(content)})
print(f"Wrote {{len(content)}} chars to {{repr(filename)}}")
"""
            
            job = {"id": job_id, "code": code}
            r = redis.Redis()
            r.lpush("swarm:exec:q", json.dumps(job))
            
            # Wait for response
            for _ in range(30):
                result = r.blpop("swarm:exec:resp", timeout=1)
                if result:
                    response = json.loads(result[1])
                    if response["id"] == job_id:
                        return {
                            "success": response["ok"],
                            "output": response["stdout"],
                            "action": "file_write"
                        }
                        
            return {"success": False, "error": "Timeout"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

class PackageInstallAction(BaseAction):
    """Install system packages"""
    
    async def run(self, package_name: str, package_manager: str = "auto") -> Dict[str, Any]:
        try:
            import redis, json, uuid
            
            job_id = str(uuid.uuid4())
            
            # Detect package manager if auto
            if package_manager == "auto":
                detect_code = """
import shutil
if shutil.which('apt-get'):
    pm = 'apt-get'
elif shutil.which('yum'):
    pm = 'yum'
elif shutil.which('dnf'):
    pm = 'dnf'
elif shutil.which('pacman'):
    pm = 'pacman'
else:
    pm = 'unknown'
print(f"PACKAGE_MANAGER: {pm}")
"""
            else:
                detect_code = f'print("PACKAGE_MANAGER: {package_manager}")'
            
            code = f"""
{detect_code}
import subprocess
import os

# Get package manager
pm_result = subprocess.run(['python', '-c', '''{detect_code}'''], 
                          capture_output=True, text=True)
pm = pm_result.stdout.split(': ')[1].strip()

if pm == 'apt-get':
    cmd = ['sudo', 'apt-get', 'install', '-y', {repr(package_name)}]
elif pm == 'yum':
    cmd = ['sudo', 'yum', 'install', '-y', {repr(package_name)}]
elif pm == 'dnf':
    cmd = ['sudo', 'dnf', 'install', '-y', {repr(package_name)}]
else:
    print(f"ERROR: Unsupported package manager: {{pm}}")
    exit(1)

print(f"Installing {{repr(package_name)}} with {{pm}}...")
result = subprocess.run(cmd, capture_output=True, text=True)
print(f"Exit code: {{result.returncode}}")
print(f"STDOUT: {{result.stdout}}")
if result.stderr:
    print(f"STDERR: {{result.stderr}}")
"""
            
            job = {"id": job_id, "code": code}
            r = redis.Redis()
            r.lpush("swarm:exec:q", json.dumps(job))
            
            # Wait for response
            for _ in range(120):  # 2 minute timeout for package installs
                result = r.blpop("swarm:exec:resp", timeout=1)
                if result:
                    response = json.loads(result[1])
                    if response["id"] == job_id:
                        return {
                            "success": response["ok"],
                            "output": response["stdout"],
                            "action": "package_install"
                        }
                        
            return {"success": False, "error": "Package install timeout"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

class ServiceRestartAction(BaseAction):
    """Restart system services"""
    
    async def run(self, service_name: str) -> Dict[str, Any]:
        try:
            import redis, json, uuid
            
            job_id = str(uuid.uuid4())
            code = f"""
import subprocess
import platform

service = {repr(service_name)}

if platform.system() == 'Linux':
    # Try systemd first
    try:
        result = subprocess.run(['sudo', 'systemctl', 'restart', service], 
                              capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print(f"Service {{service}} restarted successfully via systemctl")
            status_result = subprocess.run(['sudo', 'systemctl', 'status', service], 
                                         capture_output=True, text=True)
            print(f"Status: {{status_result.stdout}}")
        else:
            print(f"systemctl failed: {{result.stderr}}")
    except Exception as e:
        print(f"systemctl error: {{e}}")
        
        # Fallback to service command
        try:
            result = subprocess.run(['sudo', 'service', service, 'restart'], 
                                  capture_output=True, text=True, timeout=30)
            print(f"Service restart via service command: {{result.returncode}}")
            print(result.stdout)
        except Exception as e2:
            print(f"Service restart failed: {{e2}}")
            
elif platform.system() == 'Windows':
    # Windows service restart
    try:
        result = subprocess.run(['sc', 'stop', service], capture_output=True, text=True)
        print(f"Stop result: {{result.returncode}}")
        import time
        time.sleep(2)
        result = subprocess.run(['sc', 'start', service], capture_output=True, text=True) 
        print(f"Start result: {{result.returncode}}")
        print(result.stdout)
    except Exception as e:
        print(f"Windows service restart failed: {{e}}")
else:
    print(f"Unsupported platform: {{platform.system()}}")
"""
            
            job = {"id": job_id, "code": code}
            r = redis.Redis()
            r.lpush("swarm:exec:q", json.dumps(job))
            
            # Wait for response
            for _ in range(60):  # 1 minute timeout
                result = r.blpop("swarm:exec:resp", timeout=1)
                if result:
                    response = json.loads(result[1])
                    if response["id"] == job_id:
                        return {
                            "success": response["ok"],
                            "output": response["stdout"],
                            "action": "service_restart"
                        }
                        
            return {"success": False, "error": "Service restart timeout"}
            
        except Exception as e:
            return {"success": False, "error": str(e)}

# ===== INTENT TO ACTION MAPPING =====

INTENT_TO_ACTION = {
    "os_file_create": FileCreateAction,
    "os_file_write": FileWriteAction,       # 🚀 NEW
    "package_install": PackageInstallAction, # 🚀 NEW  
    "service_restart": ServiceRestartAction,  # 🚀 NEW
}

# ===== EXCEPTION CLASSES =====

class UnsupportedIntent(Exception):
    """Raised when intent is not supported"""
    pass

# ===== MAIN HANDLER FUNCTION =====

async def handle_intent(intent_name: str, **kwargs) -> Dict[str, Any]:
    """
    Main intent handler function from grab-and-go kit
    
    Args:
        intent_name: The classified intent name
        **kwargs: Arguments for the action
        
    Returns:
        Dict with action results
        
    Raises:
        UnsupportedIntent: If intent is not mapped to an action
    """
    if intent_name not in INTENT_TO_ACTION:
        raise UnsupportedIntent(f"Intent '{intent_name}' not supported. Available: {list(INTENT_TO_ACTION.keys())}")
    
    action_class = INTENT_TO_ACTION[intent_name]
    action_instance = action_class()
    
    logger.info(f"🎯 Executing intent: {intent_name} with args: {kwargs}")
    
    try:
        result = await action_instance.run(**kwargs)
        logger.info(f"✅ Intent {intent_name} completed: {result.get('success', False)}")
        return result
    except Exception as e:
        logger.error(f"❌ Intent {intent_name} failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "action": intent_name
        }

# ===== UTILITY FUNCTIONS =====

def get_supported_intents() -> list:
    """Get list of supported intent names"""
    return list(INTENT_TO_ACTION.keys())

def is_intent_supported(intent_name: str) -> bool:
    """Check if an intent is supported"""
    return intent_name in INTENT_TO_ACTION

if __name__ == "__main__":
    # Test the intent mapper
    import asyncio
    
    async def test_intent_mapper():
        print("🧪 Testing Intent Mapper")
        print("=" * 40)
        
        test_cases = [
            ("os_file_create", {"filename": "test.txt", "content": "Hello World!"}),
            ("os_file_write", {"filename": "test.txt", "content": "Updated content"}),
            # Note: package_install and service_restart require sudo, skip in test
        ]
        
        for intent, kwargs in test_cases:
            print(f"\n🎯 Testing intent: {intent}")
            try:
                result = await handle_intent(intent, **kwargs)
                print(f"   Result: {result}")
            except Exception as e:
                print(f"   Error: {e}")
        
        # Test unsupported intent
        print(f"\n🎯 Testing unsupported intent")
        try:
            await handle_intent("unsupported_intent")
        except UnsupportedIntent as e:
            print(f"   Expected error: {e}")
    
    asyncio.run(test_intent_mapper()) 