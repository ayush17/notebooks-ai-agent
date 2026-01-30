"""Core module for DevAssist.

Contains the core services. Legacy manager classes have been deprecated
in favor of the unified ClientConfig and self-contained ClaudeClient architecture.
"""

from devassist.core.brief_generator import BriefGenerator

# Legacy managers removed in favor of unified architecture:
# - CacheManager → utility functions in devassist.utils.cache
# - ConfigManager → devassist.models.config.ClientConfig
# - SessionManager → ClaudeClient static session store

__all__ = [
    "BriefGenerator",
]
