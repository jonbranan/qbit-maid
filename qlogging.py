import logging
from logging.handlers import RotatingFileHandler


def tor_notify(self):
    """Seting up to use pushover, if self.use_pushover is set to true and 
    if valid self.po_key and self.po_token is provided in the config file"""
    if self.use_pushover:
        self.poc = self.po.Pushover(self.po_token)

def tor_notify_apprise(self, req_obj, app_obj):
    """Use apprise"""
    body = f"   Total: {self.total_torrents}\n\
    Premature: {self.preme_tor_counter}\n\
    Ignored: {self.ignored_counter}\n\
    Protected: {self.c[self.tracker_protected_tag]}\n\
    Non-protected: {self.c[self.tracker_non_protected_tag]}\n\
    Orphaned: {self.up_tor_counter}\n\
    Marked for deletion: {len(self.torrent_hash_delete_list)}\n\
    {self.extm}"
    title = "--- qbit-maid summary ---"
    app_obj(req_obj, self.apprise_host, self.apprise_port, self.apprise_aurls, title, body)

def tornotifytest(self):
    """Used to make sure tornotify is working and messages are getting to the client"""
    self.poc.message(self.po_key, "Test Message", title="qbit-maid")

def process_counts(self):
    self.c = self.ct()
    for item in self.tracker_list:
        self.c[item["tags"]] += 1
        
def print_processor(self):
    """Print summary of torrents"""
    self.tl.info(f'Total: {self.total_torrents}')
    self.tl.info(f'Premature: {self.preme_tor_counter}')
    self.tl.info(f'Ignored: {self.ignored_counter}')
    self.tl.info(f'Protected: {self.c[self.tracker_protected_tag]}')
    self.tl.info(f'Non-protected: {self.c[self.tracker_non_protected_tag]}')
    self.tl.info(f'Orphaned: {self.up_tor_counter}')
    self.tl.info(f'Marked for deletion: {len(self.torrent_hash_delete_list)}')

def tor_notify_summary(self):
    """Main notification method when the app is used in an automated fashion"""
    self.poc.message(self.po_key, f"   Total: {self.total_torrents}\n\
    Premature: {self.preme_tor_counter}\n\
    Ignored: {self.ignored_counter}\n\
    Protected: {self.c[self.tracker_protected_tag]}\n\
    Non-protected: {self.c[self.tracker_non_protected_tag]}\n\
    Orphaned: {self.up_tor_counter}\n\
    Marked for deletion: {len(self.torrent_hash_delete_list)}\n\
    {self.extm}", title="--- qbit-maid summary ---")

def list_first_tor(self, index=0):
    """Only lists the first torrent"""
    self.tl.debug('First torrent in the list:')
    torrent = self.torrent_list[index]
    for k,v in torrent.items():
         self.tl.debug(f'{k}:  {v}')
    self.tl.debug('\n')

def list_qbit_api_info(self):
        """Writes torrent info to log file"""
        self.tl.debug(f'qBittorrent: {self.qbt_client.app.version}')
        self.tl.debug(f'qBittorrent Web API: {self.qbt_client.app.web_api_version}')

def torrent_count(self):
    """write torrent counts to log file"""
    self.tl.debug(f'*** Torrents with tag["{self.tracker_protected_tag}"] {self.c[self.tracker_protected_tag]} ***')
    self.tl.debug(f'*** Torrents with tag["{self.tracker_non_protected_tag}"] {self.c[self.tracker_non_protected_tag]} ***')

def get_script_runtime(self):
    elapsed_time = self.et - self.st
    self.tl.info(f'Execution time: [{elapsed_time}]')
    if self.use_pushover:
        self.extm = f"Execution time: [{elapsed_time}]"
    if self.use_apprise:
        self.extm = f"Execution time: [{elapsed_time}]"

def send_ping(self, req_obj, healthcheck_url):
    try:
        req_obj.get(healthcheck_url, timeout=5)
    except req_obj.RequestException as e:
        self.tl.info(f"Ping failed: {e}")

def debug_torrent_list(self):
    self.tl.debug(self.torrent_list)


# ---------------------------------------------------------------------------
# New logging infrastructure (Phase 1 & 3)
# ---------------------------------------------------------------------------
LOGGER_NAME = "qbit-maid"
DEFAULT_MAX_BYTES = 5_000_000
DEFAULT_BACKUP_COUNT = 3


def setup_logging(use_log: bool, log_path: str, log_level: str,
                  max_bytes: int = DEFAULT_MAX_BYTES,
                  backup_count: int = DEFAULT_BACKUP_COUNT) -> logging.Logger:
    """Configure and return the qbit-maid logger.

    Args:
        use_log: If False, adds a NullHandler and sets level to CRITICAL.
        log_path: Path to the log file.
        log_level: One of debug, info, warn, warning, error, critical.
        max_bytes: Max size of a log file before rotation (default 5 MB).
        backup_count: Number of rotated backups to keep (default 3).

    Returns:
        A configured :class:`logging.Logger` named ``"qbit-maid"``.
    """
    logger = logging.getLogger(LOGGER_NAME)

    # Make setup idempotent: clear any handlers from a previous call
    for handler in list(logger.handlers):
        logger.removeHandler(handler)

    if not use_log:
        logger.addHandler(logging.NullHandler())
        logger.setLevel(logging.CRITICAL)
        return logger

    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warn": logging.WARNING,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }
    level = level_map.get(log_level.lower(), logging.INFO)
    logger.setLevel(level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        datefmt="%m/%d/%Y %I:%M:%S %p",
    )

    # File handler with rotation
    file_handler = RotatingFileHandler(
        log_path, maxBytes=max_bytes, backupCount=backup_count, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Console handler for Docker / cron visibility
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger


def log_torrent(logger: logging.Logger, level: int, torrent: dict, message: str = ""):
    """Log a torrent record with structured extra fields.

    Args:
        logger: The qbit-maid logger instance.
        level: Logging level constant (e.g. ``logging.INFO``).
        torrent: A dict with torrent fields (hash, name, tracker, tags, etc.).
        message: Optional human-readable message.
    """
    extra = {
        "torrent_hash": torrent.get("infohash_v1", ""),
        "torrent_name": (torrent.get("name", "") or "")[:20],
        "torrent_tracker": torrent.get("tracker", "") or "",
        "torrent_tags": torrent.get("tags", "") or "",
    }
    logger.log(level, message, extra=extra)