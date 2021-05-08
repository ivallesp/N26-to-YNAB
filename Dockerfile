# Debian-based image with Python interpreter
FROM python:3.6.1-slim

# Install and configure package manager
RUN pip install --upgrade pip
RUN pip install 'poetry==1.1.6'
RUN poetry config virtualenvs.in-project true

# Activate Poetry's virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Project root directory inside container
WORKDIR /app

# Suppress caching of compiled Python code
ENV PYTHONDONTWRITEBYTECODE=1

# Copy manifest and lock file into container
COPY pyproject.toml poetry.lock ./

# Install runtime dependencies only
RUN poetry install --no-dev

# Copy all sources into container
COPY src src

# Copy main.py file into container
COPY main.py main.py

# Copy logging configuration into container
COPY logging.ini logging.ini

# Create logs dir
RUN mkdir logs

# Run python command
CMD for ACCOUNT in $ACCOUNTS; do python main.py -a $ACCOUNT; done