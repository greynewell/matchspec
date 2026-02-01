# Base image for SWE-bench task environments
FROM python:3.11-slim

# Install comprehensive system dependencies for SWE-bench tasks
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    wget \
    vim \
    ca-certificates \
    build-essential \
    libssl-dev \
    libffi-dev \
    libpq-dev \
    default-libmysqlclient-dev \
    libxml2-dev \
    libxslt1-dev \
    libjpeg-dev \
    libpng-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up workspace
WORKDIR /workspace

# Install common Python testing tools
RUN pip install --no-cache-dir \
    pytest \
    pytest-xdist \
    coverage

# Default command
CMD ["/bin/bash"]
