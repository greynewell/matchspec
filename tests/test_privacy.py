"""Tests for privacy controls module."""

from datetime import datetime, timedelta, timezone

from mcpbr.privacy import (
    DataRetentionPolicy,
    PiiRedactor,
    PrivacyConfig,
    RedactionLevel,
    apply_privacy_controls,
)


class TestRedactionLevel:
    """Tests for RedactionLevel enum."""

    def test_none_value(self) -> None:
        """Test NONE redaction level value."""
        assert RedactionLevel.NONE.value == "none"

    def test_basic_value(self) -> None:
        """Test BASIC redaction level value."""
        assert RedactionLevel.BASIC.value == "basic"

    def test_strict_value(self) -> None:
        """Test STRICT redaction level value."""
        assert RedactionLevel.STRICT.value == "strict"


class TestPrivacyConfig:
    """Tests for PrivacyConfig dataclass."""

    def test_defaults(self) -> None:
        """Test that PrivacyConfig has sensible defaults."""
        config = PrivacyConfig()
        assert config.redaction_level == RedactionLevel.BASIC
        assert config.custom_patterns == []
        assert config.exclude_fields == []
        assert config.data_retention_days is None
        assert config.anonymize_task_ids is False
        assert config.opt_out_analytics is False

    def test_custom_values(self) -> None:
        """Test PrivacyConfig with custom values."""
        config = PrivacyConfig(
            redaction_level=RedactionLevel.STRICT,
            custom_patterns=[r"\bSECRET\b"],
            exclude_fields=["internal_id"],
            data_retention_days=90,
            anonymize_task_ids=True,
            opt_out_analytics=True,
        )
        assert config.redaction_level == RedactionLevel.STRICT
        assert config.custom_patterns == [r"\bSECRET\b"]
        assert config.exclude_fields == ["internal_id"]
        assert config.data_retention_days == 90
        assert config.anonymize_task_ids is True
        assert config.opt_out_analytics is True

    def test_custom_patterns_list_is_independent(self) -> None:
        """Test that default custom_patterns lists are independent across instances."""
        config1 = PrivacyConfig()
        config2 = PrivacyConfig()
        config1.custom_patterns.append("test")
        assert config2.custom_patterns == []


