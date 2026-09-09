# contrib-mirror

[![CI](https://github.com/MikeAlvarado/contrib-mirror/actions/workflows/ci.yml/badge.svg)](https://github.com/MikeAlvarado/contrib-mirror/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Contribution Mirror is a composite GitHub Action that copies the activity of one GitHub account, typically a work account, onto the contribution graph of another, typically a personal one. It runs inside a repository owned by the destination account, reads the public contribution graph of the source account, and creates one commit per contribution, dated to the day it happened. Only dates are stored: no repository names, no commit messages, nothing else from the source account.

It is free to use under the [MIT license](LICENSE). There is nothing to fork or copy. Reference `MikeAlvarado/contrib-mirror@v1` from a workflow as shown below.

## How it works

1. A scheduled workflow in your destination repository checks out that repository and runs this Action.
2. The Action fetches `https://github.com/users/<source-user>/contributions`, the same public fragment that draws the graph on a profile page, and reads how many contributions each day had.
3. For every contribution not yet recorded in the log file, it appends the date to the log and creates one commit whose message and timestamp are that date.
4. The workflow pushes. The Action itself never pushes.

No token or password is needed for the source account. The commits count for the destination account because their author email is verified there.

## Requirements

- The contribution graph of the source account is visible when logged out. Activity in private repositories appears there only if that account has "Include private contributions on my profile" enabled.
- The `author-email` input is an email address verified on the destination account, the one that owns the repository the Action runs in. Otherwise GitHub does not attribute the commits to that account.
- If the destination repository is private, the destination account also needs "Include private contributions on my profile" enabled, or the mirrored days will not show on its graph.

## Quick start

1. Create a repository under the destination account. Any name works. A public repository is the simplest choice.
2. Add the workflow below as `.github/workflows/mirror.yml`.
3. In the repository settings, create the variables `SOURCE_USER` and `AUTHOR_NAME` and the secret `AUTHOR_EMAIL`. If you would rather not manage variables and secrets, write the values directly in the workflow. The author email is visible in every mirrored commit anyway, and the noreply address of the destination account, shown under Settings and then Emails as `ID+USERNAME@users.noreply.github.com`, works as `author-email` without exposing a personal one.
4. Wait for the first scheduled run, or open the Actions tab, pick "Contribution mirror", and click "Run workflow".

```yaml
name: Contribution mirror

on:
  schedule:
    - cron: "30 5 * * *"
  workflow_dispatch:

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
          lookback-days: "365"

      - run: git push
```

With `lookback-days` set to `365` the first run backfills the past year and every later run catches up on anything missed, for the cost of the same single request. Contributions already in the log file are never mirrored twice. A working example is at [MikeAlvarado/contrib-mirror-BuildPeer](https://github.com/MikeAlvarado/contrib-mirror-BuildPeer).

## Inputs and outputs

| Input | Required | Default | Description |
| --- | --- | --- | --- |
| `source-user` | yes | | GitHub username whose contribution graph is mirrored. |
| `author-name` | yes | | Author name for the mirrored commits. |
| `author-email` | yes | | Author email for the mirrored commits. Must be verified on the destination account. |
| `lookback-days` | no | `3` | Days before today to inspect, inclusive of today. Values above 365 are fetched one calendar year at a time. |
| `log-file` | no | `log.md` | File that records mirrored contributions, one date per line. |
| `timezone` | no | `UTC` | IANA timezone name, used only for the commit timestamp, for example `America/Mexico_City`. |

| Output | Description |
| --- | --- |
| `mirrored-days` | Number of days that received new commits in this run. |
| `mirrored-contributions` | Number of commits created in this run. |

## Versioning

`@v1` always points at the latest 1.x release and is the recommended reference. Pin a tag such as `@v1.1.0` for an exact version. Breaking changes will go to a `v2` branch. Changes are listed in [CHANGELOG.md](CHANGELOG.md).

## Privacy and policy

What is stored in the destination repository:

- The log file, containing one `YYYY-MM-DD` line per mirrored contribution. A day with three contributions appears three times.
- One commit per mirrored contribution, whose message is that date and whose timestamp is noon of that day in the configured timezone, plus one second for each further contribution on the same day.

What is never stored: repository names, commit messages, activity levels, or any other detail from the source account. The number of contributions per day is already visible on the public profile and is reflected only as the number of commits.

Before enabling this, check the policy of the employer or organization that owns the source account on tracking activity publicly. This tool does not bypass any access control. It reads the contribution graph that the source account has already chosen to make public.

## Upgrading from v1.0

Version 1.0 created one commit per active day. A log written by it lists each day once, which version 1.1 reads as one contribution. The next run adds the missing commits for days that had more than one contribution. No manual step is needed.

## Limitations

- Profiles behind enterprise SSO, or profiles that GitHub does not render publicly, are not reachable. The run fails with a clear message.
- GitHub assigns each contribution to a day in UTC. The `timezone` input only affects the timestamp of the mirrored commit, not which day counts as active.
- If GitHub changes the contribution graph markup, the run fails instead of silently mirroring nothing. Zero parsed cells, or a day cell without a readable contribution count, is treated as an error.
- Backfill beyond 365 days relies on the `from` and `to` query parameters of the contributions endpoint. Observed on 2026-09-08: the endpoint honors them only when both dates fall in the same calendar year, and a range that crosses a year boundary snaps to the calendar year of the `to` date. The Action therefore requests one chunk per calendar year. Verify the first backfill run covers the expected range in case that behavior changes.

## Development

The script is a single file, `mirror.py`, that depends only on the standard library and `requests`. Tests use `unittest`.

```bash
python3.12 -m pip install requests
python3.12 -m unittest discover -s tests -v
```

To try a change against a real profile, run the script in a scratch repository with the inputs passed as environment variables:

```bash
git init /tmp/mirror-test
cd /tmp/mirror-test
SOURCE_USER=someuser \
AUTHOR_NAME="Test Author" \
AUTHOR_EMAIL=test@example.com \
LOOKBACK_DAYS=60 \
LOG_FILE=log.md \
TIMEZONE=America/Mexico_City \
python3.12 /path/to/contrib-mirror/mirror.py
git log --format='%ad %s' --date=iso
cat log.md
```

Running it again prints `nothing new` and creates no commits. CI runs the unit tests on every push and pull request, plus a weekly smoke run of the Action against live GitHub markup so that format changes are noticed early.

## Contributing

Bug reports and pull requests are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) first; it lists the few rules every change must keep. This project follows a [code of conduct](CODE_OF_CONDUCT.md). Security issues go through [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE). Copyright 2026 Mike Alvarado.
