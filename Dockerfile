# Debian-based image with Python interpreter
FROM debian:stable-slim

# Set locale
ENV LANG=C.UTF-8
# Avoid apt installations to require user interaction
ENV DEBIAN_FRONTEND=noninteractive

# Install crontab
RUN apt-get update && apt-get -y install cron

# Install pyenv
## Install dependencies for pyenv
RUN apt update && apt install --no-install-recommends -y \
    git curl unzip git make build-essential libssl-dev python3-pip python3-setuptools\
    libbz2-dev libreadline-dev libsqlite3-dev wget curl llvm libncurses5-dev \
    libncursesw5-dev xz-utils tk-dev libffi-dev liblzma-dev python3-openssl zlib1g-dev
## Install pyenv from online script
RUN curl https://pyenv.run | bash
## Add bashrc lines to configure pyenv
RUN echo 'export PATH="~/.pyenv/bin:$PATH"' >> ~/.bashrc
RUN echo 'eval "$(pyenv init --path)"' >> ~/.bashrc
## Configure the current shell
ENV PATH="/root/.pyenv/shims:/root/.pyenv/bin:${PATH}"
RUN eval $(pyenv init --path)

# Switch to the /app workdir
WORKDIR /app

# Install repository Python version and set-up virtual environment
COPY .python-version ./
RUN pyenv install

# Install and configure poetry package manager
RUN pip install --upgrade pip
RUN pip install poetry
RUN poetry config virtualenvs.in-project true
COPY poetry.lock  pyproject.toml ./
RUN poetry install

# Activate Poetry's virtual environment
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Suppress caching of compiled Python code
ENV PYTHONDONTWRITEBYTECODE=1

# Copy all sources into container
COPY src src

# Copy main.py file into container
COPY main.py main.py

# Copy logging configuration into container
COPY logging.ini logging.ini

# Copy configure_crontabs.sh into container
COPY configure_crontabs.sh configure_crontabs.sh

# Create logs dir
RUN mkdir logs

# If the CRONTAB expression is not defined, just run the python command, otherwise
# just wait for the crontab triggers.
CMD if [ -z $CRONTAB ]; then for ACCOUNT in $ACCOUNTS; do python main.py -a $ACCOUNT; done; else bash configure_crontabs.sh "$ACCOUNTS" "$CRONTAB"; fi
