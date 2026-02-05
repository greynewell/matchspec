# Multi-stage Dockerfile for running mcpbr CLI
# This is NOT the task environment Dockerfile - see Dockerfile for that.
# This image packages the mcpbr benchmark runner itself.

# Stage 1: Build
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build dependencies
RUN pip install --no-cache-dir build hatchling

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY src/ src/

# Build the wheel
RUN python -m build --wheel --outdir /build/dist

# Stage 2: Runtime
FROM python:3.11-slim

LABEL maintainer="mcpbr Contributors"
LABEL org.opencontainers.image.source="https://github.com/greynewell/mcpbr"
LABEL org.opencontainers.image.description="MCP Benchmark Runner - evaluate MCP servers against software engineering benchmarks"
LABEL org.opencontainers.image.licenses="MIT"

# Install runtime system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd --gid 1000 mcpbr && \
    useradd --uid 1000 --gid mcpbr --shell /bin/bash --create-home mcpbr

WORKDIR /home/mcpbr

# Install the built wheel from the builder stage
COPY --from=builder /build/dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && \
    rm -f /tmp/*.whl

# Copy entrypoint
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Create directories for configs and results
RUN mkdir -p /home/mcpbr/configs /home/mcpbr/results && \
    chown -R mcpbr:mcpbr /home/mcpbr

# Switch to non-root user
USER mcpbr

# Mount points for user configs and results
VOLUME ["/home/mcpbr/configs", "/home/mcpbr/results"]

ENTRYPOINT ["entrypoint.sh"]
CMD ["--help"]
