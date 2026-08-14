"""Presentation layer — the HTTP delivery mechanism (FastAPI).

This layer translates HTTP into calls on application use cases and translates
their results (and domain exceptions) back into HTTP. It contains no business
logic: routers are thin, request/response schemas validate the wire format, and
exception handlers own the single mapping from domain errors to status codes.
It is wired to the infrastructure adapters only at the composition root.
"""
