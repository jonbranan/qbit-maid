import logging
import socket
from logging.handlers import RotatingFileHandler


def tor_notify(self):
    """Seting up to use pushover, if self.use_pushover is set to true and 
    if valid self.po_key and self.po_token is provided in the config file"""
    if self.use_pushover:
        self.poc = self.po.Pushover(self.po_token)

def tor_notify_apprise(self, req_obj, app_obj):
    """Use apprise. Apprise has no HTML support, so always use the plain style."""
    opts = get_notify_options(self)
    title, body = build_summary(
        self,
        style="plain",
        use_emoji=opts["use_emoji"],
        include_hostname=opts["include_hostname"],
    )
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
    """Main notification method when the app is used in an automated fashion.

    Formatting is controlled by the ``[pushover]`` config section: ``format``
    (plain|html), ``use_emoji``, ``include_hostname``, ``notify_on_empty``,
    ``priority``, ``sound``, ``retry`` and ``expire``.
    """
    logger = _logger(self)
    opts = get_notify_options(self)
    title, body = build_summary(
        self,
        style=opts["style"],
        use_emoji=opts["use_emoji"],
        include_hostname=opts["include_hostname"],
    )

    if not opts["notify_on_empty"]:
        stats = summary_stats(self)
        if not stats["removed"] and not stats["orphaned"]:
            logger.info("Nothing removed or orphaned, skipping notification.")
            return

    kwargs = {}
    if opts["style"] == "html":
        kwargs["html"] = 1
    if opts["priority"] is not None:
        kwargs["priority"] = opts["priority"]
        if opts["priority"] == 2:
            kwargs["retry"] = opts["retry"]
            kwargs["expire"] = opts["expire"]
    if opts["sound"]:
        kwargs["sound"] = opts["sound"]

    try:
        self.poc.message(self.po_key, body, title=title, **kwargs)
    except Exception as e:  # never let a notification failure abort a run
        logger.error(f"Failed to send pushover notification: {e}")

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

# ---------------------------------------------------------------------------
# Notification formatting
# ---------------------------------------------------------------------------
NOTIFY_STYLES = ("plain", "html")
DEFAULT_NOTIFY_STYLE = "plain"
LABEL_WIDTH = 14
VALUE_WIDTH = 4

NOTIFY_EMOJI = {
    "removed": "\U0001F5D1\uFE0F",
    "orphaned": "\U0001F47B",
    "ignored": "\u23ED\uFE0F",
    "premature": "\U0001F423",
    "protected": "\U0001F6E1\uFE0F",
    "non_protected": "\U0001F310",
}


def _logger(self):
    """Return the configured logger, or a bare one for ad-hoc/test use."""
    return getattr(self, "tl", logging.getLogger(LOGGER_NAME))


def format_runtime(value):
    """Format a timedelta as ``12s``, ``1m 04s`` or ``1h 02m 03s``."""
    try:
        total = int(value.total_seconds())
    except AttributeError:
        return str(value)
    if total < 0:
        total = 0
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes:02d}m {seconds:02d}s"
    if minutes:
        return f"{minutes}m {seconds:02d}s"
    return f"{seconds}s"


def get_notify_options(self):
    """Read notification options from ``[pushover]``, falling back to defaults."""
    config = getattr(self, "config", None) or {}
    po = config.get("pushover", None) or {}
    style = str(po.get("format", DEFAULT_NOTIFY_STYLE) or "").lower()
    if style not in NOTIFY_STYLES:
        style = DEFAULT_NOTIFY_STYLE
    priority = po.get("priority")
    return {
        "style": style,
        "use_emoji": bool(po.get("use_emoji", False)),
        "include_hostname": bool(po.get("include_hostname", False)),
        "notify_on_empty": bool(po.get("notify_on_empty", True)),
        "priority": None if priority is None else int(priority),
        "sound": po.get("sound"),
        "retry": int(po.get("retry", 60)),
        "expire": int(po.get("expire", 3600)),
    }


def summary_runtime(self):
    """Runtime string for the summary, with a fallback to ``self.extm``."""
    start = getattr(self, "st", None)
    end = getattr(self, "et", None)
    if start is not None and end is not None:
        return format_runtime(end - start)
    extm = getattr(self, "extm", "") or ""
    if "[" in extm and "]" in extm:
        return extm[extm.index("[") + 1:extm.rindex("]")]
    return "unknown"


