"""Tests for mirror.py. They never touch the network."""

import collections
import contextlib
import datetime as dt
import io
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import mirror

FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "contributions.html"


def git(*args, cwd):
    result = subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    )
    return result.stdout


def fixture_html():
    return FIXTURE.read_text(encoding="utf-8")


class ParseCellsTest(unittest.TestCase):
    def test_reads_counts_from_tooltips(self):
        cells, unmatched = mirror.parse_cells(fixture_html())
        self.assertEqual(unmatched, 0)
        self.assertEqual(
            cells,
            {
                dt.date(2026, 8, 31): 0,
                dt.date(2026, 9, 1): 3,
                dt.date(2026, 9, 2): 1,
                dt.date(2026, 9, 3): 1234,
            },
        )

    def test_counts_cells_without_tooltip_as_unmatched(self):
        html = '<td data-date="2026-09-01" id="contribution-day-component-0-1"></td>'
        cells, unmatched = mirror.parse_cells(html)
        self.assertEqual(cells, {})
        self.assertEqual(unmatched, 1)

    def test_ignores_tooltips_without_a_count(self):
        html = (
            '<td data-date="2026-09-01" id="c-1"></td>'
            '<tool-tip for="c-1">Something else entirely.</tool-tip>'
        )
        cells, unmatched = mirror.parse_cells(html)
        self.assertEqual(cells, {})
        self.assertEqual(unmatched, 1)

    def test_attribute_order_does_not_matter(self):
        html = (
            '<td id="c-1" data-level="2" data-date="2026-09-01"></td>'
            '<tool-tip data-type="label" for="c-1">2 contributions on September 1st.</tool-tip>'
        )
        cells, unmatched = mirror.parse_cells(html)
        self.assertEqual(cells, {dt.date(2026, 9, 1): 2})
        self.assertEqual(unmatched, 0)


class FetchCellsTest(unittest.TestCase):
    def fake_response(self, status, text):
        response = mock.Mock()
        response.status_code = status
        response.text = text
        response.url = "https://github.com/users/someone/contributions"
        return response

    def fetch_with(self, status, text):
        with mock.patch.object(
            mirror.requests, "get", return_value=self.fake_response(status, text)
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                return mirror.fetch_cells("someone")

    def test_returns_counts(self):
        cells = self.fetch_with(200, fixture_html())
        self.assertEqual(cells[dt.date(2026, 9, 1)], 3)

    def test_fails_on_http_error(self):
        with self.assertRaises(SystemExit):
            self.fetch_with(404, "")

    def test_fails_when_no_cells(self):
        with self.assertRaises(SystemExit):
            self.fetch_with(200, "<html></html>")

    def test_fails_when_a_cell_has_no_count(self):
        with self.assertRaises(SystemExit):
            self.fetch_with(200, '<td data-date="2026-09-01" id="c-1"></td>')


class ReadLoggedTest(unittest.TestCase):
    def test_counts_repeated_dates_and_skips_other_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "log.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "2026-09-01\n2026-09-01\nnot a date\n\n2026-09-02\n2026-13-45\n"
                )
            logged = mirror.read_logged(path)
        self.assertEqual(
            logged,
            collections.Counter({dt.date(2026, 9, 1): 2, dt.date(2026, 9, 2): 1}),
        )

    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            logged = mirror.read_logged(os.path.join(tmp, "missing.md"))
        self.assertEqual(logged, collections.Counter())


class YearChunksTest(unittest.TestCase):
    def test_splits_at_calendar_year_boundaries(self):
        chunks = mirror.year_chunks(dt.date(2024, 11, 20), dt.date(2026, 2, 3))
        self.assertEqual(
            chunks,
            [
                (dt.date(2024, 11, 20), dt.date(2024, 12, 31)),
                (dt.date(2025, 1, 1), dt.date(2025, 12, 31)),
                (dt.date(2026, 1, 1), dt.date(2026, 2, 3)),
            ],
        )


