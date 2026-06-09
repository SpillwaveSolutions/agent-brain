"""Unit tests for Settings auth fields added by Issue #199 plumbing.

Sub-plan 199-01 adds two new Settings fields alongside the existing
AGENT_BRAIN_API_KEY:
- API_KEY: SecretStr | None — the canonical Bearer token storage
- INSECURE_NO_AUTH: bool — the --insecure opt-out flag

Neither is wired into the routers yet. Sub-plan 199-02 swaps
verify_api_key → verify_bearer_token to actually consume API_KEY.
These tests pin the field shape so the 199-02 swap is mechanical.
"""

from pydantic import SecretStr

from agent_brain_server.config.settings import Settings


class TestNewAuthFields:
    """Plumbing-only tests for Issue #199 sub-plan 199-01 field additions."""

    def test_api_key_defaults_to_none(self):
        """API_KEY is None by default — server is unauthenticated unless explicit."""
        settings = Settings(_env_file=None)
        assert settings.API_KEY is None

    def test_insecure_no_auth_defaults_to_false(self):
        """INSECURE_NO_AUTH is False by default — opt-in only."""
        settings = Settings(_env_file=None)
        assert settings.INSECURE_NO_AUTH is False

    def test_api_key_is_secret_str_when_set(self):
        """API_KEY wraps the token in SecretStr so logs/tracebacks redact it."""
        settings = Settings(_env_file=None, API_KEY="hunter2")
        assert isinstance(settings.API_KEY, SecretStr)
        assert settings.API_KEY.get_secret_value() == "hunter2"
        # repr() must NOT expose the secret value
        assert "hunter2" not in repr(settings.API_KEY)

    def test_insecure_no_auth_accepts_true(self):
        """INSECURE_NO_AUTH can be flipped on."""
        settings = Settings(_env_file=None, INSECURE_NO_AUTH=True)
        assert settings.INSECURE_NO_AUTH is True

    def test_agent_brain_api_key_still_exists_for_v1_compat(self):
        """AGENT_BRAIN_API_KEY field is preserved in 199-01 — 199-02 will remove."""
        settings = Settings(_env_file=None)
        assert settings.AGENT_BRAIN_API_KEY == ""

    def test_v1_and_v2_fields_are_independent_in_199_01(self):
        """Setting one does not affect the other (alias migration is 199-02 work)."""
        settings = Settings(
            _env_file=None,
            AGENT_BRAIN_API_KEY="v1-key",
            API_KEY="v2-key",
        )
        assert settings.AGENT_BRAIN_API_KEY == "v1-key"
        assert settings.API_KEY is not None
        assert settings.API_KEY.get_secret_value() == "v2-key"
