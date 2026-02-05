# Homebrew Formula for mcpbr

Install mcpbr via Homebrew on macOS and Linux.

## Installation

### From the tap (recommended)

```bash
brew tap greynewell/mcpbr
brew install mcpbr
```

### From the formula directly

```bash
brew install --formula Formula/mcpbr.rb
```

## Updating the Formula

When releasing a new version:

1. Update the `url` in `Formula/mcpbr.rb` to point to the new release tarball
2. Update the `sha256` hash:
   ```bash
   curl -sL https://files.pythonhosted.org/packages/source/m/mcpbr/mcpbr-VERSION.tar.gz | shasum -a 256
   ```
3. Update resource hashes for any changed dependencies
4. Test the formula:
   ```bash
   brew install --build-from-source Formula/mcpbr.rb
   brew test mcpbr
   ```

## Notes

- The formula uses `PLACEHOLDER_SHA256` for hashes that need to be computed from actual release artifacts
- Resource blocks list the minimum required dependencies; transitive dependencies are resolved by pip within the virtualenv
