"""Phase 6E model-agnostic inference framework."""

from llm_experiments.inference.base import ModelAdapter
from llm_experiments.inference.failures import FAILURE_HANDLING_VERSION
from llm_experiments.inference.requests import INFERENCE_INTERFACE_VERSION, make_inference_request
from llm_experiments.inference.runner import build_execution_manifest, run_mock_inference
from llm_experiments.inference.state_machine import run_synthetic_failure_matrix

__all__ = [
    "INFERENCE_INTERFACE_VERSION",
    "FAILURE_HANDLING_VERSION",
    "ModelAdapter",
    "build_execution_manifest",
    "make_inference_request",
    "run_mock_inference",
    "run_synthetic_failure_matrix",
]
