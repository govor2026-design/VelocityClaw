FROM python:3.12-slim

RUN groupadd -r velocity_claw && useradd -r -g velocity_claw velocity_claw

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=velocity_claw:velocity_claw . /app

RUN mkdir -p /workspace /var/lib/velocity-claw /var/log/velocity-claw \
    && chown -R velocity_claw:velocity_claw /workspace /var/lib/velocity-claw /var/log/velocity-claw

USER velocity_claw

ENV WORKSPACE_ROOT=/workspace
ENV SHELL_ENABLED=false
ENV GIT_ENABLED=false
ENV EXECUTION_PROFILE=safe

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "cli.py", "--server"]
