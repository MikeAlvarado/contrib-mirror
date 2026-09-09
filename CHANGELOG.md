# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.1.2] - 2026-09-09

### Changed

- Shorter `action.yml` description to meet the Marketplace limit of 125 characters. No change in behavior.

## [1.1.1] - 2026-09-09

### Added

- Unit tests, a CI workflow with a weekly smoke run against live GitHub markup, and contributor documentation. README rewritten as a guide for any account. No change in behavior.

## [1.1.0] - 2026-09-09

### Changed

- One commit per contribution instead of one per active day. The count is read from the same public page and represented only by repeating the date line in the log file. Logs written by 1.0.0 are completed automatically on the next run.
- The run now also fails when a day cell has no readable contribution count.

### Added

- `mirrored-contributions` output.

## [1.0.0] - 2026-09-09

### Added

- Initial release. One commit per active day, dates only, fail loud, never push.

[Unreleased]: https://github.com/MikeAlvarado/contrib-mirror/compare/v1.1.2...HEAD
[1.1.2]: https://github.com/MikeAlvarado/contrib-mirror/compare/v1.1.1...v1.1.2
[1.1.1]: https://github.com/MikeAlvarado/contrib-mirror/compare/v1.1.0...v1.1.1
[1.1.0]: https://github.com/MikeAlvarado/contrib-mirror/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/MikeAlvarado/contrib-mirror/releases/tag/v1.0.0
