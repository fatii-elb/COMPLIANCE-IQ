"""Infrastructure layer — adapters to the outside world.

Everything that talks to a framework, a network, a database, or a vendor SDK
lives here and nowhere else: configuration loading, structured logging, the
system clock, and (in later phases) the SQLAlchemy repositories, the Anthropic
provider, the pgvector store, and the Core API client. Each adapter implements a
port defined in the domain, so the business logic never depends on these
concrete choices.
"""
