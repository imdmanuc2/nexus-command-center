"""Managed executor framework for Nexus operations automation."""

from backend.executors.registry import get_executor_registry

__all__ = ["get_executor_registry"]
