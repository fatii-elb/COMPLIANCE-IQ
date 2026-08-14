"""Mint an HS256 development token for local testing.

Usage:
    python -m scripts.mint_dev_token --tenant tenant-a --sub demo.analyst --role analyst

Prints a bearer token valid against the running service's HS256 verifier (it uses
the same ``CIQ_*`` settings). Use it in an ``Authorization: Bearer <token>``
header, or paste it into the frontend's "Paste a token" sign-in. This is a
development convenience — production tokens are issued by the Core Service.
"""

from __future__ import annotations

import argparse

from complianceiq.infrastructure.auth.dev_token import mint_hs256_token
from complianceiq.infrastructure.config.settings import get_settings


def main() -> None:
    """Parse arguments, mint a token, and print it."""
    parser = argparse.ArgumentParser(description="Mint an HS256 dev token.")
    parser.add_argument("--tenant", default="tenant-a", help="tenant_id claim")
    parser.add_argument("--sub", default="demo.analyst@acme.example", help="subject claim")
    parser.add_argument("--role", action="append", dest="roles", help="a role (repeatable)")
    parser.add_argument("--ttl-minutes", type=int, default=120, help="token lifetime in minutes")
    args = parser.parse_args()

    settings = get_settings()
    token, expires_at = mint_hs256_token(
        secret=settings.jwt_hs256_secret.get_secret_value(),
        issuer=settings.jwt_issuer,
        audience=settings.jwt_audience,
        subject=args.sub,
        tenant_id=args.tenant,
        roles=args.roles or ["analyst"],
        ttl_seconds=args.ttl_minutes * 60,
    )
    print(token)
    print(f"\n# tenant={args.tenant} sub={args.sub} roles={args.roles or ['analyst']}")
    print(f"# expires_at (epoch) = {expires_at}")
    print(f'# curl: curl -H "Authorization: Bearer {token}" http://localhost:8000/api/v1/findings')


if __name__ == "__main__":
    main()
