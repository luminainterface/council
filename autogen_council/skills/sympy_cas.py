#!/usr/bin/env python3
"""
🔬 SymPy CAS Skill Adapter
==========================

Computer Algebra System adapter for AutoGen that provides symbolic mathematics,
equation solving, calculus, and advanced mathematical operations.

Features:
- Symbolic computation and exact arithmetic
- Equation solving and system solving
- Calculus operations (derivatives, integrals, limits)
- Matrix operations and linear algebra
- Polynomial manipulation
- Series expansion and simplification
"""

import re
import asyncio
from typing import Dict, Any, Optional, List, Union, Tuple
from dataclasses import dataclass
from enum import Enum

try:
    import sympy as sp
    from sympy import (
        symbols, Symbol, Function, Expr,
        solve, solveset, Eq, simplify, expand, factor, collect,
        diff, integrate, limit, series, Sum, Product,
        Matrix, det, eigenvals, eigenvects,
        sin, cos, tan, exp, log, sqrt, pi, E, I, oo,
        latex, pretty, srepr
    )
    SYMPY_AVAILABLE = True
except ImportError:
    SYMPY_AVAILABLE = False
    print("[SYMPY_CAS] Error: SymPy not available - symbolic math disabled")

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

class CASOperation(Enum):
    """Types of Computer Algebra System operations"""
    SIMPLIFY = "simplify"
    EXPAND = "expand"
    FACTOR = "factor"
    SOLVE = "solve"
    DIFFERENTIATE = "differentiate"
    INTEGRATE = "integrate"
    LIMIT = "limit"
    SERIES = "series"
    MATRIX = "matrix"
    EQUATION = "equation"
    SUBSTITUTION = "substitution"
    UNKNOWN = "unknown"

@dataclass
class CASResult:
    """Result from Computer Algebra System operation"""
    result: str
    latex_form: Optional[str]
    operation_type: CASOperation
    input_expression: str
    steps: List[str]
    confidence: float
    execution_time_ms: float
    warnings: List[str]
    metadata: Dict[str, Any]

