# qbit-maid
> Warning: This application removes torrents that are over the minimum age and that are not part of the ignored categories, domains or tags. Please use the delete_torrents feature set to false when first testing its functionality.

![Build Status](https://git.jonb.io/jblu/qbit-maid/actions/workflows/docker.yml/badge.svg)

The objective is to remove torrents based on the following criteria:
- tracker domain name
- age
- ratio
- state

## Install
### Docker(Recommended)

[package](https://git.jonb.io/jblu/-/packages/container/qbit-maid/latest)

    docker pull git.jonb.io/jblu/qbit-maid:latest

#### Docker Run Command:

> Please note it is best practice to escape spaces in variables. That is why there is backslashes in the cron schedule.

    docker run --name qbit-maid -v /opt/qbit-maid:/config/ -e CRON=0\ 1\ *\ *\ * -e toml_path=/config/config.toml git.jonb.io/jblu/qbit-maid

#### Docker Compose

```
version: '3.3'
services:
    qbit-maid:
        image: git.jonb.io/jblu/qbit-maid
        container_name: qbit-maid
        volumes:
            - /opt/qbit-maid:/config
        environment:
            - CRON="0 1 * * *"
            - toml_path=/config/config.toml
```
### Via Git
    git clone https://git.jonb.io/jblu/qbit-maid.git

Qbit-maid will look for an environment variable *toml_path* for its configuration.If it doesn't find it, it will look for a config.toml file in it's own directory.
##### config.toml
```
[qbittorrent]
host = "192.168.x.x"
port = 8080
username = "user"
password = "pass"

[logging]
use_log = true
log_level = "INFO"
log_path = "./qc.log"
# Optional: log rotation (defaults shown)
log_max_bytes = 5000000
log_backup_count = 3

[app_tags]
protected_tag = "ipt"
non_protected_tag = "public"

[torrent]
age = 2419200
minimum_age = 432000
delete_torrents = false

[pushover]
use_pushover = false
po_key = "<key>"
po_token = "<token>"
# Notification formatting
# format: "plain" (aligned text) or "html" (bold labels, Pushover HTML)
format = "plain"
use_emoji = false
include_hostname = false
notify_on_empty = true
# Optional: -2..2. Priority 2 also needs retry/expire (defaults shown).
# priority = 0
# sound = "pushover"
# retry = 60
# expire = 3600

[apprise]
use_apprise = false
host = "192.168.x.x"
port = 8088
aurls = 'mailto://user:pass@gmail.com'

[dragnet]
enable_dragnet = false
dragnet_outfile = "./orphaned.csv"

[telemetry]
enable_telemetry = false
telemetry_outfile = "./telemetry.csv"

[ignored_categories]
tech = "tech"
books = "books"
general = "general"

[ignored_domains]
iptorrents-empirehost = "ssl.empirehost.me"
iptorrents-stackoverflow = "localhost.stackoverflow.tech"
iptorrents-bgp = "routing.bgp.technology"

[ignored_tags]
save = "save"

[healthcheck]
use_healthcheck = false
healthcheck_url = "https://example.com/ping/<uuid>>"
```

## Logging

qbit-maid uses a named logger (`qbit-maid`) that writes to both the configured
log file and the console (useful for Docker/cron output).

- `use_log` — enable or disable logging entirely.
- `log_level` — one of `DEBUG`, `INFO`, `WARN`, `ERROR`, `CRITICAL`.
- `log_path` — path to the log file.
- `log_max_bytes` — rotate the log file once it reaches this size (default 5 MB).
- `log_backup_count` — number of rotated backups to keep (default 3).

Log lines include the timestamp, level, logger name, function, and line number,
for example:

```
10/26/2026 10:10:00 PM [INFO] qbit-maid:tor_processor:24 - Submitted ["My Torrent..."] for deletion.
```

## Notifications

Pushover and Apprise share one summary builder, so both report the same
numbers. The title states the outcome, the body gives the scanned total, the
actionable counters, then the tracker split.

The default summary looks like this:

```
qbit-maid: 7 torrents removed

Scanned 42 torrents in 12s

🗑️ 7 removed  ·  👻 4 orphaned
⏭️ 5 ignored  ·  🐣 3 premature

🛡️ 10 protected  ·  🌐 20 public
```

Each counter is `emoji value label`, grouped two per line and joined with a
middle dot. The value leads so the numbers are the first thing the eye lands
on, and the separator survives any font — Pushover renders the body in a
proportional font, so space-padded columns collapse into a ragged list on a
phone.

`format = "html"` bolds the values using Pushover's HTML subset (`html=1` is
set automatically). Apprise has no HTML support, so it always receives the
plain body.

`use_emoji` defaults to `true`. Set it to `false` for a plain-text variant:

```
Scanned 42 torrents in 12s

7 removed  ·  4 orphaned
5 ignored  ·  3 premature

10 protected  ·  20 public
```

To preview the result without sending a push, render the real
`build_summary()` output as a phone-width mockup:

```
python3 docs/notify-preview.py /tmp/notify.png
```

Pass `--mock` to render the design sketches instead of the live output.

Other options:

- `include_hostname` — add a `Host:` line, useful when several instances notify
  the same device.
- `notify_on_empty` — set to `false` to skip the push when nothing was removed
  or orphaned.
- `priority` / `sound` — passed through to Pushover. Priority `2` automatically
  adds `retry` and `expire`.

When `delete_torrents = false` the summary says `Would remove` instead of
`Removed`, so a dry run is never mistaken for a real one.
