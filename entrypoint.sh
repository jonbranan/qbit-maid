#!/bin/sh

CRON_CONFIG_FILE="/etc/crontabs/root"

grep -qF 'python /opt/qbit-maid.py' $CRON_CONFIG_FILE || echo "${CRON} python /opt/qbit-maid.py" >> $CRON_CONFIG_FILE
grep -qF '@reboot' $CRON_CONFIG_FILE || echo "@reboot python /opt/qbit-maid.py" >> $CRON_CONFIG_FILE

exec crond -f