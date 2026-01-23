#!/usr/bin/env python3
"""Test case to reproduce the string concatenation TypeError."""

import sys


def test_instance_id_construction():
    """Test the pattern used in harness.py line 312."""

    # Normal case: all strings
    task1 = {"project": "django", "bug_id": "12345"}
    instance_id1 = task1.get(
        "instance_id", f"{task1.get('project', 'unknown')}_{task1.get('bug_id', 'unknown')}"
    )
    print(f"✓ Case 1 (all strings): {instance_id1}")

    # Bug case: bug_id is an integer
    task2 = {
        "project": "django",
        "bug_id": 12345,  # Integer!
    }
    try:
        instance_id2 = task2.get(
            "instance_id", f"{task2.get('project', 'unknown')}_{task2.get('bug_id', 'unknown')}"
        )
        print(f"✓ Case 2 (bug_id as int): {instance_id2}")
    except TypeError as e:
        print(f"✗ Case 2 failed: {e}")
        return False

    # Bug case: instance_id is constructed elsewhere with string concatenation
    # Simulate what might happen in task preprocessing
    task3 = {"project": "django", "bug_id": 12345}
    try:
        # This is the problematic pattern - explicit string concatenation
        task3["instance_id"] = task3["project"] + "_" + task3["bug_id"]
        print("✗ Case 3 should fail with TypeError")
    except TypeError as e:
        print(f"✓ Case 3 correctly fails: {e}")
        # This is the bug!
        return True

    return False


def test_task_id_suffix():
    """Test the pattern used for task_id construction."""

    # Case where instance_id might be an int
    instance_id = 12345
    try:
        task_id = f"{instance_id}:mcp"
        print(f"✓ F-string handles int task_id: {task_id}")
    except TypeError as e:
        print(f"✗ F-string failed: {e}")
        return False

    # Case where someone uses + instead of f-string
    try:
        _ = str(instance_id) + ":mcp"  # This works
        _ = instance_id + ":mcp"  # This fails!
        print("✗ Should have failed")
    except TypeError as e:
        print(f"✓ Correctly fails on int + str: {e}")
        return True

    return False


if __name__ == "__main__":
    print("Testing string concatenation patterns...")
    print("=" * 60)

    test1_passed = test_instance_id_construction()
    print()
    test2_passed = test_task_id_suffix()

    print("=" * 60)
    if test1_passed or test2_passed:
        print("✓ Bug reproduced! String + int concatenation causes TypeError")
        sys.exit(0)
    else:
        print("✗ Could not reproduce the bug")
        sys.exit(1)
