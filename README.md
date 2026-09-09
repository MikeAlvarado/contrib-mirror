# contrib-mirror

Contribution Mirror is a composite GitHub Action that mirrors the activity of another GitHub account, typically a work account, into the repository where it runs. Every contribution on the source account becomes one commit dated to that day, so a day with three contributions gets three commits and the activity shows on the graph of the account that owns the repository with the same daily totals. Only dates are stored: no repository names, no commit messages, nothing else from the source account.

## Requirements

- The source account has "Include private contributions on my profile" enabled. With that setting on, GitHub renders the contribution graph publicly and no token is needed.
- The `author-email` input is an email address verified on the destination account, the one that owns the repository the Action runs in. Otherwise GitHub does not attribute the commits to that account.
- If the destination repository is private, the destination account also needs "Include private contributions on my profile" enabled, or the mirrored days will not show on its graph.

## Usage

Create `.github/workflows/mirror.yml` in the destination repository. Set the repository variables `SOURCE_USER` and `AUTHOR_NAME`, and the repository secret `AUTHOR_EMAIL`.

```yaml
name: Contribution mirror

on:
  schedule:
    - cron: "30 5 * * *"
    - cron: "0 18 * * *"
  workflow_dispatch:
    inputs:
      lookback-days:
        description: Number of days to look back
        required: false
        default: "3"

permissions:
  contents: write

jobs:
  mirror:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: MikeAlvarado/contrib-mirror@v1
        with:
          source-user: ${{ vars.SOURCE_USER }}
          author-name: ${{ vars.AUTHOR_NAME }}
          author-email: ${{ secrets.AUTHOR_EMAIL }}
          lookback-days: ${{ inputs.lookback-days || '3' }}
          timezone: America/Monterrey

      - run: git push
```

The Action creates commits but never pushes. The final `git push` step is what publishes them.

## Inputs and outputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `source-user` | yes | | GitHub username whose contribution graph is mirrored. |
| `author-name` | yes | | Author name for the mirrored commits. |
| `author-email` | yes | | Author email for the mirrored commits. Must be verified on the destination account. |
| `lookback-days` | no | `3` | Days before today to inspect, inclusive of today. |
| `log-file` | no | `log.md` | File that records mirrored contributions, one date per line. |
| `timezone` | no | `UTC` | IANA timezone name, used only for the commit timestamp. |

| Output | Description |
| --- | --- |
| `mirrored-days` | Number of days that received new commits in this run. |
| `mirrored-contributions` | Number of commits created in this run. |

## Backfill

Open the Actions tab, pick the mirror workflow, choose "Run workflow", and set `lookback-days` to `365`. Contributions already present in the log file are skipped, so running a backfill more than once is safe. Setting `lookback-days` to `365` permanently is also fine: it costs the same single request as a short lookback and lets the mirror catch up by itself after a missed run.

## Privacy and policy

What is stored in the destination repository:

- The log file, containing one `YYYY-MM-DD` line per mirrored contribution. A day with three contributions appears three times.
- One commit per mirrored contribution, whose message is that date and whose timestamp is noon of that day in the configured timezone, plus one second for each further contribution on the same day.

What is never stored: repository names, commit messages, activity levels, or any other detail from the source account. The number of contributions per day is already visible on the public profile and is reflected only as the number of commits.

Before enabling this, check the policy of the employer or organization that owns the source account on tracking activity publicly. This tool does not bypass any access control. It reads the contribution graph that the source account has already chosen to make public through the "Include private contributions on my profile" setting.

## Upgrading from v1.0

Version 1.0 created one commit per active day. A log written by it lists each day once, which version 1.1 reads as one contribution. The next run adds the missing commits for days that had more than one contribution. No manual step is needed.

## Limitations

- Profiles behind enterprise SSO, or profiles that GitHub does not render publicly, are not reachable. The run fails with a clear message.
- GitHub assigns each contribution to a day in UTC. The `timezone` input only affects the timestamp of the mirrored commit, not which day counts as active.
- If GitHub changes the contribution graph markup, the run fails instead of silently mirroring nothing. Zero parsed cells, or a day cell without a readable contribution count, is treated as an error.
- Backfill beyond 365 days relies on the `from` and `to` query parameters of the contributions endpoint. Observed on 2026-09-08: the endpoint honors them only when both dates fall in the same calendar year, and a range that crosses a year boundary snaps to the calendar year of the `to` date. The Action therefore requests one chunk per calendar year. Verify the first backfill run covers the expected range in case that behavior changes.

## Local test

Run the script against a scratch repository with the inputs passed as environment variables.

```bash
git init /tmp/mirror-test
cd /tmp/mirror-test
python3.12 -m pip install requests
SOURCE_USER=someuser \
AUTHOR_NAME="Test Author" \
AUTHOR_EMAIL=test@example.com \
LOOKBACK_DAYS=60 \
LOG_FILE=log.md \
TIMEZONE=America/Monterrey \
python3.12 /path/to/contrib-mirror/mirror.py
git log --format='%ad %s' --date=iso
cat log.md
```

Running it again prints `nothing new` and creates no commits.
