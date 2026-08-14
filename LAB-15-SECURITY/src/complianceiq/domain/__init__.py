"""Domain layer — the enterprise core.

Contains entities, value objects, ports (interfaces), and policies. This layer
has ZERO dependencies on frameworks, databases, or providers: it imports only
the Python standard library and Pydantic. That purity is enforced automatically
by the ``domain-is-pure`` import-linter contract.

Everything the outer layers implement (LLM providers, vector stores,
repositories, clocks) is defined here as an abstract *port* so the business
rules never know which concrete technology fulfils them.
"""
