"""Application metadata DTO.

Carries the handful of build/identity facts the ``/version`` endpoint exposes.
It exists so the presentation layer can report name/version/environment without
importing the infrastructure ``Settings`` object — keeping presentation and
infrastructure independent (the ``adapters-are-independent`` contract). The
composition root projects ``Settings`` into this plain DTO.
"""

from __future__ import annotations

from complianceiq.domain._base import FrozenModel


class AppInfo(FrozenModel):
    """Build/identity metadata for the running service.

    Attributes:
        name: Human-readable service name.
        version: Semantic version of the build.
        environment: Deployment environment name (``local``/``production``/…).
    """

    name: str
    version: str
    environment: str
