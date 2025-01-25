FROM python:3.12.2-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV DEBIAN_FRONTEND noninteractive

WORKDIR /code

RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-thai-tlwg \
    build-essential \
    python3-dev \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf2.0-0 \
    libffi-dev \
    shared-mime-info \
    netcat-traditional \
    libpq-dev \
    nodejs \
    npm \
    cron \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY ./requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt

COPY . .

RUN chmod +x /code/entrypoint.sh \
        && chown root:root /code/entrypoint.sh
    
    # Use shell form cmd
ENTRYPOINT ["/bin/sh", "/code/entrypoint.sh"]
