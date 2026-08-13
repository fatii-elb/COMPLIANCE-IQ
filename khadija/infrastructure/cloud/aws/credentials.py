"""How to obtain an AWS session — never the credentials themselves.

``AwsCredentialConfig`` intentionally has no ``aws_access_key_id``/
``aws_secret_access_key``/``aws_session_token`` fields. Per the Phase 3
brief's explicit preference order (SDK default credential chain > env
vars > profile > IAM role > explicit keys only if strictly necessary),
this project supports only the first four — a named profile (which
itself resolves via boto3's own default chain: env vars, shared
credentials file, or an attached IAM role) and, optionally, assuming a
role via STS. Raw long-lived access keys are never modeled, so there is
no field here that could ever hold one, and nothing in this codebase
can accidentally log or serialize one that was never stored.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AwsCredentialConfig:
    """Configuration for how to obtain an AWS session — a strategy
    pointer, never a secret.
    """

    region: str
    profile: str | None = None
    role_arn: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.region, str) or not self.region.strip():
            raise ValueError("region must be a non-blank string")
        if self.profile is not None and not self.profile.strip():
            raise ValueError("profile must be None or a non-blank string")
        if self.role_arn is not None and not self.role_arn.strip():
            raise ValueError("role_arn must be None or a non-blank string")
