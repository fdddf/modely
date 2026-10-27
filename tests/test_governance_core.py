"""Unit tests for governance core modules: rbac, permissions, redaction."""

from __future__ import annotations

import pytest

from modely.governance.rbac import ROLE_ACTIONS, Principal, check_permission
from modely.governance.permissions import (
    DEFAULT_ACTIONS,
    PermissionDecision,
    allow,
    batch_check_permissions,
)
from modely.governance.redaction import (
    REDACTION,
    SENSITIVE_FIELD_NAMES,
    is_sensitive_field,
    permission_filter_items,
    redact_credential_metadata,
    redact_mapping,
    redact_value,
)
from modely.domain.tenants import TenantScope


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def org_scope() -> TenantScope:
    return TenantScope(organization_id="org-1", workspace_id="ws-1")


@pytest.fixture
def alt_scope() -> TenantScope:
    return TenantScope(organization_id="org-2", workspace_id="ws-2")


# ---------------------------------------------------------------------------
# RBAC tests
# ---------------------------------------------------------------------------


class TestCheckPermissionTenantScope:
    """check_permission with TenantScope on Principal."""

    def test_allowed_when_scope_matches_resource(self, org_scope):
        principal = Principal(
            id="u1", roles=["Developer"], tenant_scope=org_scope
        )

        class FakeResource:
            tenant_scope = org_scope

        decision = check_permission(principal, "asset:read", resource=FakeResource())
        assert decision.allowed is True
        assert decision.action == "asset:read"
        assert decision.metadata["principal_id"] == "u1"
        assert decision.metadata["roles"] == ["Developer"]

    def test_denied_when_scope_mismatches_resource(self, org_scope, alt_scope):
        principal = Principal(
            id="u1", roles=["Developer"], tenant_scope=org_scope
        )

        class FakeResource:
            tenant_scope = alt_scope

        decision = check_permission(principal, "asset:read", resource=FakeResource())
        assert decision.allowed is False
        assert decision.reason == "tenant_scope_mismatch"
        assert decision.metadata["principal_id"] == "u1"
        assert decision.metadata["resource_tenant_scope"] == alt_scope

    def test_allowed_when_resource_has_no_scope(self, org_scope):
        principal = Principal(
            id="u1", roles=["Developer"], tenant_scope=org_scope
        )

        class FakeResource:
            pass  # no tenant_scope attribute

        decision = check_permission(principal, "asset:read", resource=FakeResource())
        assert decision.allowed is True


class TestCheckPermission4ArgForm:
    """check_permission with explicit tenant_scope keyword argument."""

    def test_denied_on_tenant_scope_mismatch(self, org_scope, alt_scope):
        principal = Principal(
            id="u1", roles=["Developer"], tenant_scope=org_scope
        )
        decision = check_permission(principal, "asset:read", tenant_scope=alt_scope)
        assert decision.allowed is False
        assert decision.reason == "tenant_scope_mismatch"
        assert decision.metadata["requested_tenant_scope"] == alt_scope

    def test_allowed_on_tenant_scope_match(self, org_scope):
        principal = Principal(
            id="u1", roles=["Developer"], tenant_scope=org_scope
        )
        decision = check_permission(principal, "asset:read", tenant_scope=org_scope)
        assert decision.allowed is True

    def test_no_scope_on_principal_skips_check(self, org_scope):
        principal = Principal(id="u1", roles=["Developer"])
        # principal has no tenant_scope, so scope check is bypassed
        decision = check_permission(principal, "asset:read", tenant_scope=org_scope)
        assert decision.allowed is True


