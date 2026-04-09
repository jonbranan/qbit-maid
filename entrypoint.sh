#!/bin/sh

CRON_CONFIG_FILE="/etc/crontabs/root"

echo "${CRON} python /opt/qbit-maid.py" >> $CRON_CONFIG_FILE
echo "@reboot python /opt/qbit-maid.py" >> $CRON_CONFIG_FILE

exec crond -f