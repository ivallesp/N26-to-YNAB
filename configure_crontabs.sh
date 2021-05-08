#!/bin/bash

ACCOUNTS=$1
CRONTAB=$2

echo ACCOUNTS: $ACCOUNTS
echo CRONTAB: $CRONTAB

# Create the crontab
touch /etc/cron.d/app

# Fill the crontab
for ACCOUNT in $ACCOUNTS; do
    echo "$CRONTAB"'    cd /app && .venv/bin/python main.py -a '"$ACCOUNT" >> /etc/cron.d/app
done

# Give execution rights on the cron job
chmod 0644 /etc/cron.d/app

# Apply cron job
crontab /etc/cron.d/app

# Create the log file to be able to run tail
touch /var/log/cron.log

# Run the cron and show the log
cron && tail -f /var/log/cron.log