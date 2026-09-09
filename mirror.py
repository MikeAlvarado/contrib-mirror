"""Mirror a GitHub contribution graph into dated commits, one per contribution.

Only dates are stored. Nothing else from the source account is read into
the repository: no repository names, no commit messages, no activity details.
A day with three contributions on the source account gets three commits and
three identical lines in the log file. That repetition is the only way the
number of contributions is represented.

The script never pushes. The calling workflow is responsible for that.
"""

import collections
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

CELL_TAG_RE = re.compile(r'<[^<>]*\sdata-date="\d{4}-\d{2}-\d{2}"[^<>]*>')
DATE_ATTR_RE = re.compile(r'\sdata-date="(\d{4}-\d{2}-\d{2})"')
ID_ATTR_RE = re.compile(r'\sid="([^"]+)"')
TOOLTIP_RE = re.compile(
    r'<tool-tip\b[^<>]*\sfor="([^"]+)"[^<>]*>(.*?)</tool-tip>', re.DOTALL
)
COUNT_RE = re.compile(r"^\s*(No|\d[\d,]*)\s+contributions?\b", re.IGNORECASE)


def fail(message):
    print(f"contrib-mirror: {message}", file=sys.stderr)
    sys.exit(1)


def plural(count, noun):
    if count == 1:
        return f"1 {noun}"
    return f"{count} {noun}s"


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
    """Return (cells, unmatched).

    cells maps date -> contribution count for every day cell whose tooltip
    was found. unmatched is the number of day cells without a readable count.
    """
    counts_by_id = {}
    for match in TOOLTIP_RE.finditer(html):
        count_match = COUNT_RE.match(match.group(2))
        if not count_match:
            continue
        raw = count_match.group(1)
        if raw.lower() == "no":
            counts_by_id[match.group(1)] = 0
        else:
            counts_by_id[match.group(1)] = int(raw.replace(",", ""))

    cells = {}
    unmatched = 0
    for tag_match in CELL_TAG_RE.finditer(html):
        tag = tag_match.group(0)
        date_match = DATE_ATTR_RE.search(tag)
        id_match = ID_ATTR_RE.search(tag)
        try:
            day = dt.date.fromisoformat(date_match.group(1))
        except ValueError:
            continue
        if id_match is None or id_match.group(1) not in counts_by_id:
            unmatched += 1
            continue
        cells[day] = counts_by_id[id_match.group(1)]
    return cells, unmatched


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

    cells, unmatched = parse_cells(response.text)
    if unmatched:
        fail(
            f"GET {response.url}: {plural(unmatched, 'day cell')} without a "
            "readable contribution count. GitHub may have changed the tooltip "
            "markup."
        )
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


def contribution_counts(user, start, end, lookback_days):
    cells = {}
    if lookback_days > 365:
        for chunk_start, chunk_end in year_chunks(start, end):
            cells.update(fetch_cells(user, chunk_start, chunk_end))
    else:
        cells.update(fetch_cells(user))
    return {day: count for day, count in cells.items() if count > 0}


def read_logged(log_file):
    """Return a Counter of date -> how many times it appears in the log."""
    logged = collections.Counter()
    if not os.path.exists(log_file):
        return logged
    with open(log_file, encoding="utf-8") as handle:
        for line in handle:
            text = line.strip()
            if DATE_RE.match(text):
                try:
                    logged[dt.date.fromisoformat(text)] += 1
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


def commit_contribution(config, day, ordinal):
    """Create one commit for the given day.

    ordinal is the zero-based position of this contribution within the day.
    The timestamp is noon of that day plus ordinal seconds, so commits for
    the same day stay in order and all fall on the same calendar day.
    """
    noon = dt.datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=config["tz"])
    stamp_text = (noon + dt.timedelta(seconds=ordinal)).isoformat()
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


def write_output(days, contributions):
    path = os.environ.get("GITHUB_OUTPUT")
    if not path:
        return
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"mirrored-days={days}\n")
        handle.write(f"mirrored-contributions={contributions}\n")


def main():
    config = read_config()
    today = dt.datetime.now(config["tz"]).date()
    start = today - dt.timedelta(days=config["lookback_days"])

    counts = contribution_counts(
        config["source_user"], start, today, config["lookback_days"]
    )
    logged = read_logged(config["log_file"])

    days = 0
    contributions = 0
    for day in sorted(counts):
        if not start <= day <= today:
            continue
        have = logged[day]
        want = counts[day]
        if have >= want:
            continue
        for ordinal in range(have, want):
            commit_contribution(config, day, ordinal)
            contributions += 1
        days += 1

    if contributions == 0:
        print("contrib-mirror: nothing new")
    else:
        print(
            f"contrib-mirror: mirrored {plural(contributions, 'contribution')} "
            f"across {plural(days, 'day')}"
        )
    write_output(days, contributions)


if __name__ == "__main__":
    main()
