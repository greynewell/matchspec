"""Output file validation utilities."""

import json
from pathlib import Path

import yaml


def validate_output_file(output_path: Path) -> tuple[bool, str]:
    """Validate output file was created and is valid JSON or YAML.

    Args:
        output_path: Path to the output file to validate.

    Returns:
        Tuple of (is_valid, message) where message describes the validation result.
    """
    # Check file exists
    if not output_path.exists():
        return False, f"Output file not created: {output_path}"

    # Check file is not empty
    if output_path.stat().st_size == 0:
        return False, f"Output file is empty: {output_path}"

    # Determine file type by extension
    file_ext = output_path.suffix.lower()

    # Validate structure based on file type
    try:
        with open(output_path) as f:
            if file_ext in (".yaml", ".yml"):
                data = yaml.safe_load(f)
                file_type = "YAML"
            else:
                # Default to JSON
                data = json.load(f)
                file_type = "JSON"

        # Validate required structure
        if not isinstance(data, dict):
            return False, f"Output must be a {file_type} object"

        if "tasks" not in data:
            return False, "Output missing 'tasks' field"

        if not isinstance(data["tasks"], list):
            return False, "'tasks' field must be a list"

        task_count = len(data["tasks"])
        return True, f"Valid {file_type} with {task_count} task(s)"

    except json.JSONDecodeError as e:
        return False, f"Invalid JSON: {e}"
    except yaml.YAMLError as e:
        return False, f"Invalid YAML: {e}"
    except Exception as e:
        return False, f"Validation error: {e}"
