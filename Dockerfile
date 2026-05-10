FROM python:3.12-slim

# Create non-root user
RUN groupadd -r velocity_claw && useradd -r -g velocity_claw velocity_claw

# Install minimal dependencies for git operations and healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements first for better caching
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=velocity_claw:velocity_claw . /app

# Create workspace directory with proper permissions
RUN mkdir -p /workspace && chown velocity_claw:velocity_claw /workspace

# Switch to non-root user
USER velocity_claw

# Set workspace root to /workspace
ENV WORKSPACE_ROOT=/workspace

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "cli.py", "--server"]
