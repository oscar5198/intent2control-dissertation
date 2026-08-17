"""Phase 6E.1 backend adapter scaffolds."""

from llm_experiments.inference.adapters.mock import MockAdapter
from llm_experiments.inference.adapters.qmul import (
    AnthropicMessagesQMULAdapter,
    LocalTransformersLlamaQMULAdapter,
    OpenAIResponsesQMULAdapter,
    QMULAdapter,
)
from llm_experiments.inference.adapters.runpod import RunPodAdapter

__all__ = [
    "AnthropicMessagesQMULAdapter",
    "LocalTransformersLlamaQMULAdapter",
    "MockAdapter",
    "OpenAIResponsesQMULAdapter",
    "QMULAdapter",
    "RunPodAdapter",
]
