# GitLab Integration

modely-ai enterprise treats GitLab projects as CI/CD and internal tool/code asset integration points.

## Scope

- Use GitLab CI to run `modely-ai policy check` against lockfiles, manifests, or catalog reports.
- Use scoped service-account/API tokens from Phase 3.
- Support self-hosted GitLab and intranet deployments.
- Treat GitLab repositories as `tool` or internal engineering assets when mirrored into the catalog.

## CI Gate Example

```yaml
modely_policy_gate:
  image: python:3.11
  script:
    - pip install modely-ai
    - modely-ai policy check modely.lock --profile production --format json
  artifacts:
    when: always
    paths:
      - modely-policy-report.json
```

This is a target enterprise example. Validate command flags against the implemented CLI before enabling in production.

## Credential Handling

- Store tokens in GitLab CI masked/protected variables.
- Prefer project/environment-bound service accounts.
- Rotate credentials and audit usage.
- Do not print raw tokens or signed URLs.

## Failure Semantics

The policy gate should fail for blocked assets, missing approvals, checksum/manifest mismatches, and invalid lockfiles. Warning behavior is configurable by policy profile.

## Offline/Self-hosted Notes

- Use internal package indexes and container registries.
- Point modely-ai to the internal `modely-server` endpoint.
- Keep external source access disabled unless explicitly allowed.