class MainTest(unittest.TestCase):
    """Run the whole flow inside a temporary git repository."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = self.tmp.name
        git("init", "-q", cwd=self.repo)
        self.previous_cwd = os.getcwd()
        os.chdir(self.repo)
        self.output_path = os.path.join(self.repo, "github-output.txt")
        self.env = mock.patch.dict(
            os.environ,
            {
                "SOURCE_USER": "someone",
                "AUTHOR_NAME": "Test Author",
                "AUTHOR_EMAIL": "test@example.com",
                "LOOKBACK_DAYS": "30",
                "LOG_FILE": "log.md",
                "TIMEZONE": "UTC",
                "GITHUB_OUTPUT": self.output_path,
            },
        )
        self.env.start()
        self.today = dt.datetime.now(dt.timezone.utc).date()

    def tearDown(self):
        self.env.stop()
        os.chdir(self.previous_cwd)
        self.tmp.cleanup()

    def run_main(self, counts):
        with mock.patch.object(mirror, "fetch_cells", return_value=counts):
            with contextlib.redirect_stdout(io.StringIO()):
                mirror.main()

    def commits(self):
        """Return (author timestamp as epoch seconds, message) per commit, newest first."""
        out = git("log", "--format=%at %s", cwd=self.repo)
        commits = []
        for line in out.strip().splitlines():
            stamp, message = line.split(" ", 1)
            commits.append((int(stamp), message))
        return commits

    def noon(self, day, ordinal=0):
        stamp = dt.datetime(day.year, day.month, day.day, 12, 0, 0, tzinfo=dt.timezone.utc)
        return int(stamp.timestamp()) + ordinal

    def log_lines(self):
        with open("log.md", encoding="utf-8") as handle:
            return handle.read().splitlines()

    def outputs(self):
        with open(self.output_path, encoding="utf-8") as handle:
            return handle.read()

    def test_one_commit_per_contribution_within_lookback(self):
        yesterday = self.today - dt.timedelta(days=1)
        long_ago = self.today - dt.timedelta(days=200)
        self.run_main({self.today: 2, yesterday: 1, long_ago: 5})

        today = self.today.isoformat()
        self.assertEqual(
            self.commits(),
            [
                (self.noon(self.today, 1), today),
                (self.noon(self.today, 0), today),
                (self.noon(yesterday, 0), yesterday.isoformat()),
            ],
        )
        self.assertEqual(self.log_lines(), [yesterday.isoformat(), today, today])
        self.assertEqual(self.outputs(), "mirrored-days=2\nmirrored-contributions=3\n")

    def test_second_run_adds_only_what_is_missing(self):
        self.run_main({self.today: 1})
        self.run_main({self.today: 1})
        self.assertEqual(len(self.commits()), 1)

        self.run_main({self.today: 3})
        commits = self.commits()
        self.assertEqual(len(commits), 3)
        self.assertEqual(commits[0][0], self.noon(self.today, 2))
        self.assertEqual(self.log_lines(), [self.today.isoformat()] * 3)
        self.assertEqual(
            self.outputs(),
            "mirrored-days=1\nmirrored-contributions=1\n"
            "mirrored-days=0\nmirrored-contributions=0\n"
            "mirrored-days=1\nmirrored-contributions=2\n",
        )

    def test_log_from_v1_0_counts_as_one_contribution_per_day(self):
        with open("log.md", "w", encoding="utf-8") as handle:
            handle.write(f"{self.today.isoformat()}\n")
        git("add", "log.md", cwd=self.repo)
        git("-c", "user.name=Seed", "-c", "user.email=seed@example.com", "commit", "-qm", "seed", cwd=self.repo)

        self.run_main({self.today: 2})
        self.assertEqual(len(self.commits()), 2)
        self.assertEqual(self.log_lines(), [self.today.isoformat()] * 2)
        self.assertEqual(self.outputs(), "mirrored-days=1\nmirrored-contributions=1\n")


if __name__ == "__main__":
    unittest.main()
