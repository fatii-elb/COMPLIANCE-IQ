"""Static safety validation for generated Infrastructure-as-Code.

Before a Terraform remediation is offered (never applied — rule 2), we statically
scan it for **overly-permissive patterns**: a "fix" that opens a bucket to the
world or grants ``*`` to everyone is worse than the original finding. This is a
pure, deterministic scan (no Terraform execution) — a cheap guardrail against the
model proposing a dangerous change.

Patterns are precise IaC constructs (not prose) so that discussing "public access"
in a justification never trips them; only real dangerous HCL/JSON does.
"""

from __future__ import annotations

import re

# (compiled pattern, issue label). Precise enough to match real IaC, not prose.
_FORBIDDEN: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r'"?[Pp]rincipal"?\s*[:=]\s*[\[{]?\s*"\*"'), "wildcard-principal"),
    (re.compile(r'"?[Aa]ction"?\s*[:=]\s*[\[{]?\s*"\*"'), "wildcard-action"),
    (re.compile(r"0\.0\.0\.0/0"), "open-cidr-ipv4"),
    (re.compile(r"::/0"), "open-cidr-ipv6"),
    (re.compile(r'acl\s*=\s*"public-read(-write)?"'), "public-acl"),
    (
        re.compile(r'"?[Ee]ffect"?\s*[:=]\s*"Allow".{0,40}"?[Pp]rincipal"?\s*[:=]\s*"\*"', re.S),
        "allow-all-principals",
    ),
)


def validate_terraform(terraform: str) -> list[str]:
    """Return the labels of any overly-permissive patterns found in ``terraform``.

    An empty list means the snippet passed the static safety scan.
    """
    return [label for pattern, label in _FORBIDDEN if pattern.search(terraform)]
