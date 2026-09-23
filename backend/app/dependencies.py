"""FastAPI dependency injection -- wires services together.

No LangChain imports permitted in this module. The AgentService
is imported from the agent layer (which does use LangChain internally),
but this module only references it as a type.
"""

from __future__ import annotations

from typing import Any

# Module-level singletons
_agent_service: Any | None = None
_session_service: Any | None = None


def set_session_service(service: Any) -> None:
    """Set the module-level SessionService singleton.

    Called during application startup (lifespan).

    Args:
        service: The SessionService instance.
    """
    global _session_service
    _session_service = service


def get_session_service() -> Any:
    """FastAPI dependency that returns the SessionService singleton.

    Returns:
        The SessionService instance.

    Raises:
        RuntimeError: If the service has not been initialized.
    """
    if _session_service is None:
        raise RuntimeError("SessionService not initialized. Application startup incomplete.")
    return _session_service


def set_agent_service(service: Any) -> None:
    """Set the module-level AgentService singleton.

    Called during application startup (lifespan).

    Args:
        service: The AgentService instance.
    """
    global _agent_service
    _agent_service = service


def get_agent_service() -> Any:
    """FastAPI dependency that returns the AgentService singleton.

    Returns:
        The AgentService instance.

    Raises:
        RuntimeError: If the service has not been initialized.
    """
    if _agent_service is None:
        raise RuntimeError("AgentService not initialized. Application startup incomplete.")
    return _agent_service
