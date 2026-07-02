"""SpecForge — an AI-assisted SDLC toolkit.

Turn an existing codebase plus a business request into structured, traceable
engineering artefacts (specification -> user stories -> acceptance criteria ->
test scenarios), then validate the AI-generated output for completeness,
security, and traceability before it is trusted.

The core is dependency-free (Python standard library only). LLM backends are
pluggable: a deterministic MockLLM for offline/CI use, and an Ollama backend
for local models. Any other provider can be added by implementing LLMClient.
"""

__version__ = "0.1.0"

from .models import (
    AcceptanceCriterion,
    Artefacts,
    CodeUnit,
    Specification,
    TestScenario,
    UserStory,
    ValidationIssue,
)

__all__ = [
    "__version__",
    "CodeUnit",
    "Specification",
    "UserStory",
    "AcceptanceCriterion",
    "TestScenario",
    "ValidationIssue",
    "Artefacts",
]