class TestPrincipalFields:
    """Principal with team_memberships and correlation_id."""

    def test_team_memberships_defaults_to_empty(self):
        p = Principal(id="u1")
        assert p.team_memberships == []

    def test_team_memberships_set(self):
        p = Principal(id="u1", team_memberships=["team-a", "team-b"])
        assert p.team_memberships == ["team-a", "team-b"]

    def test_correlation_id_defaults_to_none(self):
        p = Principal(id="u1")
        assert p.correlation_id is None

    def test_correlation_id_set(self):
        p = Principal(id="u1", correlation_id="req-12345")
        assert p.correlation_id == "req-12345"

    def test_service_account_type(self):
        p = Principal(id="sa-1", roles=["Service Account"], principal_type="service_account",
                      correlation_id="trace-abc")
        assert p.principal_type == "service_account"
        assert p.correlation_id == "trace-abc"

    def test_to_dict_includes_correlation_id_when_set(self):
        p = Principal(id="u1", correlation_id="corr-1")
        d = p.to_dict()
        assert d["correlation_id"] == "corr-1"

    def test_to_dict_omits_correlation_id_when_none(self):
        p = Principal(id="u1")
        d = p.to_dict()
        assert "correlation_id" not in d

    def test_to_dict_includes_team_memberships(self):
        p = Principal(id="u1", team_memberships=["team-x"])
        d = p.to_dict()
        assert d["team_memberships"] == ["team-x"]


class TestPermissionDecisionMetadata:
    """PermissionDecision with metadata."""

    def test_allowed_decision_carries_roles_metadata(self):
        p = Principal(id="u1", roles=["Developer"])
        decision = check_permission(p, "asset:read")
        assert decision.allowed is True
        assert decision.metadata["principal_id"] == "u1"
        assert decision.metadata["roles"] == ["Developer"]

    def test_denied_unknown_action_carries_roles_metadata(self):
        p = Principal(id="u1", roles=["Viewer"])
        decision = check_permission(p, "asset:download")
        assert decision.allowed is False
        assert decision.reason == "denied"
        assert decision.metadata["principal_id"] == "u1"
        assert decision.metadata["roles"] == ["Viewer"]

    def test_custom_metadata_on_decision(self):
        decision = PermissionDecision(
            allowed=True, action="asset:read", reason="allowed",
            metadata={"custom": "value"},
        )
        assert decision.metadata["custom"] == "value"

    def test_decision_str_fields(self):
        decision = PermissionDecision(allowed=False, action="asset:delete", reason="denied")
        assert decision.action == "asset:delete"
        assert decision.reason == "denied"
        assert decision.allowed is False


class TestRoleActionsMapping:
    """ROLE_ACTIONS correctness."""

    def test_all_seven_roles_present(self):
        expected_roles = {
            "Platform Admin",
            "Security Admin",
            "Asset Admin",
            "Team Admin",
            "Developer",
            "Viewer",
            "Service Account",
        }
        assert set(ROLE_ACTIONS.keys()) == expected_roles

    def test_platform_admin_has_all_actions(self):
        assert ROLE_ACTIONS["Platform Admin"] == DEFAULT_ACTIONS

    def test_viewer_only_has_asset_read(self):
        assert ROLE_ACTIONS["Viewer"] == {"asset:read"}

    def test_developer_actions(self):
        assert ROLE_ACTIONS["Developer"] == {"asset:read", "asset:download", "asset:scan"}

    def test_service_account_has_token_manage(self):
        assert "token:manage" in ROLE_ACTIONS["Service Account"]

    def test_security_admin_has_policy_manage_and_audit_read(self):
        actions = ROLE_ACTIONS["Security Admin"]
        assert "policy:manage" in actions
        assert "audit:read" in actions

    def test_asset_admin_actions(self):
        actions = ROLE_ACTIONS["Asset Admin"]
        assert "asset:delete" in actions
        assert "asset:publish" in actions
        assert "asset:sync" in actions

    def test_team_admin_actions(self):
        actions = ROLE_ACTIONS["Team Admin"]
        assert "asset:publish" in actions
        assert "asset:scan" in actions
        assert "report:read" in actions


