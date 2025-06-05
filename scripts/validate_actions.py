#!/usr/bin/env python3
"""
Stage 1: Schema sanity - actions.json syntactically valid and contract-safe
Checks executor ∈ {shell, cloud, internal} + primitive arg types
"""

import json
import sys
from pathlib import Path
from typing import Dict, Any, List

def validate_action_schema(action: Dict[str, Any], action_name: str) -> List[str]:
    """Validate a single action against contract requirements"""
    errors = []
    
    # Required fields
    required_fields = ['name', 'executor', 'args', 'timeout_ms']
    for field in required_fields:
        if field not in action:
            errors.append(f"{action_name}: Missing required field '{field}'")
    
    # Executor validation
    valid_executors = {'shell', 'cloud', 'internal'}
    executor = action.get('executor', '')
    if executor not in valid_executors:
        errors.append(f"{action_name}: Invalid executor '{executor}', must be one of {valid_executors}")
    
    # Args validation - must be dict with primitive types
    args = action.get('args', {})
    if not isinstance(args, dict):
        errors.append(f"{action_name}: 'args' must be a dictionary")
    else:
        for arg_name, arg_spec in args.items():
            if not isinstance(arg_spec, str):
                errors.append(f"{action_name}.{arg_name}: arg type must be string (e.g., 'string', 'int', 'bool')")
            elif arg_spec not in {'string', 'int', 'float', 'bool', 'list', 'dict'}:
                errors.append(f"{action_name}.{arg_name}: invalid type '{arg_spec}', must be primitive type")
    
    # Timeout validation
    timeout = action.get('timeout_ms', 0)
    if not isinstance(timeout, int) or timeout <= 0:
        errors.append(f"{action_name}: timeout_ms must be positive integer")
    
    # Security validation for shell executor
    if executor == 'shell':
        if 'command_template' not in action:
            errors.append(f"{action_name}: shell executor requires 'command_template'")
        else:
            template = action['command_template']
            # Check for dangerous patterns
            dangerous_patterns = ['rm -rf', 'format', 'mkfs', 'dd if=', '> /dev/']
            for pattern in dangerous_patterns:
                if pattern in template.lower():
                    errors.append(f"{action_name}: dangerous pattern '{pattern}' in command_template")
    
    return errors

def main():
    """Validate actions.json schema and contracts"""
    print("🔍 Stage 1: Validating actions.json schema...")
    
    actions_file = Path("actions.json")
    if not actions_file.exists():
        print("❌ actions.json not found")
        return 1
    
    try:
        with open(actions_file) as f:
            actions_data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in actions.json: {e}")
        return 1
    
    if not isinstance(actions_data, dict):
        print("❌ actions.json must contain a JSON object")
        return 1
    
    if 'actions' not in actions_data:
        print("❌ actions.json must have 'actions' key")
        return 1
    
    actions = actions_data['actions']
    if not isinstance(actions, list):
        print("❌ 'actions' must be a list")
        return 1
    
    all_errors = []
    action_names = set()
    
    for i, action in enumerate(actions):
        action_name = action.get('name', f'action_{i}')
        
        # Check for duplicate names
        if action_name in action_names:
            all_errors.append(f"Duplicate action name: {action_name}")
        action_names.add(action_name)
        
        # Validate action schema
        errors = validate_action_schema(action, action_name)
        all_errors.extend(errors)
    
    if all_errors:
        print("❌ Schema validation failed:")
        for error in all_errors:
            print(f"  • {error}")
        return 1
    
    print(f"✅ Stage 1: PASS - {len(actions)} actions validated")
    print(f"  Actions: {', '.join(sorted(action_names))}")
    return 0

if __name__ == "__main__":
    sys.exit(main()) 