# contrib-mirror

A composite GitHub Action that mirrors the daily activity of another GitHub
account into the repository where it runs, as one dated commit per active day.

## Hard constraints

- Dates only. The log file and the commits may contain nothing from the
  source account except `YYYY-MM-DD` dates. No repository names, commit
  messages, counts, or contribution levels. Do not add fields to the log.
- Fail loud. If the contributions fragment cannot be fetched or yields zero
  cells, exit non-zero with a clear message. Never exit 0 silently.
- Never push. The Action creates commits; the calling workflow pushes.
- Standard library plus `requests` only. Python 3.12.
- No em dashes anywhere. No inline comments in commands or YAML.