class TestPiiRedactor:
    """Tests for PiiRedactor class."""

    def test_redact_email(self) -> None:
        """Test that email addresses are redacted at BASIC level."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        result = redactor.redact("Contact admin@example.com")
        assert result == "Contact [REDACTED]"

    def test_redact_api_key(self) -> None:
        """Test that API keys are redacted at BASIC level."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        result = redactor.redact("key sk_abc123def456789012345678")
        assert "[REDACTED]" in result
        assert "sk_abc123def456789012345678" not in result

    def test_redact_ipv4(self) -> None:
        """Test that IPv4 addresses are redacted at BASIC level."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        result = redactor.redact("Server at 192.168.1.1")
        assert result == "Server at [REDACTED]"

    def test_no_redaction_when_none_level(self) -> None:
        """Test that no redaction occurs when level is NONE."""
        config = PrivacyConfig(redaction_level=RedactionLevel.NONE)
        redactor = PiiRedactor(config)
        text = "Contact admin@example.com at 192.168.1.1"
        result = redactor.redact(text)
        assert result == text

    def test_redact_ssn_strict_only(self) -> None:
        """Test that SSNs are NOT redacted at BASIC but ARE at STRICT."""
        text = "SSN is 123-45-6789"

        basic_config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        basic_redactor = PiiRedactor(basic_config)
        assert "123-45-6789" in basic_redactor.redact(text)

        strict_config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        strict_redactor = PiiRedactor(strict_config)
        assert "123-45-6789" not in strict_redactor.redact(text)
        assert "[REDACTED]" in strict_redactor.redact(text)

    def test_redact_phone_strict_only(self) -> None:
        """Test that phone numbers are NOT redacted at BASIC but ARE at STRICT."""
        text = "Call me at (555) 123-4567"

        basic_config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        basic_redactor = PiiRedactor(basic_config)
        assert "(555) 123-4567" in basic_redactor.redact(text)

        strict_config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        strict_redactor = PiiRedactor(strict_config)
        result = strict_redactor.redact(text)
        assert "[REDACTED]" in result

    def test_redact_credit_card_strict_only(self) -> None:
        """Test that credit card numbers are NOT redacted at BASIC but ARE at STRICT."""
        text = "Card: 4111-1111-1111-1111"

        basic_config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        basic_redactor = PiiRedactor(basic_config)
        assert "4111-1111-1111-1111" in basic_redactor.redact(text)

        strict_config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        strict_redactor = PiiRedactor(strict_config)
        result = strict_redactor.redact(text)
        assert "4111-1111-1111-1111" not in result
        assert "[REDACTED]" in result

    def test_custom_pattern(self) -> None:
        """Test that custom patterns are applied at STRICT level."""
        config = PrivacyConfig(
            redaction_level=RedactionLevel.STRICT,
            custom_patterns=[r"\bCONFIDENTIAL\b"],
        )
        redactor = PiiRedactor(config)
        result = redactor.redact("This is CONFIDENTIAL data")
        assert "CONFIDENTIAL" not in result
        assert "[REDACTED]" in result

    def test_redact_dict_basic(self) -> None:
        """Test that dict string values are redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        data = {"name": "Alice", "email": "alice@example.com"}
        result = redactor.redact_dict(data)
        assert result["name"] == "Alice"
        assert result["email"] == "[REDACTED]"

    def test_redact_dict_excludes_fields(self) -> None:
        """Test that exclude_fields removes keys from the output dict."""
        config = PrivacyConfig(
            redaction_level=RedactionLevel.BASIC,
            exclude_fields=["secret_field"],
        )
        redactor = PiiRedactor(config)
        data = {"public": "hello", "secret_field": "sensitive_value"}
        result = redactor.redact_dict(data)
        assert "public" in result
        assert "secret_field" not in result

    def test_redact_dict_nested(self) -> None:
        """Test that deeply nested dicts are redacted recursively."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        data = {
            "level1": {
                "level2": {
                    "contact": "nested@example.com",
                }
            }
        }
        result = redactor.redact_dict(data)
        assert result["level1"]["level2"]["contact"] == "[REDACTED]"

    def test_redact_dict_with_list_values(self) -> None:
        """Test that lists of strings within dicts are redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        data = {
            "emails": ["user1@example.com", "user2@example.com"],
            "count": 2,
        }
        result = redactor.redact_dict(data)
        assert result["emails"] == ["[REDACTED]", "[REDACTED]"]
        assert result["count"] == 2

    def test_redact_dict_preserves_non_string_values(self) -> None:
        """Test that non-string values like ints and bools pass through unchanged."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        data = {"count": 42, "active": True, "ratio": 3.14}
        result = redactor.redact_dict(data)
        assert result["count"] == 42
        assert result["active"] is True
        assert result["ratio"] == 3.14

    def test_anonymize_id_enabled(self) -> None:
        """Test that anonymize_id returns a hash prefix when enabled."""
        config = PrivacyConfig(anonymize_task_ids=True)
        redactor = PiiRedactor(config)
        result = redactor.anonymize_id("my-task-id")
        assert result != "my-task-id"
        assert len(result) == 12

    def test_anonymize_id_disabled(self) -> None:
        """Test that anonymize_id returns the original when disabled."""
        config = PrivacyConfig(anonymize_task_ids=False)
        redactor = PiiRedactor(config)
        result = redactor.anonymize_id("my-task-id")
        assert result == "my-task-id"

    def test_anonymize_id_consistent(self) -> None:
        """Test that the same input always produces the same anonymized output."""
        config = PrivacyConfig(anonymize_task_ids=True)
        redactor = PiiRedactor(config)
        result1 = redactor.anonymize_id("consistent-id")
        result2 = redactor.anonymize_id("consistent-id")
        assert result1 == result2

    def test_anonymize_id_different_inputs_differ(self) -> None:
        """Test that different inputs produce different anonymized outputs."""
        config = PrivacyConfig(anonymize_task_ids=True)
        redactor = PiiRedactor(config)
        result1 = redactor.anonymize_id("task-a")
        result2 = redactor.anonymize_id("task-b")
        assert result1 != result2

    def test_custom_replacement(self) -> None:
        """Test that a custom replacement string is used instead of [REDACTED]."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        result = redactor.redact("Contact admin@example.com", replacement="[***]")
        assert result == "Contact [***]"
        assert "[REDACTED]" not in result

    def test_custom_replacement_in_dict(self) -> None:
        """Test that custom replacement works in redact_dict."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        data = {"email": "test@example.com"}
        result = redactor.redact_dict(data, replacement="[***]")
        assert result["email"] == "[***]"

    def test_redact_multiple_emails_in_one_string(self) -> None:
        """Test that multiple PII instances in one string are all redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        text = "From a@b.com to c@d.com"
        result = redactor.redact(text)
        assert "a@b.com" not in result
        assert "c@d.com" not in result

    def test_redact_empty_string(self) -> None:
        """Test that redacting an empty string returns an empty string."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        assert redactor.redact("") == ""

    def test_redact_dict_empty(self) -> None:
        """Test that redacting an empty dict returns an empty dict."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        assert redactor.redact_dict({}) == {}


