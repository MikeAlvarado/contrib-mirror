# Contributing

Thanks for taking the time to contribute. Bug reports, questions, and pull requests are welcome.

## Rules every change must keep

These are the project's hard constraints. They are also listed in `CLAUDE.md`, the file used to brief coding assistants.

- Dates only. The log file and the commits may contain nothing from the source account except `YYYY-MM-DD` dates. A day with N contributions is represented by N identical lines and N commits, never by a number. No repository names, commit messages, or contribution levels. Do not add fields to the log.
- Fail loud. If the contributions fragment cannot be fetched, yields zero cells, or has a day cell without a readable count, exit non-zero with a clear message. Never exit 0 silently.
- Never push. The Action creates commits; the calling workflow pushes.
- Standard library plus `requests` only. Python 3.12.
- No em dashes anywhere. No inline comments in commands or YAML.

## Development setup

```bash
git clone https://github.com/MikeAlvarado/contrib-mirror.git
cd contrib-mirror
python3.12 -m pip install requests
python3.12 -m unittest discover -s tests -v
```

The tests never touch the network. They parse a fixture that mirrors the markup of the real contributions fragment and run the commit flow inside temporary git repositories.

To try a change against a real profile, follow the "Development" section of the README.

## Pull requests

- Open an issue first for anything beyond a small fix, so the approach can be agreed on before the work is done.
- Keep each pull request focused on one topic.
- Add or update tests in `tests/` for any behavior change.
- Update `README.md` and `CHANGELOG.md` when inputs, outputs, or behavior change.
- CI runs the unit tests and a smoke run of the Action against the public graph of the repository owner. Both must pass.

## Releases

For maintainers.

1. Move the changes from the Unreleased section of `CHANGELOG.md` into a new version section with today's date, and commit.
2. Create an annotated tag and push it:

   ```bash
   git tag -a v1.2.0 -m "v1.2.0"
   git push origin v1.2.0
   ```

3. Move the major branch forward so that `@v1` picks up the release:

   ```bash
   git push origin main:refs/heads/v1
   ```

Breaking changes get a new major branch, `v2`, and the README reference changes with it.