class SymPyCASAgent(Agent):
    """
    SymPy-powered Computer Algebra System agent for AutoGen
    """
    
    def __init__(self, agent_id: str = "sympy_cas"):
        super().__init__(agent_id)
        if not SYMPY_AVAILABLE:
            raise ImportError("SymPy is required for CAS operations")
        
        self.setup_cas_patterns()
        self.common_symbols = {}
        self._init_common_symbols()
        print(f"[SYMPY_CAS] Initialized with SymPy {sp.__version__}")
    
    def _init_common_symbols(self):
        """Initialize commonly used symbolic variables"""
        self.common_symbols = {
            'x': symbols('x'),
            'y': symbols('y'), 
            'z': symbols('z'),
            't': symbols('t'),
            'n': symbols('n'),
            'a': symbols('a'),
            'b': symbols('b'),
            'c': symbols('c'),
        }
    
    def setup_cas_patterns(self):
        """Setup regex patterns for CAS operation recognition"""
        self.patterns = {
            CASOperation.SIMPLIFY: [
                r'simplify',
                r'reduce',
                r'clean up',
                r'make simpler',
            ],
            CASOperation.EXPAND: [
                r'expand',
                r'multiply out',
                r'distribute',
            ],
            CASOperation.FACTOR: [
                r'factor',
                r'factorize',
                r'factor out',
            ],
            CASOperation.SOLVE: [
                r'solve',
                r'find.*=',
                r'equation.*for',
                r'what.*equal',
            ],
            CASOperation.DIFFERENTIATE: [
                r'derivative',
                r'differentiate',
                r'd/dx',
                r'∂/∂',
                r'gradient',
            ],
            CASOperation.INTEGRATE: [
                r'integrate',
                r'integral',
                r'∫',
                r'antiderivative',
            ],
            CASOperation.LIMIT: [
                r'limit',
                r'approaches',
                r'as.*→',
                r'as.*tends to',
            ],
            CASOperation.SERIES: [
                r'series',
                r'taylor',
                r'maclaurin',
                r'expansion',
            ],
            CASOperation.MATRIX: [
                r'matrix',
                r'determinant',
                r'eigenvalue',
                r'eigenvector',
                r'inverse',
            ],
        }
    
    def classify_operation(self, prompt: str) -> CASOperation:
        """Classify the type of CAS operation requested"""
        prompt_lower = prompt.lower()
        
        for operation, patterns in self.patterns.items():
            for pattern in patterns:
                if re.search(pattern, prompt_lower):
                    return operation
        
        return CASOperation.UNKNOWN
    
    async def process_cas_request(self, prompt: str) -> CASResult:
        """Main entry point for CAS operations"""
        import time
        start_time = time.time()
        
        operation_type = self.classify_operation(prompt)
        steps = []
        warnings = []
        
        try:
            if operation_type == CASOperation.SIMPLIFY:
                result = await self._simplify_expression(prompt, steps)
            elif operation_type == CASOperation.EXPAND:
                result = await self._expand_expression(prompt, steps)
            elif operation_type == CASOperation.FACTOR:
                result = await self._factor_expression(prompt, steps)
            elif operation_type == CASOperation.SOLVE:
                result = await self._solve_equation(prompt, steps)
            elif operation_type == CASOperation.DIFFERENTIATE:
                result = await self._differentiate(prompt, steps)
            elif operation_type == CASOperation.INTEGRATE:
                result = await self._integrate(prompt, steps)
            elif operation_type == CASOperation.LIMIT:
                result = await self._compute_limit(prompt, steps)
            elif operation_type == CASOperation.SERIES:
                result = await self._series_expansion(prompt, steps)
            elif operation_type == CASOperation.MATRIX:
                result = await self._matrix_operations(prompt, steps)
            else:
                result = await self._generic_cas_operation(prompt, steps)
                
        except Exception as e:
            warnings.append(f"CAS error: {str(e)}")
            result = {
                'expression': None,
                'latex': None,
                'input_expr': prompt,
                'confidence': 0.1
            }
        
        execution_time = (time.time() - start_time) * 1000
        
        return CASResult(
            result=str(result.get('expression', 'Error')),
            latex_form=result.get('latex'),
            operation_type=operation_type,
            input_expression=result.get('input_expr', prompt),
            steps=steps,
            confidence=result.get('confidence', 0.0),
            execution_time_ms=execution_time,
            warnings=warnings,
            metadata=result.get('metadata', {})
        )
    
    async def _simplify_expression(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Simplify mathematical expressions"""
        expr_str = self._extract_expression(prompt)
        if not expr_str:
            raise ValueError("Could not extract expression to simplify")
        
        steps.append(f"Parsing expression: {expr_str}")
        
        # Parse the expression
        expr = sp.sympify(expr_str, locals=self.common_symbols)
        steps.append(f"Parsed as: {expr}")
        
        # Simplify
        simplified = sp.simplify(expr)
        steps.append(f"Simplified: {simplified}")
        
        return {
            'expression': simplified,
            'latex': sp.latex(simplified),
            'input_expr': expr_str,
            'confidence': 0.95,
            'metadata': {
                'original': str(expr),
                'simplified': str(simplified),
                'reduction_achieved': len(str(expr)) > len(str(simplified))
            }
        }
    
    async def _expand_expression(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Expand mathematical expressions"""
        expr_str = self._extract_expression(prompt)
        if not expr_str:
            raise ValueError("Could not extract expression to expand")
        
        steps.append(f"Parsing expression: {expr_str}")
        
        expr = sp.sympify(expr_str, locals=self.common_symbols)
        steps.append(f"Parsed as: {expr}")
        
        # Expand
        expanded = sp.expand(expr)
        steps.append(f"Expanded: {expanded}")
        
        return {
            'expression': expanded,
            'latex': sp.latex(expanded),
            'input_expr': expr_str,
            'confidence': 0.95,
            'metadata': {
                'original': str(expr),
                'expanded': str(expanded)
            }
        }
    
    async def _factor_expression(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Factor mathematical expressions"""
        expr_str = self._extract_expression(prompt)
        if not expr_str:
            raise ValueError("Could not extract expression to factor")
        
        steps.append(f"Parsing expression: {expr_str}")
        
        expr = sp.sympify(expr_str, locals=self.common_symbols)
        steps.append(f"Parsed as: {expr}")
        
        # Factor
        factored = sp.factor(expr)
        steps.append(f"Factored: {factored}")
        
        return {
            'expression': factored,
            'latex': sp.latex(factored),
            'input_expr': expr_str,
            'confidence': 0.95,
            'metadata': {
                'original': str(expr),
                'factored': str(factored)
            }
        }
    
    async def _solve_equation(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Solve equations and systems of equations"""
        # Extract equation
        equation_match = re.search(r'([^=]+)=([^=]+)', prompt)
        if not equation_match:
            raise ValueError("Could not identify equation to solve")
        
        left_side = equation_match.group(1).strip()
        right_side = equation_match.group(2).strip()
        
        steps.append(f"Equation: {left_side} = {right_side}")
        
        # Parse both sides
        left_expr = sp.sympify(left_side, locals=self.common_symbols)
        right_expr = sp.sympify(right_side, locals=self.common_symbols)
        
        # Create equation
        equation = sp.Eq(left_expr, right_expr)
        steps.append(f"Symbolic equation: {equation}")
        
        # Determine variables to solve for
        variables = list(equation.free_symbols)
        if not variables:
            raise ValueError("No variables found in equation")
        
        # If multiple variables, try to determine which one to solve for
        solve_var = self._determine_solve_variable(prompt, variables)
        steps.append(f"Solving for: {solve_var}")
        
        # Solve
        solutions = sp.solve(equation, solve_var)
        steps.append(f"Solutions: {solutions}")
        
        return {
            'expression': solutions,
            'latex': sp.latex(solutions),
            'input_expr': f"{left_side} = {right_side}",
            'confidence': 0.9,
            'metadata': {
                'equation': str(equation),
                'variable': str(solve_var),
                'num_solutions': len(solutions) if isinstance(solutions, list) else 1
            }
        }
    
    async def _differentiate(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Compute derivatives"""
        expr_str = self._extract_expression(prompt)
        if not expr_str:
            raise ValueError("Could not extract function to differentiate")
        
        steps.append(f"Function: {expr_str}")
        
        # Parse expression
        expr = sp.sympify(expr_str, locals=self.common_symbols)
        
        # Determine variable of differentiation
        diff_var = self._determine_diff_variable(prompt, expr.free_symbols)
        steps.append(f"Differentiating with respect to: {diff_var}")
        
        # Compute derivative
        derivative = sp.diff(expr, diff_var)
        steps.append(f"Derivative: {derivative}")
        
        return {
            'expression': derivative,
            'latex': sp.latex(derivative),
            'input_expr': expr_str,
            'confidence': 0.95,
            'metadata': {
                'original_function': str(expr),
                'variable': str(diff_var),
                'derivative': str(derivative)
            }
        }
    
    async def _integrate(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Compute integrals"""
        expr_str = self._extract_expression(prompt)
        if not expr_str:
            raise ValueError("Could not extract function to integrate")
        
        steps.append(f"Function: {expr_str}")
        
        # Parse expression
        expr = sp.sympify(expr_str, locals=self.common_symbols)
        
        # Determine variable of integration
        int_var = self._determine_diff_variable(prompt, expr.free_symbols)
        steps.append(f"Integrating with respect to: {int_var}")
        
        # Check for limits of integration
        limits = self._extract_integration_limits(prompt)
        
        if limits:
            # Definite integral
            lower, upper = limits
            steps.append(f"Definite integral from {lower} to {upper}")
            integral = sp.integrate(expr, (int_var, lower, upper))
        else:
            # Indefinite integral
            steps.append("Indefinite integral")
            integral = sp.integrate(expr, int_var)
        
        steps.append(f"Result: {integral}")
        
        return {
            'expression': integral,
            'latex': sp.latex(integral),
            'input_expr': expr_str,
            'confidence': 0.9,
            'metadata': {
                'original_function': str(expr),
                'variable': str(int_var),
                'limits': limits,
                'integral': str(integral)
            }
        }
    
    async def _compute_limit(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Compute limits"""
        expr_str = self._extract_expression(prompt)
        if not expr_str:
            raise ValueError("Could not extract expression for limit")
        
        steps.append(f"Expression: {expr_str}")
        
        # Parse expression
        expr = sp.sympify(expr_str, locals=self.common_symbols)
        
        # Extract limit variable and point
        limit_info = self._extract_limit_info(prompt)
        if not limit_info:
            raise ValueError("Could not determine limit variable and point")
        
        var, point = limit_info
        steps.append(f"Computing limit as {var} approaches {point}")
        
        # Compute limit
        limit_result = sp.limit(expr, var, point)
        steps.append(f"Limit: {limit_result}")
        
        return {
            'expression': limit_result,
            'latex': sp.latex(limit_result),
            'input_expr': expr_str,
            'confidence': 0.9,
            'metadata': {
                'expression': str(expr),
                'variable': str(var),
                'point': str(point),
                'limit': str(limit_result)
            }
        }
    
    async def _series_expansion(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Compute series expansions"""
        expr_str = self._extract_expression(prompt)
        if not expr_str:
            raise ValueError("Could not extract expression for series expansion")
        
        steps.append(f"Expression: {expr_str}")
        
        # Parse expression
        expr = sp.sympify(expr_str, locals=self.common_symbols)
        
        # Determine expansion variable and point
        var = list(expr.free_symbols)[0] if expr.free_symbols else symbols('x')
        point = 0  # Default expansion point
        order = 6  # Default order
        
        # Try to extract expansion point and order from prompt
        point_match = re.search(r'around\s+(\d+)', prompt.lower())
        if point_match:
            point = int(point_match.group(1))
        
        order_match = re.search(r'order\s+(\d+)', prompt.lower())
        if order_match:
            order = int(order_match.group(1))
        
        steps.append(f"Expanding around {var} = {point} to order {order}")
        
        # Compute series expansion
        series_expansion = sp.series(expr, var, point, order).removeO()
        steps.append(f"Series: {series_expansion}")
        
        return {
            'expression': series_expansion,
            'latex': sp.latex(series_expansion),
            'input_expr': expr_str,
            'confidence': 0.9,
            'metadata': {
                'original': str(expr),
                'variable': str(var),
                'point': point,
                'order': order,
                'series': str(series_expansion)
            }
        }
    
    async def _matrix_operations(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Perform matrix operations"""
        # This is a simplified implementation
        # In practice, you'd want more sophisticated matrix parsing
        steps.append("Matrix operations not fully implemented")
        
        return {
            'expression': "Matrix operations coming soon",
            'latex': None,
            'input_expr': prompt,
            'confidence': 0.1,
            'metadata': {}
        }
    
    async def _generic_cas_operation(self, prompt: str, steps: List[str]) -> Dict[str, Any]:
        """Handle generic CAS operations"""
        expr_str = self._extract_expression(prompt)
        if not expr_str:
            raise ValueError("Could not extract mathematical expression")
        
        steps.append(f"Generic processing: {expr_str}")
        
        # Parse and return simplified form
        expr = sp.sympify(expr_str, locals=self.common_symbols)
        simplified = sp.simplify(expr)
        
        return {
            'expression': simplified,
            'latex': sp.latex(simplified),
            'input_expr': expr_str,
            'confidence': 0.7,
            'metadata': {
                'original': str(expr),
                'processed': str(simplified)
            }
        }
    
    def _extract_expression(self, prompt: str) -> Optional[str]:
        """Extract mathematical expression from prompt"""
        # Look for mathematical expressions in various formats
        patterns = [
            r'(?:expression|function|equation)[:=]?\s*([^,\n]+)',
            r'(?:f\(x\)|y)\s*=\s*([^,\n]+)',
            r'(\w+\^?\w*\s*[\+\-\*/\^]+[^,\n]+)',
            r'([a-zA-Z_]\w*\([^)]+\))',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, prompt, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # If no pattern matches, try to find any mathematical expression
        # This is a fallback that looks for common mathematical symbols
        math_chars = re.search(r'([a-zA-Z0-9\+\-\*/\^().\s]+)', prompt)
        if math_chars and any(c in math_chars.group(1) for c in ['+', '-', '*', '/', '^', '(']):
            return math_chars.group(1).strip()
        
        return None
    
    def _determine_solve_variable(self, prompt: str, variables: List[Symbol]) -> Symbol:
        """Determine which variable to solve for"""
        prompt_lower = prompt.lower()
        
        # Look for explicit variable mentions
        for var in variables:
            if f"for {str(var)}" in prompt_lower or f"solve {str(var)}" in prompt_lower:
                return var
        
        # Default to first variable or 'x' if available
        if symbols('x') in variables:
            return symbols('x')
        return variables[0]
    
    def _determine_diff_variable(self, prompt: str, variables: set) -> Symbol:
        """Determine variable for differentiation/integration"""
        prompt_lower = prompt.lower()
        
        # Look for explicit variable mentions
        for pattern in [r'd/d(\w+)', r'with respect to (\w+)', r'∂/∂(\w+)']:
            match = re.search(pattern, prompt_lower)
            if match:
                var_name = match.group(1)
                return symbols(var_name)
        
        # Default to 'x' if available, otherwise first variable
        if symbols('x') in variables:
            return symbols('x')
        elif variables:
            return list(variables)[0]
        else:
            return symbols('x')
    
    def _extract_integration_limits(self, prompt: str) -> Optional[Tuple[Any, Any]]:
        """Extract integration limits from prompt"""
        # Look for patterns like "from a to b" or "between a and b"
        limit_patterns = [
            r'from\s+(\S+)\s+to\s+(\S+)',
            r'between\s+(\S+)\s+and\s+(\S+)',
            r'\[(\S+),\s*(\S+)\]',
        ]
        
        for pattern in limit_patterns:
            match = re.search(pattern, prompt.lower())
            if match:
                try:
                    lower = sp.sympify(match.group(1))
                    upper = sp.sympify(match.group(2))
                    return (lower, upper)
                except:
                    continue
        
        return None
    
    def _extract_limit_info(self, prompt: str) -> Optional[Tuple[Symbol, Any]]:
        """Extract limit variable and point"""
        # Look for patterns like "as x approaches 0" or "x → ∞"
        limit_patterns = [
            r'as\s+(\w+)\s+approaches\s+(\S+)',
            r'(\w+)\s*→\s*(\S+)',
            r'(\w+)\s+tends to\s+(\S+)',
        ]
        
        for pattern in limit_patterns:
            match = re.search(pattern, prompt.lower())
            if match:
                var_name = match.group(1)
                point_str = match.group(2)
                
                var = symbols(var_name)
                
                # Parse the point
                if point_str in ['infinity', '∞', 'inf']:
                    point = sp.oo
                elif point_str in ['-infinity', '-∞', '-inf']:
                    point = -sp.oo
                else:
                    try:
                        point = sp.sympify(point_str)
                    except:
                        point = 0
                
                return (var, point)
        
        return None

# Factory function
def create_sympy_cas_agent() -> SymPyCASAgent:
    """Factory function to create a SymPy CAS agent"""
    return SymPyCASAgent()

# Convenience function for direct usage
async def solve_symbolic(prompt: str) -> Dict[str, Any]:
    """
    Direct interface for symbolic mathematics
    
    Args:
        prompt: Mathematical problem or expression
        
    Returns:
        Dictionary with symbolic solution details
    """
    if not SYMPY_AVAILABLE:
        return {
            "error": "SymPy not available",
            "result": None,
            "confidence": 0.0
        }
    
    agent = create_sympy_cas_agent()
    result = await agent.process_cas_request(prompt)
    
    return {
        "result": result.result,
        "latex": result.latex_form,
        "operation": result.operation_type.value,
        "steps": result.steps,
        "confidence": result.confidence,
        "execution_time_ms": result.execution_time_ms,
        "warnings": result.warnings,
        "metadata": result.metadata
    } 