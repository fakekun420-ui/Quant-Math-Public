"""
Adapters for AQDE - Implementation of hexagonal architecture ports.

These adapters implement the AQDE interfaces by wrapping existing
quant-math components and external services.
"""

from .quant_math_adapter import QuantMathAdapter
from .risk_manager import RiskManagementEngine
from .knowledge_manager_stub import HypothesisKnowledgeBase

__all__ = [
    "QuantMathAdapter",
    "RiskManagementEngine",
    "HypothesisKnowledgeBase",
]