class TestRbacEdgeCases:
    """Edge cases: unknown role, empty roles."""

    def test_unknown_role_yields_no_extra_actions(self):
        p = Principal(id="u1", roles=["UnknownRole"])
        # Unknown role grants nothing -> any action denied
        decision = check_permission(p, "asset:read")
        assert decision.allowed is False

    def test_empty_roles_denies_all(self):
        p = Principal(id="u1", roles=[])
        decision = check_permission(p, "asset:read")
        assert decision.allowed is False

    def test_unknown_role_plus_real_role(self):
        p = Principal(id="u1", roles=["UnknownRole", "Viewer"])
        # Viewer grants asset:read, so it should be allowed
        decision = check_permission(p, "asset:read")
        assert decision.allowed is True

    def test_empty_roles_metadata_still_populated(self):
        p = Principal(id="u1", roles=[])
        decision = check_permission(p, "asset:scan")
        assert decision.metadata["principal_id"] == "u1"
        assert decision.metadata["roles"] == []


# ---------------------------------------------------------------------------
# Permissions tests
# ---------------------------------------------------------------------------


class TestBatchCheckPermissions:
    """batch_check_permissions tests."""

    def test_single_principal_list_of_actions(self):
        p = Principal(id="u1", roles=["Developer"])
        results = batch_check_permissions(p, ["asset:read", "asset:download", "asset:delete"])
        assert isinstance(results, dict)
        assert results["asset:read"].allowed is True
        assert results["asset:download"].allowed is True
        assert results["asset:delete"].allowed is False

    def test_single_principal_list_of_actions_all_keys_present(self):
        p = Principal(id="u1", roles=["Viewer"])
        results = batch_check_permissions(p, ["asset:read", "asset:scan", "asset:delete"])
        assert set(results.keys()) == {"asset:read", "asset:scan", "asset:delete"}

    def test_list_of_tuples_form(self):
        dev = Principal(id="dev", roles=["Developer"])
        viewer = Principal(id="viewer", roles=["Viewer"])
        results = batch_check_permissions([
            (dev, "asset:read"),
            (dev, "asset:delete"),
            (viewer, "asset:read"),
            (viewer, "asset:download"),
        ])
        assert isinstance(results, list)
        assert results[0].allowed is True  # dev asset:read
        assert results[1].allowed is False  # dev asset:delete
        assert results[2].allowed is True  # viewer asset:read
        assert results[3].allowed is False  # viewer asset:download

    def test_list_of_tuples_order_preserved(self):
        p = Principal(id="u1", roles=["Developer"])
        results = batch_check_permissions([
            (p, "asset:delete"),
            (p, "asset:read"),
        ])
        assert len(results) == 2
        assert results[0].action == "asset:delete"
        assert results[0].allowed is False
        assert results[1].action == "asset:read"
        assert results[1].allowed is True

    def test_with_explicit_allowed_actions_set(self):
        p = Principal(id="u1", roles=["Developer"])
        results = batch_check_permissions(
            p, ["asset:read", "asset:delete"],
            allowed_actions_set={"asset:delete"},
        )
        assert results["asset:read"].allowed is False
        assert results["asset:delete"].allowed is True


class TestAllowFunction:
    """allow() function tests."""

    def test_allow_with_custom_allowed_actions(self):
        decision = allow("custom:do_thing", allowed_actions={"custom:do_thing", "asset:read"})
        assert decision.allowed is True
        assert decision.action == "custom:do_thing"

    def test_allow_with_custom_set_denies_unknown(self):
        decision = allow("custom:other_thing", allowed_actions={"custom:do_thing"})
        assert decision.allowed is False
        assert decision.reason == "denied"


class TestDefaultActions:
    """DEFAULT_ACTIONS correctness."""

    def test_contains_12_actions(self):
        assert len(DEFAULT_ACTIONS) == 12

    def test_all_expected_actions_present(self):
        expected = {
            "asset:read",
            "asset:download",
            "asset:sync",
            "asset:publish",
            "asset:approve",
            "asset:delete",
            "asset:scan",
            "asset:manage_acl",
            "report:read",
            "policy:manage",
            "audit:read",
            "token:manage",
        }
        assert DEFAULT_ACTIONS == expected

    def test_default_actions_are_strings_with_colon(self):
        for action in DEFAULT_ACTIONS:
            assert ":" in action


# ---------------------------------------------------------------------------
# Redaction tests
# ---------------------------------------------------------------------------


