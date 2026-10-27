# Jenkins Integration

modely-ai enterprise integrates with Jenkins as a CI gate and approved asset resolver for build, training, and release jobs.

## Scope

- Run `modely-ai policy check` in Jenkins pipelines.
- Resolve approved assets for downstream training/inference stages.
- Use Jenkins credential binding with Phase 3 service accounts/API tokens.
- Support offline or self-hosted Jenkins deployments.

## Pipeline Example

```groovy
pipeline {
  agent any
  environment {
    MODELY_SERVER = 'https://modely.internal'
  }
  stages {
    stage('Model policy gate') {
      steps {
        withCredentials([string(credentialsId: 'modely-ci-token', variable: 'MODELY_TOKEN')]) {
          sh 'modely-ai policy check modely.lock --profile production --format json'
        }
      }
    }
  }
}
```

This is a target enterprise example. Validate command flags against the implemented CLI before enabling in production.

## Credential Handling

- Use Jenkins credentials, never plaintext pipeline variables.
- Bind service accounts to project/environment scope.
- Rotate and revoke credentials through the enterprise token lifecycle.
- Redact command output and archives.

## Failure Semantics

The build should fail for policy block, approval required, manifest mismatch, invalid lockfile, or insufficient token scope. Warnings may fail or pass depending on the selected policy profile.