class TestDataRetentionPolicy:
    """Tests for DataRetentionPolicy class."""

    def test_no_retention(self) -> None:
        """Test that with retention_days=None, nothing expires."""
        policy = DataRetentionPolicy(retention_days=None)
        old_timestamp = "2020-01-01T00:00:00+00:00"
        assert policy.is_expired(old_timestamp) is False

    def test_recent_not_expired(self) -> None:
        """Test that a timestamp from 1 day ago is not expired with 30-day retention."""
        policy = DataRetentionPolicy(retention_days=30)
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        assert policy.is_expired(recent) is False

    def test_old_is_expired(self) -> None:
        """Test that a timestamp from 60 days ago is expired with 30-day retention."""
        policy = DataRetentionPolicy(retention_days=30)
        old = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
        assert policy.is_expired(old) is True

    def test_get_expiry_date_with_retention(self) -> None:
        """Test that get_expiry_date returns a date string when retention is set."""
        policy = DataRetentionPolicy(retention_days=30)
        expiry = policy.get_expiry_date()
        assert expiry is not None
        # The expiry date should be parseable as ISO 8601
        parsed = datetime.fromisoformat(expiry)
        assert parsed.tzinfo is not None

    def test_get_expiry_date_without_retention(self) -> None:
        """Test that get_expiry_date returns None when no retention is configured."""
        policy = DataRetentionPolicy(retention_days=None)
        assert policy.get_expiry_date() is None

    def test_exactly_at_boundary_is_not_expired(self) -> None:
        """Test that a timestamp exactly at the retention boundary is not expired."""
        policy = DataRetentionPolicy(retention_days=30)
        # Use a timestamp just barely within the retention window
        just_within = (datetime.now(timezone.utc) - timedelta(days=29, hours=23)).isoformat()
        assert policy.is_expired(just_within) is False

    def test_naive_timestamp_treated_as_utc(self) -> None:
        """Test that a naive timestamp (no timezone) is treated as UTC."""
        policy = DataRetentionPolicy(retention_days=30)
        # Create a naive ISO timestamp from 60 days ago
        old_naive = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m-%dT%H:%M:%S")
        assert policy.is_expired(old_naive) is True


