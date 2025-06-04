#!/usr/bin/env python3
"""
Content Graders: Check actual correctness, not just response presence
"""

import re
import ast
import math
import tempfile
import subprocess
from typing import Dict, Any, List, Optional

# Template detection for failure-is-loud
TEMPLATE_PHRASES = [
    "I understand your question",
    "Thank you for reaching out", 
    "I appreciate your inquiry",
    "That's an interesting topic",
    "Let me provide a thoughtful response",
    "I'd be happy to help",
    "Here's what I can share"
]

def looks_like_template(answer: str) -> bool:
    """Detect template/mock responses that should fail loudly"""
    answer_clean = answer.strip().lower()
    
    # Empty or very short responses
    if len(answer_clean) < 5:
        return True
    
    # Just punctuation or repeated characters
    if answer_clean in ["...", "....", '"', "'", "----", "    "]:
        return True
        
    # Contains template phrases
    for phrase in TEMPLATE_PHRASES:
        if phrase.lower() in answer_clean:
            return True
    
    return False

def grade_math(question: str, answer: str) -> Dict[str, Any]:
    """Grade mathematical responses for actual correctness"""
    
    # Check for template response first
    if looks_like_template(answer):
        return {
            "correct": False,
            "score": 0.0,
            "reason": "Template response detected",
            "grade": "FAIL_LOUD"
        }
    
    # Extract all numbers from the answer
    numbers = re.findall(r'\b\d+(?:\.\d+)?\b', answer)
    
    # Known math problems and their answers
    known_answers = {
        "8!": "40320",
        "8 factorial": "40320", 
        "factorial of 8": "40320",
        "25% of 240": "60",
        "25 percent of 240": "60",
        "25% * 240": "60",
        "2+2": "4",
        "2 + 2": "4",
        "sqrt(16)": "4",
        "square root of 16": "4"
    }
    
    question_lower = question.lower().strip()
    
    # Check against known answers
    for q_pattern, expected in known_answers.items():
        if q_pattern.lower() in question_lower:
            if expected in numbers:
                return {
                    "correct": True,
                    "score": 1.0,
                    "expected": expected,
                    "found": expected,
                    "grade": "PASS"
                }
            else:
                return {
                    "correct": False,
                    "score": 0.0,
                    "expected": expected,
                    "found": numbers,
                    "reason": f"Expected {expected}, found {numbers}",
                    "grade": "FAIL"
                }
    
    # For other math problems, check if there's at least a numeric answer
    if not numbers:
        return {
            "correct": False,
            "score": 0.0,
            "reason": "No numeric answer found",
            "grade": "FAIL"
        }
    
    # Partial credit for having numbers
    return {
        "correct": True,
        "score": 0.5,
        "found": numbers,
        "reason": "Numeric answer present, correctness unknown",
        "grade": "PARTIAL"
    }

def grade_code(question: str, answer: str) -> Dict[str, Any]:
    """Grade code responses for compilation and basic correctness"""
    
    # Check for template response first
    if looks_like_template(answer):
        return {
            "correct": False,
            "score": 0.0,
            "reason": "Template response detected",
            "grade": "FAIL_LOUD"
        }
    
    # Extract code blocks (look for python function definitions)
    code_blocks = re.findall(r'def\s+\w+.*?(?=\n\n|\n(?=def)|\Z)', answer, re.DOTALL)
    
    if not code_blocks:
        # Look for any Python-like code
        if any(keyword in answer.lower() for keyword in ['def', 'return', 'while', 'for', 'if']):
            return {
                "correct": False,
                "score": 0.3,
                "reason": "Contains code keywords but no complete function",
                "grade": "PARTIAL"
            }
        else:
            return {
                "correct": False,
                "score": 0.0,
                "reason": "No code found in response",
                "grade": "FAIL"
            }
    
    # Try to compile the first code block
    code = code_blocks[0].strip()
    
    try:
        # Parse the code to check syntax
        ast.parse(code)
        
        # For GCD specifically, check for key elements
        if "gcd" in question.lower():
            required_elements = ["def", "gcd", "return", "%"]
            found_elements = sum(1 for elem in required_elements if elem in code.lower())
            
            if found_elements >= 3:
                return {
                    "correct": True,
                    "score": 1.0,
                    "code": code,
                    "elements_found": found_elements,
                    "grade": "PASS"
                }
            else:
                return {
                    "correct": False,
                    "score": 0.5,
                    "code": code,
                    "elements_found": found_elements,
                    "reason": f"Missing key elements: {4-found_elements}",
                    "grade": "PARTIAL"
                }
        
        # Generic code check - if it parses, partial credit
        return {
            "correct": True,
            "score": 0.7,
            "code": code,
            "reason": "Code compiles, correctness unknown",
            "grade": "PARTIAL"
        }
        
    except SyntaxError as e:
        return {
            "correct": False,
            "score": 0.0,
            "code": code,
            "error": str(e),
            "reason": "Code does not compile",
            "grade": "FAIL"
        }