def summary_stats(self):
    """Collect the counters shown in a notification summary."""
    counter = getattr(self, "c", None)
    protected_tag = getattr(self, "tracker_protected_tag", "") or ""
    non_protected_tag = getattr(self, "tracker_non_protected_tag", "") or ""

    def tag_count(tag):
        if counter is None or not tag:
            return 0
        try:
            return counter[tag]
        except (KeyError, TypeError):
            return 0

    return {
        "total": getattr(self, "total_torrents", 0),
        "removed": len(getattr(self, "torrent_hash_delete_list", None) or []),
        "orphaned": getattr(self, "up_tor_counter", 0),
        "ignored": getattr(self, "ignored_counter", 0),
        "premature": getattr(self, "preme_tor_counter", 0),
        "protected": tag_count(protected_tag),
        "non_protected": tag_count(non_protected_tag),
        "runtime": summary_runtime(self),
    }


def send_ping(self, req_obj, healthcheck_url):
    try:
        req_obj.get(healthcheck_url, timeout=5)
    except req_obj.RequestException as e:
        self.tl.info(f"Ping failed: {e}")

def debug_torrent_list(self):
    self.tl.debug(self.torrent_list)


def _notify_row(label, value, style, use_emoji, key):
    """Render one label/value line for the chosen style."""
    emoji = NOTIFY_EMOJI.get(key, "") if use_emoji else ""
    if use_emoji:
        prefix = f"{emoji} " if emoji else ""
        if style == "html":
            return f"{prefix}<b>{label}</b>: {value}"
        return f"{prefix}{label}: {value}"
    if style == "html":
        pad = " " * max(LABEL_WIDTH - len(label), 1)
        return f"<b>{label}</b>{pad}{value:>{VALUE_WIDTH}}"
    return f"{label:<{LABEL_WIDTH}}{value:>{VALUE_WIDTH}}"


def build_summary(self, style=DEFAULT_NOTIFY_STYLE, use_emoji=False,
                  include_hostname=False):
    """Build the ``(title, body)`` pair used by every notifier.

    Result-first layout: the title states what happened, the body gives the
    scanned total, the actionable counters, then the tracker split.

    Args:
        style: ``"plain"`` for aligned text, ``"html"`` for Pushover HTML.
        use_emoji: Prefix each row with an emoji marker.
        include_hostname: Add a ``Host:`` line above the summary.

    Returns:
        A ``(title, body)`` tuple of strings.
    """
    if style not in NOTIFY_STYLES:
        style = DEFAULT_NOTIFY_STYLE

    stats = summary_stats(self)
    delete_enabled = bool(getattr(self, "delete_torrents", False))

    # Title: say what happened. Pushover does not render HTML in titles.
    removed = stats["removed"]
    noun = "torrent" if removed == 1 else "torrents"
    if removed:
        action = "removed" if delete_enabled else "would be removed"
        title = f"qbit-maid: {removed} {noun} {action}"
    elif delete_enabled:
        title = "qbit-maid: nothing removed"
    else:
        title = "qbit-maid: nothing to remove"

    lines = []
    if include_hostname:
        host = socket.gethostname()
        if style == "html":
            lines.append(f"<b>Host:</b> {host}")
        else:
            lines.append(f"Host: {host}")
        lines.append("")

    total = stats["total"]
    scanned_noun = "torrent" if total == 1 else "torrents"
    if style == "html":
        lines.append(f"Scanned <b>{total}</b> {scanned_noun} in <b>{stats['runtime']}</b>")
    else:
        lines.append(f"Scanned {total} {scanned_noun} in {stats['runtime']}")
    lines.append("")

    removed_label = "Removed" if delete_enabled else "Would remove"
    lines.append(_notify_row(removed_label, removed, style, use_emoji, "removed"))
    lines.append(_notify_row("Orphaned", stats["orphaned"], style, use_emoji, "orphaned"))
    lines.append(_notify_row("Ignored", stats["ignored"], style, use_emoji, "ignored"))
    lines.append(_notify_row("Premature", stats["premature"], style, use_emoji, "premature"))
    lines.append("")
    lines.append(_notify_row("Protected", stats["protected"], style, use_emoji, "protected"))
    lines.append(_notify_row("Non-protected", stats["non_protected"], style,
                             use_emoji, "non_protected"))

    return title, "\n".join(lines)


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