class TestIsSensitiveField:
    """is_sensitive_field tests."""

    @pytest.mark.parametrize("name", [
        "token",
        "access_token",
        "api_token",
        "authorization",
        "password",
        "secret",
        "private_key",
        "credential",
        "secret_ref",
    ])
    def test_exact_sensitive_names(self, name):
        assert is_sensitive_field(name) is True

    @pytest.mark.parametrize("name", [
        "name",
        "description",
        "created_at",
        "owner",
        "id",
        "url",
        "filename",
    ])
    def test_non_sensitive_names(self, name):
        assert is_sensitive_field(name) is False

    def test_case_insensitive(self):
        assert is_sensitive_field("TOKEN") is True
        assert is_sensitive_field("Password") is True
        assert is_sensitive_field("SECRET") is True

    def test_substring_match(self):
        # "token" appears as substring in "my_token_value"
        assert is_sensitive_field("my_token_value") is True
        # "password" appears in "old_password_hash"
        assert is_sensitive_field("old_password_hash") is True


class TestRedactValue:
    """redact_value tests."""

    def test_redact_token_equals_value(self):
        result = redact_value("token=abc123def")
        assert result == "token=<redacted>"

    def test_redact_secret_equals_value(self):
        result = redact_value("secret=s3cr3t!")
        assert result == "secret=<redacted>"

    def test_redact_password_equals_value(self):
        result = redact_value("password=hunter2")
        assert result == "password=<redacted>"

    def test_redact_api_key_equals_value(self):
        result = redact_value("api_key=sk-12345")
        assert result == "api_key=<redacted>"

    def test_redact_case_insensitive(self):
        result = redact_value("TOKEN=mysecret")
        assert result == "TOKEN=<redacted>"

    def test_non_string_value_passed_through(self):
        assert redact_value(42) == 42
        assert redact_value(None) is None
        assert redact_value([1, 2, 3]) == [1, 2, 3]

    def test_plain_string_without_match_passed_through(self):
        assert redact_value("hello world") == "hello world"

    def test_multiple_sensitive_params_in_one_string(self):
        result = redact_value("token=abc&secret=xyz&other=42")
        assert result == "token=<redacted>&secret=<redacted>&other=42"


class TestRedactMapping:
    """redact_mapping tests."""

    def test_redact_sensitive_top_level_keys(self):
        payload = {"token": "my-secret-token", "name": "test-model"}
        result = redact_mapping(payload)
        assert result["name"] == "test-model"
        assert result["token"] == REDACTION

    def test_redact_nested_dict(self):
        payload = {
            "config": {
                "password": "nested-secret",
                "endpoint": "https://api.example.com",
            },
            "name": "app",
        }
        result = redact_mapping(payload)
        assert result["name"] == "app"
        assert result["config"]["endpoint"] == "https://api.example.com"
        assert result["config"]["password"] == REDACTION

    def test_redact_nested_list_of_dicts(self):
        payload = {
            "credentials": [
                {"name": "cred1", "api_token": "abc"},
                {"name": "cred2", "secret": "xyz"},
            ],
        }
        result = redact_mapping(payload)
        assert result["credentials"][0]["name"] == "cred1"
        assert result["credentials"][0]["api_token"] == REDACTION
        assert result["credentials"][1]["name"] == "cred2"
        assert result["credentials"][1]["secret"] == REDACTION

    def test_redact_list_of_primitives(self):
        payload = {"items": ["token=abc", "plain", "secret=xyz"]}
        result = redact_mapping(payload)
        assert result["items"][0] == "token=<redacted>"
        assert result["items"][1] == "plain"
        assert result["items"][2] == "secret=<redacted>"

    def test_deeply_nested_structure(self):
        payload = {
            "level1": {
                "level2": [
                    {"level3": {"private_key": "pk-deep"}},
                ],
            },
        }
        result = redact_mapping(payload)
        assert result["level1"]["level2"][0]["level3"]["private_key"] == REDACTION