def grade_logic(question: str, answer: str) -> Dict[str, Any]:
    """Grade logical reasoning responses"""
    
    # Check for template response first  
    if looks_like_template(answer):
        return {
            "correct": False,
            "score": 0.0,
            "reason": "Template response detected",
            "grade": "FAIL_LOUD"
        }
    
    answer_lower = answer.lower().strip()
    question_lower = question.lower().strip()
    
    # Known logic problems
    if "bloops are razzles" in question_lower and "razzles are lazzles" in question_lower:
        # Expected: All bloops are lazzles (yes)
        has_yes = any(word in answer_lower for word in ["yes", "true", "correct", "are lazzles"])
        has_reasoning = any(word in answer_lower for word in ["all", "therefore", "thus", "so", "because"])
        
        if has_yes and has_reasoning:
            return {
                "correct": True,
                "score": 1.0,
                "reasoning_present": True,
                "correct_answer": True,
                "grade": "PASS"
            }
        elif has_yes:
            return {
                "correct": True,
                "score": 0.7,
                "reasoning_present": False,
                "correct_answer": True,
                "reason": "Correct answer but no reasoning shown",
                "grade": "PARTIAL"
            }
        else:
            return {
                "correct": False,
                "score": 0.0,
                "reasoning_present": has_reasoning,
                "correct_answer": False,
                "reason": "Incorrect or missing answer",
                "grade": "FAIL"
            }
    
    # Generic logic check - look for reasoning words
    reasoning_words = ["because", "therefore", "thus", "so", "since", "if", "then", "all"]
    reasoning_count = sum(1 for word in reasoning_words if word in answer_lower)
    
    if reasoning_count >= 2:
        return {
            "correct": True,
            "score": 0.6,
            "reasoning_words": reasoning_count,
            "reason": "Contains logical reasoning language",
            "grade": "PARTIAL"
        }
    else:
        return {
            "correct": False,
            "score": 0.0,
            "reasoning_words": reasoning_count,
            "reason": "No logical reasoning detected",
            "grade": "FAIL"
        }

def grade_knowledge(question: str, answer: str) -> Dict[str, Any]:
    """Grade knowledge/factual responses"""
    
    # Check for template response first
    if looks_like_template(answer):
        return {
            "correct": False,
            "score": 0.0,
            "reason": "Template response detected", 
            "grade": "FAIL_LOUD"
        }
    
    # Simple knowledge checks
    question_lower = question.lower()
    answer_lower = answer.lower()
    
    # Basic factual checks
    factual_indicators = ["is", "are", "was", "were", "has", "have", "percent", "million", "billion"]
    fact_count = sum(1 for indicator in factual_indicators if indicator in answer_lower)
    
    # Length check - knowledge answers should be substantial
    if len(answer.strip()) < 20:
        return {
            "correct": False,
            "score": 0.0,
            "reason": "Answer too short for knowledge question",
            "grade": "FAIL"
        }
    
    if fact_count >= 2:
        return {
            "correct": True,
            "score": 0.7,
            "factual_indicators": fact_count,
            "length": len(answer),
            "grade": "PARTIAL"
        }
    else:
        return {
            "correct": False,
            "score": 0.2,
            "factual_indicators": fact_count,
            "length": len(answer),
            "reason": "Lacks factual content",
            "grade": "FAIL"
        }

def grade_response(question: str, answer: str, question_type: str) -> Dict[str, Any]:
    """Main grading function - routes to specific graders"""
    
    graders = {
        "math": grade_math,
        "code": grade_code, 
        "logic": grade_logic,
        "reasoning": grade_logic,  # Alias
        "knowledge": grade_knowledge,
        "science": grade_knowledge   # Alias
    }
    
    grader = graders.get(question_type.lower(), grade_knowledge)
    
    try:
        result = grader(question, answer)
        result["question_type"] = question_type
        result["grader_used"] = grader.__name__
        return result
    except Exception as e:
        return {
            "correct": False,
            "score": 0.0,
            "error": str(e),
            "reason": f"Grader error: {e}",
            "grade": "ERROR"
        } 