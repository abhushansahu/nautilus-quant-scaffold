"""Secret resolution from environment variables.

Configs reference environment variable *names*; values are resolved here at runtime.
Secrets must never be hard-coded, logged, or printed in full.
"""

from __future__ import annotations

import os


class MissingSecretError(RuntimeError):
    """Raised when a required secret is not present in the environment."""

    def __init__(self, env_var: str) -> None:
        super().__init__(
            f"Required secret env var '{env_var}' is not set. See .env.example for documentation."
        )
        self.env_var = env_var


def resolve_secret(env_var: str, *, required: bool = True) -> str | None:
    """Return the value of `env_var`, raising `MissingSecretError` if required and unset/empty."""
    value = os.environ.get(env_var)
    if value:
        return value
    if required:
        raise MissingSecretError(env_var)
    return None


def mask_secret(value: str) -> str:
    """Mask a secret for safe display in logs: keep at most the first and last 2 chars."""
    if len(value) <= 6:
        return "*" * len(value)
    return f"{value[:2]}{'*' * (len(value) - 4)}{value[-2:]}"
