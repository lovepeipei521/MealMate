# app/config/evaluation_config.py
"""
Configuration for RAG evaluation using RAGAS framework.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class AlertThresholds:
    """Thresholds for quality alerts. Evaluations below these values trigger alerts."""
    faithfulness: float = 0.3
    answer_relevancy: float = 0.5


@dataclass
class EvaluationConfig:
    """
    Configuration for RAG evaluation.

    Attributes:
        enabled: Whether evaluation is enabled
        async_mode: Whether to run evaluation asynchronously (recommended)
        sample_rate: Fraction of requests to evaluate (0.0-1.0)
        metrics: List of metrics to compute
        llm_type: LLM tier to use for evaluation (fast recommended for cost)
        timeout_seconds: Timeout for evaluation
        alert_thresholds: Thresholds for quality alerts
    """
    enabled: bool = True
    async_mode: bool = True
    sample_rate: float = 1.0

    # RAGAS metrics to compute
    # Note: context_precision and context_recall require 'reference' (ground truth)
    # which is not available in real-time evaluation scenarios.
    # Only faithfulness and answer_relevancy work without reference.
    metrics: List[str] = field(default_factory=lambda: [
        "faithfulness",
        "answer_relevancy",
    ])

    # LLM configuration for evaluation
    llm_type: str = "fast"

    # Timeout for evaluation (seconds)
    timeout_seconds: int = 600

    # Alert thresholds
    alert_thresholds: AlertThresholds = field(default_factory=AlertThresholds)

    def should_evaluate(self) -> bool:
        """Check if evaluation should be performed based on sampling."""
        if not self.enabled:
            return False
        if self.sample_rate >= 1.0:
            return True
        import random
        return random.random() < self.sample_rate


# Default configuration
DefaultEvaluationConfig = EvaluationConfig()
