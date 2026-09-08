"""Mirror active days from a GitHub contribution graph into dated commits.

Only dates are stored. Nothing else from the source account is read into
the repository: no repository names, no commit messages, no counts.

The script never pushes. The calling workflow is responsible for that.
"""

import datetime as dt
import os
import re
import subprocess
import sys
from zoneinfo import ZoneInfo

import requests

CONTRIBUTIONS_URL = "https://github.com/users/{user}/contributions"
USER_AGENT = "contrib-mirror"
REQUEST_TIMEOUT = 30
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

CELL_RE = re.compile(
    r"<[^<>]*?(?:"
    r'data-date="(?P<date_a>\d{4}-\d{2}-\d{2})"[^<>]*?data-level="(?P<level_a>\d+)"'
    r"|"
    r'data-level="(?P<level_b>\d+)"[^<>]*?data-date="(?P<date_b>\d{4}-\d{2}-\d{2})"'
    r")[^<>]*>"
)


def fail(message):
    print(f"contrib-mirror: {message}", file=sys.stderr)
    sys.exit(1)


def read_config():
    source_user = os.environ.get("SOURCE_USER", "").strip()
    author_name = os.environ.get("AUTHOR_NAME", "").strip()
    author_email = os.environ.get("AUTHOR_EMAIL", "").strip()
    lookback_raw = os.environ.get("LOOKBACK_DAYS", "3").strip()
    log_file = os.environ.get("LOG_FILE", "log.md").strip() or "log.md"
    timezone = os.environ.get("TIMEZONE", "UTC").strip() or "UTC"

    if not source_user:
        fail("SOURCE_USER is required")
    if not author_name:
        fail("AUTHOR_NAME is required")
    if not author_email:
        fail("AUTHOR_EMAIL is required")
    try:
        lookback_days = int(lookback_raw)
    except ValueError:
        fail(f"LOOKBACK_DAYS must be an integer, got {lookback_raw!r}")
    if lookback_days < 0:
        fail("LOOKBACK_DAYS must not be negative")
    try:
        tz = ZoneInfo(timezone)
    except Exception:
        fail(f"TIMEZONE {timezone!r} is not a valid IANA timezone name")

    return {
        "source_user": source_user,
        "author_name": author_name,
        "author_email": author_email,
        "lookback_days": lookback_days,
        "log_file": log_file,
        "tz": tz,
    }


def parse_cells(html):
    """Return a dict of date -> level for every cell found in the fragment."""
    cells = {}
    for match in CELL_RE.finditer(html):
        date_text = match.group("date_a") or match.group("date_b")
        level_text = match.group("level_a") or match.group("level_b")
        try:
            cells[dt.date.fromisoformat(date_text)] = int(level_text)
        except ValueError:
            continue
    return cells


def fetch_cells(user, start=None, end=None):
    url = CONTRIBUTIONS_URL.format(user=user)
    params = None
    if start is not None and end is not None:
        params = {"from": start.isoformat(), "to": end.isoformat()}
    try:
        response = requests.get(
            url,
            params=params,
            headers={"User-Agent": USER_AGENT},
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        fail(f"request to {url} failed: {exc}")

    if response.status_code != 200:
        fail(
            f"GET {response.url} returned HTTP {response.status_code}. "
            f"Either the user {user!r} does not exist, the profile is behind "
            "enterprise SSO, or GitHub changed the endpoint."
        )

    cells = parse_cells(response.text)
    if not cells:
        fail(
            f"GET {response.url} returned HTTP 200 but no contribution cells "
            f"were parsed. Either the user {user!r} does not exist, the profile "
            'is behind enterprise SSO, "Include private contributions on my '
            'profile" is off, or GitHub changed the markup.'
        )
    return cells


def year_chunks(start, end):
    """Split [start, end] into pieces that never cross a calendar year."""
    chunks = []
    for year in range(start.year, end.year + 1):
        chunk_start = max(start, dt.date(year, 1, 1))
        chunk_end = min(end, dt.date(year, 12, 31))
        chunks.append((chunk_start, chunk_end))
    return chunks


def active_days(user, start, end, lookback_days):
    cells = {}
    if lookback_days > 365:
        for chunk_start, chunk_end in year_chunks(start, end):
            cells.update(fetch_cells(user, chunk_start, chunk_end))
    else:
        cells.update(fetch_cells(user))
    return {day for day, level in cells.items() if level > 0}


def read_logged(log_file):
    logged = set()
    if not os.path.exists(log_file):
        return logged
    with open(log_file, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if DATE_RE.match(text):
                try:
                    logged.add(dt.date.fromisoformat(text))
                except ValueError:
                    continue
    return logged


def append_date(log_file, day):
    needs_newline = False
    if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
        with open(log_file, "rb") as handle:
            handle.seek(-1, os.SEEK_END)
            needs_newline = handle.read(1) != b"\n"
    with open(log_file, "a", encoding="utf-8") as handle:
        if needs_newline:
            handle.write("\n")
        handle.write(f"{day.isoformat()}\n")


def run_git(args, extra_env=None):
    env = dict(os.environ)
    if extra_env:
        env.update(extra_env)
    try:
        subprocess.run(["git", *args], check=True, env=env)
    except (subprocess.CalledProcessError, OSError) as exc:
        fail(f"git {' '.join(args)} failed: {exc}")


def commit_day(config, day):
    stamp = dt.datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=config["tz"])
    stamp_text = stamp.isoformat()
    append_date(config["log_file"], day)
    run_git(["add", "--", config["log_file"]])
    run_git(
        [
            "-c",
            f"user.name={config['author_name']}",
            "-c",
            f"user.email={config['author_email']}",
            "commit",
            "-qm",
            day.isoformat(),
        ],
        {"GIT_AUTHOR_DATE": stamp_text, "GIT_COMMITTER_DATE": stamp_text},
    )


def write_output(count):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"mirrored-days={count}\n")


def main():
    config = read_config()
    today = dt.datetime.now(config["tz"]).date()
    start = today - dt.timedelta(days=config["lookback_days"])

    active = active_days(config["source_user"], start, today, config["lookback_days"])
    logged = read_logged(config["log_file"])
    missing = sorted(day for day in active if start <= day <= today and day not in logged)

    for day in missing:
        commit_day(config, day)

    count = len(missing)
    if count == 0:
        print("contrib-mirror: nothing new")
    elif count == 1:
        print("contrib-mirror: mirrored 1 day")
    else:
        print(f"contrib-mirror: mirrored {count} days")
    write_output(count)


if __name__ == "__main__":
    main()