class TestApplyPrivacyControls:
    """Tests for apply_privacy_controls convenience function."""

    def test_applies_redaction(self) -> None:
        """Test that apply_privacy_controls redacts PII from dict values."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        data = {"contact": "admin@example.com", "status": "ok"}
        result = apply_privacy_controls(data, config)
        assert result["contact"] == "[REDACTED]"
        assert result["status"] == "ok"

    def test_applies_field_exclusion(self) -> None:
        """Test that apply_privacy_controls removes excluded fields."""
        config = PrivacyConfig(
            redaction_level=RedactionLevel.BASIC,
            exclude_fields=["internal"],
        )
        data = {"public": "hello", "internal": "secret"}
        result = apply_privacy_controls(data, config)
        assert "public" in result
        assert "internal" not in result

    def test_applies_both_redaction_and_exclusion(self) -> None:
        """Test that both redaction and field exclusion work together."""
        config = PrivacyConfig(
            redaction_level=RedactionLevel.BASIC,
            exclude_fields=["debug_info"],
        )
        data = {
            "email": "user@example.com",
            "name": "Alice",
            "debug_info": "internal data",
        }
        result = apply_privacy_controls(data, config)
        assert result["email"] == "[REDACTED]"
        assert result["name"] == "Alice"
        assert "debug_info" not in result

    def test_no_redaction_no_exclusion(self) -> None:
        """Test that NONE level with no excluded fields returns data unchanged."""
        config = PrivacyConfig(redaction_level=RedactionLevel.NONE)
        data = {"email": "user@example.com", "ip": "10.0.0.1"}
        result = apply_privacy_controls(data, config)
        assert result == data

    def test_does_not_mutate_original(self) -> None:
        """Test that apply_privacy_controls returns a new dict without mutating input."""
        config = PrivacyConfig(
            redaction_level=RedactionLevel.BASIC,
            exclude_fields=["secret"],
        )
        data = {"email": "user@example.com", "secret": "hidden"}
        original_data = dict(data)
        apply_privacy_controls(data, config)
        assert data == original_data


class TestPiiPatternCoverageGaps:
    """Tests for PII pattern coverage gaps identified in issue #431."""

    def test_ssn_without_dashes_strict(self) -> None:
        """Test that SSNs without dashes (e.g., 123456789) are redacted in STRICT mode."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("SSN is 123456789 on file")
        assert "123456789" not in result
        assert "[REDACTED]" in result

    def test_abbreviated_ipv6_loopback_strict(self) -> None:
        """Test that abbreviated IPv6 loopback ::1 is redacted in STRICT mode."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("Listening on ::1 port 8080")
        assert "::1" not in result

    def test_abbreviated_ipv6_link_local_strict(self) -> None:
        """Test that abbreviated IPv6 like fe80::1 is redacted in STRICT mode."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("Interface at fe80::1")
        assert "fe80::1" not in result

    def test_abbreviated_ipv6_prefix_strict(self) -> None:
        """Test that abbreviated IPv6 like 2001:db8::1 is redacted in STRICT mode."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("Route via 2001:db8::1")
        assert "2001:db8::1" not in result

    def test_amex_credit_card_strict(self) -> None:
        """Test that American Express card numbers (15 digits) are redacted in STRICT."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("Amex card 378282246310005")
        assert "378282246310005" not in result
        assert "[REDACTED]" in result

    def test_amex_credit_card_with_separators_strict(self) -> None:
        """Test that Amex cards with spaces (3782 822463 10005) are redacted in STRICT."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("Amex card 3782 822463 10005")
        assert "3782 822463 10005" not in result
        assert "[REDACTED]" in result

    def test_international_phone_number_strict(self) -> None:
        """Test that international phone numbers (e.g., +44 20 7946 0958) are redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("Call +44 20 7946 0958")
        assert "+44 20 7946 0958" not in result
        assert "[REDACTED]" in result

    def test_phone_number_with_country_code_strict(self) -> None:
        """Test that phone numbers with + country code prefix are redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("Reach me at +61 2 9876 5432")
        assert "+61 2 9876 5432" not in result

    def test_multiple_pii_types_in_one_string(self) -> None:
        """Test that multiple different PII types in one string are all redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        text = "Email: user@test.com, SSN: 123-45-6789, Phone: (555) 123-4567"
        result = redactor.redact(text)
        assert "user@test.com" not in result
        assert "123-45-6789" not in result
        assert "(555) 123-4567" not in result

    def test_pii_in_json_like_string(self) -> None:
        """Test that PII embedded in JSON-like strings is redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        text = '{"email": "admin@corp.com", "ip": "10.0.0.1"}'
        result = redactor.redact(text)
        assert "admin@corp.com" not in result
        assert "10.0.0.1" not in result

    def test_redacted_output_no_pii_leak(self) -> None:
        """Verify that the redacted output contains zero original PII tokens."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        pii_values = [
            "leaked@email.org",
            "192.168.100.200",
            "4111-1111-1111-1111",
            "123-45-6789",
            "(555) 987-6543",
        ]
        text = " | ".join(pii_values)
        result = redactor.redact(text)
        for pii in pii_values:
            assert pii not in result, f"PII '{pii}' leaked through redaction"

    def test_nested_list_of_dicts_with_pii(self) -> None:
        """Test that lists of dicts containing PII are fully redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        data = {
            "records": [
                {"email": "a@b.com", "id": 1},
                {"email": "c@d.com", "id": 2},
            ]
        }
        result = redactor.redact_dict(data)
        assert result["records"][0]["email"] == "[REDACTED]"
        assert result["records"][1]["email"] == "[REDACTED]"
        assert result["records"][0]["id"] == 1
        assert result["records"][1]["id"] == 2

    def test_deeply_nested_list_and_dict_mix(self) -> None:
        """Test redaction in deeply nested structures mixing lists and dicts."""
        config = PrivacyConfig(redaction_level=RedactionLevel.BASIC)
        redactor = PiiRedactor(config)
        data = {"outer": [{"inner": [{"contact": "deep@nested.com"}]}]}
        result = redactor.redact_dict(data)
        assert result["outer"][0]["inner"][0]["contact"] == "[REDACTED]"

    def test_credit_card_no_separators_strict(self) -> None:
        """Test that credit card numbers with no separators are redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("Card: 4111111111111111")
        assert "4111111111111111" not in result
        assert "[REDACTED]" in result

    def test_phone_no_separators_strict(self) -> None:
        """Test that phone numbers with no separators (5551234567) are redacted."""
        config = PrivacyConfig(redaction_level=RedactionLevel.STRICT)
        redactor = PiiRedactor(config)
        result = redactor.redact("Phone: 5551234567")
        assert "5551234567" not in result

    def test_exclude_fields_in_nested_dict(self) -> None:
        """Test that exclude_fields works at nested levels."""
        config = PrivacyConfig(
            redaction_level=RedactionLevel.BASIC,
            exclude_fields=["secret"],
        )
        redactor = PiiRedactor(config)
        data = {
            "level1": {
                "public": "visible",
                "secret": "hidden",
            }
        }
        result = redactor.redact_dict(data)
        assert "secret" not in result["level1"]
        assert result["level1"]["public"] == "visible"
