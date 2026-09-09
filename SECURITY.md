# Security policy

## Scope

contrib-mirror reads a single public page, `https://github.com/users/<user>/contributions`, without credentials, and creates commits in the repository where it runs. It never pushes, never stores tokens, and the only data it writes is a list of dates. The `GITHUB_TOKEN` of the calling workflow is used only by the workflow's own push step.

## Supported versions

| Reference | Supported |
| --- | --- |
| The `v1` branch and the latest `v1.x` tag | yes |
| Older `v1.x` tags | no, move to `@v1` |

## Reporting a vulnerability

Please do not open a public issue for a security problem. Use the private vulnerability reporting form under the Security tab of this repository. You will get an acknowledgement within a few days, and a fix or mitigation is published as a new `v1.x` tag once available.
