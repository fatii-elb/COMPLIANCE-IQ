# syntax=docker/dockerfile:1.7
# ---------------------------------------------------------------------------
# Multi-stage build for the ComplianceIQ AI Service.
#
# Stage 1 (builder) installs dependencies into an isolated virtualenv so the
# final image carries only what is needed to run — no build tools, no caches.
# Stage 2 (runtime) is a minimal, non-root image. Running as a non-root user is
# a defence-in-depth control: a compromised process cannot trivially escalate.
# ---------------------------------------------------------------------------

# Pin to a specific minor tag. In a hardened pipeline this is pinned by digest
# (@sha256:...) as well; kept as a tag here so the file stays portable.
FROM python:3.11-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /build

# Create the virtualenv first so dependency layers cache independently of source.
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Install the application package itself.
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

# ---------------------------------------------------------------------------
FROM python:3.11-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    CIQ_HOST=0.0.0.0 \
    CIQ_PORT=8000

# Create an unprivileged user to run the service.
RUN groupadd --system --gid 1001 ciq \
    && useradd --system --uid 1001 --gid ciq --home-dir /app --no-create-home ciq

WORKDIR /app
COPY --from=builder /opt/venv /opt/venv

USER ciq
EXPOSE 8000

# Liveness healthcheck. Uses the stdlib so no extra tools are needed in-image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health').status==200 else 1)"

# exec form → the process is PID 1 and receives SIGTERM directly for graceful
# shutdown (proper signal handling in orchestrators).
CMD ["python", "-m", "complianceiq"]
