# Spec: Enterprise Identity Integration

## Objective

Define how enterprise identity integrates with modely-ai from local/dev authentication through OIDC, LDAP/group sync, optional SCIM, and service-account lifecycle.

## Identity Modes

| Mode | Use | Notes |
| --- | --- | --- |
| local/dev | Development, demos, single-node trials. | Seed admin/developer/viewer users; not sufficient for production. |
| OIDC | Enterprise SSO. | Preferred production interactive user flow. |
| LDAP/group sync | Enterprise group/team mapping. | May complement OIDC claims. |
| SCIM | Automated lifecycle management. | Optional extension for provisioning/deprovisioning. |
| Service account | CI/CD, training, inference, automation. | Phase 3 machine principal using Phase 2 permissions. |

## Principal Model

Every request resolves:

- principal ID and type: user or service account;
- organization/workspace/project/environment scope;
- team memberships;
- role bindings;
- permission actions;
- auth method and assurance level where available;
- correlation ID for audit.

## OIDC Mapping

OIDC integrations should document mappings for:

- subject/user ID;
- email and display name;
- organization/workspace/project claims;
- groups or roles;
- admin groups;
- session expiry and refresh behavior.

If OIDC claims conflict with local role bindings, deployment policy must define precedence. Recommended default: IdP group membership grants baseline roles; local explicit bindings narrow or extend within tenant scope and are audited.

## LDAP and Group Sync

LDAP/group sync should support:

- scheduled and manual sync;
- group-to-team mapping;
- group-to-role binding mapping;
- dry-run preview;
- removed user handling;
- audit events for mapping changes.

## Deprovisioning

When a user leaves or loses group membership:

- active sessions should expire or be revoked according to deployment policy;
- access tokens owned by the user are revoked or suspended;
- service accounts owned by the user must be transferred, disabled, or reviewed;
- pending approvals by that user are reassigned or escalated;
- audit events record deprovisioning actions.

## Break-glass Admin

Break-glass access must be explicit:

- small allowlist;
- strong secret/credential handling;
- reason required;
- short expiry;
- audit event and optional second review;
- disabled by default in production unless configured.

## Service Account Ownership

Service accounts:

- belong to a project/environment;
- have human or team owners;
- use Phase 2 permission actions;
- have expiry/rotation/revocation;
- emit audit events on creation, use, rotation, revoke;
- should be reviewed periodically.

## Verification

- Contract tests should cover claim mapping, group mapping, deprovisioning behavior, and break-glass audit events when implemented.
- Documentation should distinguish local/dev auth from production IdP integration.
