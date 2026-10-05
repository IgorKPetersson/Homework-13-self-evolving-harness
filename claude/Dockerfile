FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       git \
       bash \
       curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN useradd -m harness

USER harness

CMD ["bash"]