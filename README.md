# qbit-maid
> Warning: This application removes torrents that are over the minimum age and that are not part of the ignored categories, domains or tags. Please use the delete_torrents feature set to false when first testing its functionality.

[![Build Status](https://drone.jonb.io/api/badges/jblu/qbit-maid/status.svg?ref=refs/heads/main)](https://drone.jonb.io/jblu/qbit-maid)

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

[app_tags]
protected_tag = "ipt"
non_protected_tag = "public"

[torrent]
age = 2419200
minimum_age = 432000
delete_torrents = false

[pushover]
use_pushover = false
po_key = "<key>>"
po_token = "<token>>"

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