class TestRedactCredentialMetadata:
    """redact_credential_metadata tests."""

    def test_strips_secret_ref(self):
        cred = {
            "id": "cred-1",
            "secret_ref": "vault://secrets/cred-1",
            "source": "github",
            "created_at": "2024-01-01",
        }
        result = redact_credential_metadata(cred)
        assert "id" in result
        assert "source" in result
        assert "created_at" in result
        assert "secret_ref" not in result

    def test_strips_owner_principal_and_owner_team(self):
        cred = {
            "id": "cred-2",
            "owner_principal": "alice",
            "owner_team": "ml-team",
            "source": "huggingface",
        }
        result = redact_credential_metadata(cred)
        assert "id" in result
        assert "source" in result
        assert "owner_principal" not in result
        assert "owner_team" not in result

    def test_redacts_sensitive_fields_even_in_safe_metadata(self):
        cred = {
            "id": "cred-3",
            "token": "should-be-redacted",
            "credential_type": "api_key",
        }
        result = redact_credential_metadata(cred)
        assert result["token"] == REDACTION
        assert result["credential_type"] == "api_key"

    def test_preserves_safe_fields(self):
        safe_fieldnames = [
            "id", "source", "credential_type", "owner",
            "allowed_actions", "created_at", "rotated_at",
            "expires_at", "revoked_at", "last_used_at",
        ]
        for fname in safe_fieldnames:
            cred = {fname: "test-value", "id": "cred-x"}
            result = redact_credential_metadata(cred)
            assert fname in result.keys(), f"Expected '{fname}' to be preserved"


class TestPermissionFilterItems:
    """permission_filter_items tests."""

    def test_filters_by_allowed_actions(self):
        items = [
            {"action": "asset:read", "name": "item1"},
            {"action": "asset:delete", "name": "item2"},
            {"action": "asset:read", "name": "item3"},
        ]
        result = permission_filter_items(items, allowed_actions={"asset:read"})
        assert len(result) == 2
        assert result[0]["name"] == "item1"
        assert result[1]["name"] == "item3"

    def test_filters_by_tenant_scope(self):
        items = [
            {"action": "asset:read", "tenant_scope": "org-1", "name": "a"},
            {"action": "asset:read", "tenant_scope": "org-2", "name": "b"},
            {"action": "asset:read", "tenant_scope": "org-1", "name": "c"},
        ]
        result = permission_filter_items(items, principal_scope="org-1")
        assert len(result) == 2
        assert result[0]["name"] == "a"
        assert result[1]["name"] == "c"

    def test_filters_by_both_scope_and_actions(self):
        items = [
            {"action": "asset:read", "tenant_scope": "org-1", "name": "a"},
            {"action": "asset:delete", "tenant_scope": "org-1", "name": "b"},
            {"action": "asset:read", "tenant_scope": "org-2", "name": "c"},
        ]
        result = permission_filter_items(
            items,
            allowed_actions={"asset:read"},
            principal_scope="org-1",
        )
        assert len(result) == 1
        assert result[0]["name"] == "a"

    def test_redacts_sensitive_fields_in_filtered_items(self):
        items = [
            {"action": "asset:read", "name": "item1", "token": "secret-123"},
        ]
        result = permission_filter_items(items, allowed_actions={"asset:read"})
        assert len(result) == 1
        assert result[0]["token"] == REDACTION
        assert result[0]["name"] == "item1"

    def test_no_filtering_when_no_constraints(self):
        items = [
            {"name": "item1"},
            {"name": "item2"},
        ]
        result = permission_filter_items(items)
        assert len(result) == 2

    def test_item_without_action_field_not_filtered_by_actions(self):
        items = [
            {"name": "no-action-item"},
            {"action": "asset:read", "name": "has-action"},
        ]
        result = permission_filter_items(items, allowed_actions={"asset:read"})
        # no-action item passes through; has-action matches
        assert len(result) == 2

    def test_item_without_scope_not_filtered_by_scope(self):
        items = [
            {"name": "no-scope", "action": "asset:read"},
            {"name": "scoped", "action": "asset:read", "tenant_scope": "org-1"},
        ]
        result = permission_filter_items(items, principal_scope="org-1")
        assert len(result) == 2
