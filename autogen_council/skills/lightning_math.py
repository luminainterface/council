#!/usr/bin/env python3
"""
⚡ Lightning Math Skill Adapter
===============================

High-performance mathematical problem solver that integrates with AutoGen's Agent framework.
Uses symbolic computation for exact results and optimized numerical methods for speed.

Features:
- Symbolic math via SymPy integration
- Exact arithmetic for fractions, roots, etc.
- Fast numerical computation
- Integration with AutoGen message passing
"""

import re
import math
import asyncio
from typing import Dict, Any, Optional, Union, List
from dataclasses import dataclass
from enum import Enum

try:
    import sympy as sp
    from sympy import symbols, solve, simplify, expand, factor, diff, integrate
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False
    print("[LIGHTNING_MATH] Warning: SymPy not available, falling back to basic math")

# AutoGen imports with fallback
try:
    from autogen_core import Agent, MessageContext
    AUTOGEN_AVAILABLE = True
except ImportError:
    # Fallback for standalone testing
    AUTOGEN_AVAILABLE = False
    
    class Agent:
        """Fallback Agent class for standalone testing"""
        def __init__(self, agent_id: str):
            self.agent_id = agent_id
    
    class MessageContext:
        """Fallback MessageContext for standalone testing"""
        pass

class MathProblemType(Enum):
    """Categories of mathematical problems"""
    ARITHMETIC = "arithmetic"
    ALGEBRA = "algebra"
    CALCULUS = "calculus"
    GEOMETRY = "geometry"
    STATISTICS = "statistics"
    NUMBER_THEORY = "number_theory"
    UNKNOWN = "unknown"

@dataclass
class MathSolution:
    """Mathematical solution with metadata"""
    answer: str
    steps: List[str]
    problem_type: MathProblemType
    confidence: float
    execution_time_ms: float
    exact_answer: bool
    symbolic_form: Optional[str] = None

