# ADR-007: Plugin Sandbox Security

## Status

**Accepted** (Phase 5, Point 16)

## Context

Kira supports plugins for extensibility. Without sandboxing:

- **Security risk**: Plugins can access arbitrary files
- **Network abuse**: Plugins can make unlimited network calls
- **Resource exhaustion**: Runaway plugins consume CPU/memory
- **Data leaks**: Plugins can read sensitive data
- **Denial of service**: Malicious plugins crash the system

**Requirement**: Secure plugin execution with minimal privileges.

## Decision

### Sandbox Architecture

```
┌──────────────┐
│   Plugin     │  ← Untrusted code
└──────┬───────┘
       │ IPC (stdin/stdout)
       ▼
┌──────────────┐
│   Sandbox    │  ← Isolation layer
│  (subprocess)│
└──────┬───────┘
       │ Capability API
       ▼
┌──────────────┐
│  HostAPI     │  ← Trusted gateway
│  (Vault)     │
└──────────────┘
```

**Isolation Mechanisms:**

1. **Process isolation**: Run as subprocess
2. **No network**: No network access by default
3. **Resource limits**: CPU/memory/time caps
4. **Capability-based**: Explicit permissions only
5. **Constrained venv**: Minimal Python environment

### Capability API

Plugins declare required capabilities:

```python
# plugin_manifest.yaml
name: my-plugin
version: 1.0.0
capabilities:
  - vault.read:task/*      # Read tasks
  - vault.write:note/*     # Write notes
  # NO network, NO filesystem
```

**Available Capabilities:**
- `vault.read:<pattern>`: Read entities matching pattern
- `vault.write:<pattern>`: Write entities matching pattern
- `network.http`: Make HTTP requests (explicit opt-in)

**Denied by Default:**
- Arbitrary file access
- Network access
- System calls

### Resource Limits

```python
# Linux: resource module
resource.setrlimit(resource.RLIMIT_CPU, (30, 30))        # 30s CPU
resource.setrlimit(resource.RLIMIT_AS, (256*MB, 256*MB)) # 256MB RAM

# Timeout
signal.alarm(60)  # 60s wall-clock time
```

### Plugin Execution

```python
def run_plugin(plugin_path: Path, capabilities: list[str]) -> dict:
    """Run plugin in sandbox."""
    
    # Validate capabilities
    validate_capabilities(capabilities)
    
    # Create isolated subprocess
    env = {
        "PYTHONPATH": str(plugin_venv),
        "KIRA_CAPABILITIES": json.dumps(capabilities),
    }
    
    proc = subprocess.Popen(
        [python_exe, plugin_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    
    # Set resource limits (if Linux)
    if hasattr(resource, 'prlimit'):
        resource.prlimit(proc.pid, resource.RLIMIT_CPU, (30, 30))
        resource.prlimit(proc.pid, resource.RLIMIT_AS, (256*MB, 256*MB))
    
    # Run with timeout
    try:
        stdout, stderr = proc.communicate(input=input_data, timeout=60)
    except subprocess.TimeoutExpired:
        proc.kill()
        raise PluginTimeoutError()
    
    return parse_plugin_output(stdout)
```

## Consequences

### Positive

- **Security**: Plugins can't access arbitrary resources
- **Stability**: Resource limits prevent system crashes
- **Auditability**: Capability declarations are explicit
- **Isolation**: Plugin crashes don't affect main process

### Negative

- **Performance**: Subprocess overhead
- **Complexity**: Capability validation and enforcement
- **Platform-specific**: Resource limits vary by OS
- **Developer friction**: Plugins must declare capabilities

### Security Boundaries

```
                 ┌─────────────────┐
                 │  High Trust     │
                 │  (Core Kira)    │
                 └────────┬────────┘
                          │
            Capability API│
                          │
                 ┌────────▼────────┐
                 │  Low Trust      │
                 │  (Plugins)      │
                 │  - No network   │
                 │  - No FS access │
                 │  - Limited CPU  │
                 └─────────────────┘
```

## Implementation

### Sandbox Runner

```python
# src/kira/plugins/sandbox.py

class PluginSandbox:
    def __init__(self, plugin_dir: Path, config: SandboxConfig):
        self.plugin_dir = plugin_dir
        self.config = config
    
    def run(self, plugin_name: str, input_data: dict) -> dict:
        """Run plugin with sandbox constraints."""
        manifest = self.load_manifest(plugin_name)
        
        # Validate capabilities
        for cap in manifest.capabilities:
            if not self.is_valid_capability(cap):
                raise InvalidCapabilityError(cap)
        
        # Execute in subprocess
        return self._execute_subprocess(
            plugin_path=self.plugin_dir / plugin_name / "main.py",
            capabilities=manifest.capabilities,
            input_data=input_data,
        )
```

### Capability Check

```python
def check_capability(required: str, granted: list[str]) -> bool:
    """Check if required capability is granted."""
    for cap in granted:
        if capability_matches(required, cap):
            return True
    return False

def capability_matches(required: str, granted: str) -> bool:
    """Check if capability pattern matches.
    
    Examples:
        vault.read:task/* matches vault.read:task/123
        vault.write:* matches vault.write:note/456
    """
    # Parse patterns and match
    ...
```

## Verification

### DoD Check

```python
def test_plugin_cannot_access_arbitrary_files():
    """Test DoD: Plugin without capability can't access files."""
    plugin = create_plugin("""
        # Try to read /etc/passwd
        with open('/etc/passwd') as f:
            print(f.read())
    """)
    
    with pytest.raises(PluginSecurityError):
        sandbox.run(plugin, capabilities=[])

def test_plugin_cannot_make_network_calls():
    """Test DoD: Plugin without network capability can't make HTTP calls."""
    plugin = create_plugin("""
        import urllib.request
        urllib.request.urlopen('https://example.com')
    """)
    
    with pytest.raises(PluginSecurityError):
        sandbox.run(plugin, capabilities=[])
```

### Tests

- `tests/unit/test_plugin_sandbox.py`: Sandbox logic (20 tests)

## References

- Implementation: `src/kira/plugins/sandbox.py`
- Manifest schema: `plugin_manifest.yaml`
- Related: ADR-001 (Single Writer)
