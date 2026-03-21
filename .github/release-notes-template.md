## Install

### Homebrew (recommended)
```bash
brew tap razvanbalsan/h9s https://github.com/razvanbalsan/h9s
brew install h9s
```

### curl one-liner (macOS)
```bash
curl -fsSL https://raw.githubusercontent.com/razvanbalsan/h9s/main/install.sh | bash
```

### Direct binary download (macOS)

**Apple Silicon (M1/M2/M3)**
```bash
curl -L https://github.com/razvanbalsan/h9s/releases/latest/download/h9s-macos-arm64 \
  -o /usr/local/bin/h9s && chmod +x /usr/local/bin/h9s
```

**Intel Mac**
```bash
curl -L https://github.com/razvanbalsan/h9s/releases/latest/download/h9s-macos-x86_64 \
  -o /usr/local/bin/h9s && chmod +x /usr/local/bin/h9s
```

### pipx
```bash
pipx install git+https://github.com/razvanbalsan/h9s.git
```

## Requirements

- **helm** v3 on PATH (`brew install helm`)
- **kubectl** recommended (`brew install kubectl`)

## SHA256 Checksums

See `checksums.txt` attached to this release.
