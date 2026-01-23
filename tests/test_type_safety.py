"""Tests for type safety in task field handling."""


class TestTaskFieldTypes:
    """Test that task fields with unexpected types don't cause TypeErrors."""

    def test_instance_id_with_integer_fields(self):
        """Test instance_id construction when project/bug_id are integers."""
        # This simulates what happens in harness.py lines 312 and 410
        task = {
            "project": "django",
            "bug_id": 12345,  # Integer instead of string
        }

        # Current code uses f-strings which handle this correctly
        instance_id = task.get(
            "instance_id", f"{task.get('project', 'unknown')}_{task.get('bug_id', 'unknown')}"
        )

        assert instance_id == "django_12345"

    def test_instance_id_all_strings(self):
        """Test instance_id construction with all string fields."""
        task = {
            "project": "django",
            "bug_id": "12345",
        }

        instance_id = task.get(
            "instance_id", f"{task.get('project', 'unknown')}_{task.get('bug_id', 'unknown')}"
        )

        assert instance_id == "django_12345"

    def test_instance_id_already_present(self):
        """Test when instance_id is already in task."""
        task = {
            "instance_id": "django__django-12345",
            "project": "django",
            "bug_id": 12345,
        }

        instance_id = task.get(
            "instance_id", f"{task.get('project', 'unknown')}_{task.get('bug_id', 'unknown')}"
        )

        assert instance_id == "django__django-12345"

    def test_task_id_suffix_with_string(self):
        """Test adding suffix to task_id when it's a string."""
        instance_id = "django-12345"
        task_id = f"{instance_id}:mcp"

        assert task_id == "django-12345:mcp"

    def test_task_id_suffix_with_integer(self):
        """Test adding suffix to task_id when it might be an integer."""
        # If instance_id somehow becomes an integer, f-strings handle it
        instance_id = 12345
        task_id = f"{instance_id}:mcp"

        assert task_id == "12345:mcp"

    def test_none_values_in_task(self):
        """Test when task fields are None."""
        task = {
            "project": None,
            "bug_id": None,
        }

        instance_id = task.get(
            "instance_id", f"{task.get('project', 'unknown')}_{task.get('bug_id', 'unknown')}"
        )

        assert instance_id == "None_None"  # f-strings convert None to "None"
