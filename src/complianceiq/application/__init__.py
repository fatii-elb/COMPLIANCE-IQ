"""Application layer — use cases that orchestrate the domain.

Each use case is a small, single-purpose object that coordinates domain entities
and ports to fulfil one piece of application behaviour (check readiness now;
enrich a finding, answer a question, generate a report in later phases). Use
cases depend only on the domain and on ports — never on FastAPI, SQLAlchemy, or
any provider SDK. That is enforced by the ``application-is-framework-free``
import-linter contract.
"""
