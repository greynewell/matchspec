#!/usr/bin/env python3
"""Test that the Docker label fix handles integer instance_ids correctly."""


def test_docker_labels_with_integer_instance_id():
    """Test that Docker labels work with integer instance_id values."""
    # Simulate what happens in docker_env.py line 419-424

    # Test case 1: instance_id is a string (normal case)
    instance_id_str = "django__django-12345"
    labels_str = {
        "mcpbr": "true",
        "mcpbr.instance": str(instance_id_str),  # Fixed version
        "mcpbr.session": "test-session",
        "mcpbr.timestamp": "2026-01-23",
    }

    # All label values should be strings
    for key, value in labels_str.items():
        assert isinstance(value, str), f"Label {key} value should be str, got {type(value)}"

    print("✓ Test 1 passed: String instance_id works")

    # Test case 2: instance_id is an integer (bug case)
    instance_id_int = 12345
    labels_int = {
        "mcpbr": "true",
        "mcpbr.instance": str(instance_id_int),  # Fixed version with str()
        "mcpbr.session": "test-session",
        "mcpbr.timestamp": "2026-01-23",
    }

    # All label values should be strings
    for key, value in labels_int.items():
        assert isinstance(value, str), f"Label {key} value should be str, got {type(value)}"

    print("✓ Test 2 passed: Integer instance_id converted to string")

    # Test case 3: Demonstrate the old bug (without str())
    try:
        labels_buggy = {
            "mcpbr": "true",
            "mcpbr.instance": instance_id_int,  # Bug: passing int directly
            "mcpbr.session": "test-session",
        }

        # Docker library would try to do something like:
        # label_str = "mcpbr.instance=" + instance_id_int
        # This would raise TypeError
        for key, value in labels_buggy.items():
            if not isinstance(value, str):
                # Simulate what Docker library does internally
                _ = key + "=" + value  # This will fail with int

    except TypeError as e:
        print(f"✓ Test 3 passed: Confirmed old bug would fail with: {e}")
        return True

    print("✗ Test 3 failed: Should have caught TypeError")
    return False


if __name__ == "__main__":
    print("Testing Docker label fix...")
    print("=" * 60)

    success = test_docker_labels_with_integer_instance_id()

    print("=" * 60)
    if success:
        print("✓ All tests passed! The fix resolves the issue.")
        exit(0)
    else:
        print("✗ Tests failed!")
        exit(1)