class LightningMathAgent(Agent):
    """
    Lightning-fast mathematical problem solver integrated with AutoGen
    """
    
    def __init__(self, agent_id: str = "lightning_math"):
        super().__init__(agent_id)
        self.setup_math_patterns()
        print(f"[LIGHTNING_MATH] Initialized with SymPy: {SYMPY_AVAILABLE}, AutoGen: {AUTOGEN_AVAILABLE}")
    
    def setup_math_patterns(self):
        """Setup regex patterns for math problem recognition"""
        self.patterns = {
            MathProblemType.ARITHMETIC: [
                r'\d+\s*[\+\-\*\/]\s*\d+',  # Basic operations
                r'calculate:?\s*',
                r'what is \d+',
                r'find the (sum|product|difference|quotient)',
                r'square root',  # Add square root support
                r'sqrt',  # Add sqrt abbreviation
                r'root of \d+',  # "root of 64"
            ],
            MathProblemType.ALGEBRA: [
                r'solve.*[xy]\s*[=<>]',
                r'find.*[xy]',
                r'[xy]\s*[\+\-\*\/]\s*\d+\s*=',
                r'equation',
                r'roots? of',
            ],
            MathProblemType.CALCULUS: [
                r'derivative',
                r'integral?',
                r'limit',
                r'd/dx',
                r'∫',
                r'∂',
            ],
            MathProblemType.GEOMETRY: [
                r'area.*triangle|circle|square|rectangle',
                r'volume.*cube|sphere|cylinder',
                r'perimeter',
                r'circumference',
                r'surface area',
                r'diagonal',
                r'rectangle.*\d+\s*[x×]\s*\d+',  # Added pattern for "rectangle 8x12"
                r'area.*circle',  # Specific circle area pattern
                r'circle.*area',  # Alternative circle area pattern
            ],
            MathProblemType.STATISTICS: [
                r'mean|average',
                r'standard deviation',
                r'variance',
                r'probability',
                r'median|mode',
            ],
            MathProblemType.NUMBER_THEORY: [
                r'prime',
                r'lcm|gcd',
                r'factorial',
                r'fibonacci',
                r'binary|hexadecimal',
                r'\d+\s*!',  # Added pattern for factorial notation
                r'\d+\s+factorial',  # Added pattern for "5 factorial"
                r'factorial.*function',  # Added pattern for "factorial function"
                r'implement.*factorial',  # Added pattern for "implement factorial"
            ]
        }
    
    def classify_problem(self, prompt: str) -> MathProblemType:
        """Classify the type of mathematical problem"""
        prompt_lower = prompt.lower()
        
        # Check for specific patterns that might conflict first
        # Square root needs to be checked before geometry (which contains "square")
        if re.search(r'square root', prompt_lower) or re.search(r'sqrt', prompt_lower):
            return MathProblemType.ARITHMETIC
        
        # ⚡ FIX: Check for rectangle perimeter specifically before other patterns
        if 'rectangle' in prompt_lower and re.search(r'\d+\s*[x×]\s*\d+', prompt_lower):
            return MathProblemType.GEOMETRY
        
        # Check more specific patterns first to avoid false matches
        specific_order = [
            MathProblemType.NUMBER_THEORY,
            MathProblemType.CALCULUS,
            MathProblemType.ALGEBRA,
            MathProblemType.STATISTICS,
            MathProblemType.ARITHMETIC,  # Check arithmetic before geometry
            MathProblemType.GEOMETRY,   # Move geometry after arithmetic
        ]
        
        for problem_type in specific_order:
            patterns = self.patterns[problem_type]
            for pattern in patterns:
                if re.search(pattern, prompt_lower):
                    return problem_type
        
        return MathProblemType.UNKNOWN
    
    async def solve_math_problem(self, prompt: str) -> MathSolution:
        """Main mathematical problem solver"""
        import time
        start_time = time.time()
        
        problem_type = self.classify_problem(prompt)
        
        try:
            if problem_type == MathProblemType.ARITHMETIC:
                solution = await self._solve_arithmetic(prompt)
            elif problem_type == MathProblemType.ALGEBRA:
                solution = await self._solve_algebra(prompt)
            elif problem_type == MathProblemType.CALCULUS:
                solution = await self._solve_calculus(prompt)
            elif problem_type == MathProblemType.GEOMETRY:
                solution = await self._solve_geometry(prompt)
            elif problem_type == MathProblemType.STATISTICS:
                solution = await self._solve_statistics(prompt)
            elif problem_type == MathProblemType.NUMBER_THEORY:
                solution = await self._solve_number_theory(prompt)
            else:
                solution = await self._solve_generic(prompt)
                
        except Exception as e:
            # Fallback to basic computation
            solution = MathSolution(
                answer=f"Error in computation: {str(e)}",
                steps=["Error occurred during calculation"],
                problem_type=problem_type,
                confidence=0.1,
                execution_time_ms=(time.time() - start_time) * 1000,
                exact_answer=False
            )
        
        solution.execution_time_ms = (time.time() - start_time) * 1000
        return solution
    
    async def _solve_arithmetic(self, prompt: str) -> MathSolution:
        """Solve basic arithmetic problems"""
        steps = []
        
        # ⚡ FIX: Handle percentage calculations - "X% of Y"
        percent_match = re.search(r'(\d+)\s*%\s*of\s*(\d+)', prompt.lower())
        if percent_match:
            percent = int(percent_match.group(1))
            number = int(percent_match.group(2))
            result = (percent * number) / 100
            steps.append(f"Computing {percent}% of {number}")
            steps.append(f"{percent}% × {number} = {percent} × {number} ÷ 100 = {result}")
            
            return MathSolution(
                answer=str(int(result)) if result.is_integer() else str(result),
                steps=steps,
                problem_type=MathProblemType.ARITHMETIC,
                confidence=0.95,
                execution_time_ms=0,
                exact_answer=result.is_integer()
            )
        
        # Handle square root specifically
        sqrt_match = re.search(r'square root of (\d+)', prompt.lower())
        if sqrt_match:
            number = int(sqrt_match.group(1))
            result = math.sqrt(number)
            steps.append(f"Computing square root of {number}")
            steps.append(f"√{number} = {result}")
            
            return MathSolution(
                answer=str(int(result)) if result.is_integer() else str(result),
                steps=steps,
                problem_type=MathProblemType.ARITHMETIC,
                confidence=0.95,
                execution_time_ms=0,
                exact_answer=result.is_integer()
            )
        
        # Handle sqrt() function notation
        sqrt_func_match = re.search(r'sqrt\((\d+)\)', prompt.lower())
        if sqrt_func_match:
            number = int(sqrt_func_match.group(1))
            result = math.sqrt(number)
            steps.append(f"Computing sqrt({number})")
            steps.append(f"sqrt({number}) = {result}")
            
            return MathSolution(
                answer=str(int(result)) if result.is_integer() else str(result),
                steps=steps,
                problem_type=MathProblemType.ARITHMETIC,
                confidence=0.95,
                execution_time_ms=0,
                exact_answer=result.is_integer()
            )
        
        # Extract numbers and operations for regular arithmetic
        expression = self._extract_expression(prompt)
        if not expression:
            return self._create_error_solution("Could not parse arithmetic expression")
        
        steps.append(f"Extracted expression: {expression}")
        
        try:
            # Use eval safely for basic arithmetic
            if self._is_safe_expression(expression):
                result = eval(expression)
                steps.append(f"Computed: {expression} = {result}")
                
                return MathSolution(
                    answer=str(result),
                    steps=steps,
                    problem_type=MathProblemType.ARITHMETIC,
                    confidence=0.95,
                    execution_time_ms=0,  # Will be set by caller
                    exact_answer=True
                )
            else:
                return self._create_error_solution("Unsafe expression")
                
        except Exception as e:
            return self._create_error_solution(f"Arithmetic error: {str(e)}")
    
    async def _solve_algebra(self, prompt: str) -> MathSolution:
        """Solve algebraic equations"""
        if not SYMPY_AVAILABLE:
            return self._create_error_solution("SymPy required for algebraic solutions")
        
        steps = []
        
        try:
            # Extract equation
            equation_match = re.search(r'([xy]\s*[\+\-\*\/]?\s*\d*)\s*=\s*(\d+)', prompt.lower())
            if equation_match:
                left_side = equation_match.group(1).replace(' ', '')
                right_side = int(equation_match.group(2))
                
                steps.append(f"Identified equation: {left_side} = {right_side}")
                
                # Create symbolic variable
                x = symbols('x')
                y = symbols('y')
                
                # Parse and solve
                equation = sp.Eq(sp.sympify(left_side), right_side)
                solutions = solve(equation)
                
                steps.append(f"Solving: {equation}")
                steps.append(f"Solutions: {solutions}")
                
                return MathSolution(
                    answer=f"x = {solutions}" if solutions else "No solution found",
                    steps=steps,
                    problem_type=MathProblemType.ALGEBRA,
                    confidence=0.9,
                    execution_time_ms=0,
                    exact_answer=True,
                    symbolic_form=str(equation)
                )
            else:
                return self._create_error_solution("Could not parse algebraic equation")
                
        except Exception as e:
            return self._create_error_solution(f"Algebra error: {str(e)}")
    
    async def _solve_calculus(self, prompt: str) -> MathSolution:
        """Solve calculus problems"""
        if not SYMPY_AVAILABLE:
            return self._create_error_solution("SymPy required for calculus")
        
        steps = []
        try:
            x = symbols('x')
            
            # Check for derivative
            if 'derivative' in prompt.lower() or 'd/dx' in prompt:
                # Extract function (simplified)
                func_match = re.search(r'of\s+([^,\s]+)', prompt)
                if func_match:
                    func_str = func_match.group(1)
                    func = sp.sympify(func_str)
                    derivative = diff(func, x)
                    
                    steps.append(f"Function: f(x) = {func}")
                    steps.append(f"Derivative: f'(x) = {derivative}")
                    
                    return MathSolution(
                        answer=str(derivative),
                        steps=steps,
                        problem_type=MathProblemType.CALCULUS,
                        confidence=0.85,
                        execution_time_ms=0,
                        exact_answer=True,
                        symbolic_form=str(func)
                    )
            
            # Check for integral
            elif 'integral' in prompt.lower() or '∫' in prompt:
                func_match = re.search(r'of\s+([^,\s]+)', prompt)
                if func_match:
                    func_str = func_match.group(1)
                    func = sp.sympify(func_str)
                    integral = integrate(func, x)
                    
                    steps.append(f"Function: f(x) = {func}")
                    steps.append(f"Integral: ∫f(x)dx = {integral}")
                    
                    return MathSolution(
                        answer=str(integral),
                        steps=steps,
                        problem_type=MathProblemType.CALCULUS,
                        confidence=0.85,
                        execution_time_ms=0,
                        exact_answer=True,
                        symbolic_form=str(func)
                    )
            
            return self._create_error_solution("Could not parse calculus problem")
            
        except Exception as e:
            return self._create_error_solution(f"Calculus error: {str(e)}")
    
    async def _solve_geometry(self, prompt: str) -> MathSolution:
        """Solve geometry problems"""
        steps = []
        
        try:
            prompt_lower = prompt.lower()
            
            # Pattern: "rectangle 8x12" or "perimeter rectangle 8x12"
            if 'perimeter' in prompt_lower and 'rectangle' in prompt_lower:
                rect_match = re.search(r'(\d+)\s*[x×]\s*(\d+)', prompt_lower)
                if rect_match:
                    width = int(rect_match.group(1))
                    height = int(rect_match.group(2))
                    perimeter = 2 * (width + height)
                    
                    steps.append(f"Rectangle perimeter formula: P = 2 × (width + height)")
                    steps.append(f"Given: width = {width}, height = {height}")
                    steps.append(f"Perimeter = 2 × ({width} + {height}) = 2 × {width + height} = {perimeter}")
                    
                    return MathSolution(
                        answer=str(perimeter),
                        steps=steps,
                        problem_type=MathProblemType.GEOMETRY,
                        confidence=0.95,
                        execution_time_ms=0,
                        exact_answer=True
                    )
            
            # ⚡ FIX: Handle implicit rectangle perimeter (without "perimeter" keyword)
            elif 'rectangle' in prompt_lower and re.search(r'(\d+)\s*[x×]\s*(\d+)', prompt_lower):
                rect_match = re.search(r'(\d+)\s*[x×]\s*(\d+)', prompt_lower)
                width = int(rect_match.group(1))
                height = int(rect_match.group(2))
                perimeter = 2 * (width + height)
                
                steps.append(f"Rectangle perimeter formula: P = 2 × (width + height)")
                steps.append(f"Given: width = {width}, height = {height}")
                steps.append(f"Perimeter = 2 × ({width} + {height}) = 2 × {width + height} = {perimeter}")
                
                return MathSolution(
                    answer=str(perimeter),
                    steps=steps,
                    problem_type=MathProblemType.GEOMETRY,
                    confidence=0.95,
                    execution_time_ms=0,
                    exact_answer=True
                )
            
            # Area of triangle
            elif 'area' in prompt_lower and 'triangle' in prompt_lower:
                base_match = re.search(r'base\s+(\d+(?:\.\d+)?)', prompt_lower)
                height_match = re.search(r'height\s+(\d+(?:\.\d+)?)', prompt_lower)
                
                if base_match and height_match:
                    base = float(base_match.group(1))
                    height = float(height_match.group(1))
                    area = 0.5 * base * height
                    
                    steps.append(f"Triangle area formula: A = (1/2) × base × height")
                    steps.append(f"Given: base = {base}, height = {height}")
                    steps.append(f"Area = (1/2) × {base} × {height} = {area}")
                    
                    return MathSolution(
                        answer=str(area),
                        steps=steps,
                        problem_type=MathProblemType.GEOMETRY,
                        confidence=0.95,
                        execution_time_ms=0,
                        exact_answer=True
                    )
            
            # Circle circumference
            elif 'circumference' in prompt_lower and 'circle' in prompt_lower:
                diameter_match = re.search(r'diameter\s+(\d+(?:\.\d+)?)', prompt_lower)
                radius_match = re.search(r'radius\s+(\d+(?:\.\d+)?)', prompt_lower)
                
                if diameter_match:
                    diameter = float(diameter_match.group(1))
                    circumference = math.pi * diameter
                    steps.append(f"Circumference formula: C = π × diameter")
                    steps.append(f"C = π × {diameter} = {circumference:.4f}")
                elif radius_match:
                    radius = float(radius_match.group(1))
                    circumference = 2 * math.pi * radius
                    steps.append(f"Circumference formula: C = 2π × radius")
                    steps.append(f"C = 2π × {radius} = {circumference:.4f}")
                else:
                    return self._create_error_solution("Missing diameter or radius")
                
                return MathSolution(
                    answer=f"{circumference:.4f}",
                    steps=steps,
                    problem_type=MathProblemType.GEOMETRY,
                    confidence=0.95,
                    execution_time_ms=0,
                    exact_answer=False  # Due to π approximation
                )
            
            # ⚡ FIX: Circle area calculation
            elif 'area' in prompt_lower and 'circle' in prompt_lower:
                radius_match = re.search(r'radius\s+(\d+(?:\.\d+)?)', prompt_lower)
                diameter_match = re.search(r'diameter\s+(\d+(?:\.\d+)?)', prompt_lower)
                
                if radius_match:
                    radius = float(radius_match.group(1))
                    area = math.pi * radius * radius
                    steps.append(f"Circle area formula: A = π × r²")
                    steps.append(f"Given: radius = {radius}")
                    steps.append(f"Area = π × {radius}² = π × {radius * radius} = {area:.4f}")
                elif diameter_match:
                    diameter = float(diameter_match.group(1))
                    radius = diameter / 2
                    area = math.pi * radius * radius
                    steps.append(f"Circle area formula: A = π × r²")
                    steps.append(f"Given: diameter = {diameter}, so radius = {radius}")
                    steps.append(f"Area = π × {radius}² = {area:.4f}")
                else:
                    return self._create_error_solution("Missing radius or diameter for circle area")
                
                return MathSolution(
                    answer=f"{area:.4f}",
                    steps=steps,
                    problem_type=MathProblemType.GEOMETRY,
                    confidence=0.95,
                    execution_time_ms=0,
                    exact_answer=False  # Due to π approximation
                )
            
            return self._create_error_solution("Unsupported geometry problem")
            
        except Exception as e:
            return self._create_error_solution(f"Geometry error: {str(e)}")
    
    async def _solve_statistics(self, prompt: str) -> MathSolution:
        """Solve statistics problems"""
        # Placeholder - would implement statistical calculations
        return self._create_error_solution("Statistics solver not yet implemented")
    
    async def _solve_number_theory(self, prompt: str) -> MathSolution:
        """Solve number theory problems"""
        steps = []
        
        try:
            prompt_lower = prompt.lower()
            
            # Factorial
            if 'factorial' in prompt_lower or '!' in prompt:
                num_match = re.search(r'(\d+)!', prompt)
                if not num_match:
                    # Try pattern where number comes after factorial
                    num_match = re.search(r'factorial.*?(\d+)', prompt_lower)
                if not num_match:
                    # Try pattern where number comes before factorial
                    num_match = re.search(r'(\d+)\s+factorial', prompt_lower)
                
                if num_match:
                    n = int(num_match.group(1))
                    if n > 20:  # Prevent huge calculations
                        return self._create_error_solution("Factorial too large")
                    
                    result = math.factorial(n)
                    steps.append(f"Computing {n}!")
                    steps.append(f"{n}! = {result}")
                    
                    return MathSolution(
                        answer=str(result),
                        steps=steps,
                        problem_type=MathProblemType.NUMBER_THEORY,
                        confidence=0.95,
                        execution_time_ms=0,
                        exact_answer=True
                    )
            
            # GCD/LCM
            elif 'gcd' in prompt_lower or 'lcm' in prompt_lower:
                numbers = re.findall(r'\d+', prompt)
                if len(numbers) >= 2:
                    a, b = int(numbers[0]), int(numbers[1])
                    
                    if 'gcd' in prompt_lower:
                        result = math.gcd(a, b)
                        steps.append(f"Computing GCD of {a} and {b}")
                        steps.append(f"GCD({a}, {b}) = {result}")
                    else:  # LCM
                        result = abs(a * b) // math.gcd(a, b)
                        steps.append(f"Computing LCM of {a} and {b}")
                        steps.append(f"LCM({a}, {b}) = |{a} × {b}| / GCD({a}, {b}) = {result}")
                    
                    return MathSolution(
                        answer=str(result),
                        steps=steps,
                        problem_type=MathProblemType.NUMBER_THEORY,
                        confidence=0.95,
                        execution_time_ms=0,
                        exact_answer=True
                    )
            
            return self._create_error_solution("Unsupported number theory problem")
            
        except Exception as e:
            return self._create_error_solution(f"Number theory error: {str(e)}")
    
    async def _solve_generic(self, prompt: str) -> MathSolution:
        """Generic mathematical problem solver"""
        # Try to extract any mathematical expression
        expression = self._extract_expression(prompt)
        if expression and self._is_safe_expression(expression):
            try:
                result = eval(expression)
                return MathSolution(
                    answer=str(result),
                    steps=[f"Evaluated: {expression} = {result}"],
                    problem_type=MathProblemType.UNKNOWN,
                    confidence=0.7,
                    execution_time_ms=0,
                    exact_answer=True
                )
            except:
                pass
        
        return self._create_error_solution("Unable to solve mathematical problem")
    
    def _extract_expression(self, prompt: str) -> Optional[str]:
        """Extract mathematical expression from prompt"""
        # Look for common mathematical expressions
        patterns = [
            r'(\d+(?:\.\d+)?\s*[\+\-\*\/]\s*\d+(?:\.\d+)?)',
            r'(\d+\s*\^\s*\d+)',
            r'sqrt\((\d+)\)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, prompt)
            if match:
                expr = match.group(1) if match.groups() else match.group(0)
                # Clean up expression
                expr = expr.replace('^', '**')  # Convert to Python exponentiation
                return expr
        
        return None
    
    def _is_safe_expression(self, expression: str) -> bool:
        """Check if expression is safe to evaluate"""
        dangerous_patterns = [
            'import', '__', 'exec', 'eval', 'open', 'file',
            'os', 'sys', 'subprocess', 'compile'
        ]
        
        for pattern in dangerous_patterns:
            if pattern in expression.lower():
                return False
        
        # Only allow numbers, basic operators, and parentheses
        allowed_chars = set('0123456789+-*/.() ')
        return all(c in allowed_chars for c in expression)
    
    def _create_error_solution(self, error_msg: str) -> MathSolution:
        """Create error solution"""
        return MathSolution(
            answer=error_msg,
            steps=[error_msg],
            problem_type=MathProblemType.UNKNOWN,
            confidence=0.0,
            execution_time_ms=0,
            exact_answer=False
        )

# Factory function for creating the agent
def create_lightning_math_agent() -> LightningMathAgent:
    """Factory function to create a LightningMathAgent"""
    return LightningMathAgent()

# Convenience function for direct usage
async def solve_math(prompt: str) -> Dict[str, Any]:
    """
    Direct interface for mathematical problem solving
    
    Args:
        prompt: Mathematical problem description
        
    Returns:
        Dictionary with solution details
    """
    agent = create_lightning_math_agent()
    solution = await agent.solve_math_problem(prompt)
    
    return {
        "answer": solution.answer,
        "steps": solution.steps,
        "problem_type": solution.problem_type.value,
        "confidence": solution.confidence,
        "execution_time_ms": solution.execution_time_ms,
        "exact_answer": solution.exact_answer,
        "symbolic_form": solution.symbolic_form
    } 