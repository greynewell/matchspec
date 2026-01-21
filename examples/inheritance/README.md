# Configuration Inheritance Examples

This directory contains examples of using the configuration inheritance feature in mcpbr.

## Basic Inheritance

The simplest form of inheritance uses the `extends` field to inherit from a base configuration:

```yaml
# dev-config.yaml
extends: ./base-config.yaml

model: "haiku"
sample_size: 1
```

## How It Works

1. **Base Configuration**: Define common settings in a base config file
2. **Derived Configurations**: Create specific configs that extend the base
3. **Deep Merging**: Nested dictionaries are merged recursively
4. **Override**: Values in the derived config override those in the base

## Examples in This Directory

### base-config.yaml
The foundation configuration with common settings:
- MCP server configuration
- Provider and harness settings
- Default resource limits

### dev-config.yaml
Development environment configuration:
- Extends base-config.yaml
- Uses faster model (haiku)
- Small sample size for quick testing
- Lower concurrency and timeout

### production-config.yaml
Production environment configuration:
- Extends base-config.yaml
- Uses most capable model (opus)
- Full dataset evaluation
- Higher concurrency and timeout
- Budget limits

### Multiple Inheritance

You can extend from multiple configuration files:

```yaml
# multi-extend-config.yaml
extends:
  - ./base-config.yaml
  - ./shared-mcp-settings.yaml

model: "sonnet"
```

Later configurations in the list take precedence over earlier ones.

## Multi-Level Inheritance

Configurations can form inheritance chains:

```
base-config.yaml
  ↓
staging-config.yaml (extends base)
  ↓
dev-config.yaml (extends staging)
```

## Path Resolution

### Relative Paths
Relative paths are resolved relative to the config file containing the `extends` field:

```yaml
extends: ./base.yaml        # Same directory
extends: ../base.yaml       # Parent directory
extends: configs/base.yaml  # Subdirectory
```

### Absolute Paths
Absolute paths work as expected:

```yaml
extends: /etc/mcpbr/base.yaml
```

### Remote Configs (URLs)
You can extend from remote configuration files:

```yaml
extends: https://example.com/configs/base.yaml
```

**Note**: Remote configs cannot themselves use `extends` for security reasons.

## Deep Merge Behavior

Nested dictionaries are merged recursively:

```yaml
# base.yaml
mcp_server:
  command: npx
  env:
    BASE_VAR: "base"

# derived.yaml
extends: ./base.yaml

mcp_server:
  env:
    DERIVED_VAR: "derived"

# Result:
# mcp_server:
#   command: npx
#   env:
#     BASE_VAR: "base"
#     DERIVED_VAR: "derived"
```

**Lists are replaced, not merged**:

```yaml
# base.yaml
mcp_server:
  args: ["a", "b", "c"]

# derived.yaml
extends: ./base.yaml

mcp_server:
  args: ["x", "y"]

# Result: args will be ["x", "y"], not ["a", "b", "c", "x", "y"]
```

## Environment Variables

Inheritance works seamlessly with environment variable expansion:

```yaml
# base.yaml
mcp_server:
  env:
    API_KEY: "${API_KEY}"

# dev.yaml
extends: ./base.yaml

mcp_server:
  env:
    DEBUG: "${DEBUG:-true}"
```

## Circular Dependency Detection

mcpbr automatically detects and prevents circular inheritance:

```yaml
# a.yaml
extends: ./b.yaml

# b.yaml
extends: ./a.yaml

# Error: Circular inheritance detected!
```

## Best Practices

1. **Base Configuration**: Create a base config with common settings
2. **Environment-Specific**: Create separate configs for dev, staging, production
3. **Keep It DRY**: Use inheritance to avoid duplicating common settings
4. **Use Relative Paths**: Makes configs portable across different machines
5. **Document Overrides**: Comment why specific settings are overridden

## Running with Inherited Configs

Simply use the derived configuration file:

```bash
mcpbr run --config dev-config.yaml
mcpbr run --config production-config.yaml
```

The inheritance is handled automatically - you don't need to specify the base configuration.
