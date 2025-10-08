# Filesystem Adapter

**Watch directories for file changes and auto-import to Kira Vault.**

The Filesystem adapter monitors directories for new markdown files and automatically imports them into the Vault with proper validation and schema normalization.

---

## Status

⚠️ **Under Development**

This adapter is currently a placeholder. Full implementation coming in Phase 7.

---

## Planned Features

- 📂 **Directory Watching** - Monitor folders for file changes
- 📝 **Markdown Import** - Auto-import `.md` files
- ✅ **Schema Validation** - Validate against Vault schemas
- 🔄 **Normalization** - Convert to canonical format
- 📊 **Duplicate Detection** - Skip already-imported files
- 🗂️ **Folder Routing** - Auto-detect entity type from folder
- 🔔 **Event Emission** - Publish `file.dropped` events

---

## Planned Usage

```python
from kira.adapters.filesystem import create_filesystem_adapter
from kira.core.events import create_event_bus
from pathlib import Path

# Create adapter
adapter = create_filesystem_adapter(
    watch_dirs=[
        Path("~/Dropbox/Inbox"),
        Path("~/Documents/Notes")
    ],
    vault_path=Path("vault"),
    event_bus=event_bus,
    auto_import=True,
    validate=True
)

# Start watching (non-blocking)
adapter.start()

# Stop watching
adapter.stop()
```

---

## Planned Configuration

```python
@dataclass
class FilesystemAdapterConfig:
    watch_dirs: list[Path]              # Directories to monitor
    vault_path: Path                     # Vault root directory
    auto_import: bool = True             # Automatically import new files
    validate: bool = True                # Validate against schemas
    move_imported: bool = False          # Move files after import
    imported_dir: Path | None = None     # Where to move imported files
    ignore_patterns: list[str] = [       # Files to ignore
        ".*",           # Hidden files
        "*~",           # Backup files
        "*.tmp"         # Temporary files
    ]
    polling_interval: float = 2.0        # Check interval (seconds)
    debounce_delay: float = 1.0          # Wait before processing (seconds)
```

---

## Planned Workflow

### 1. File Detected

```
~/Dropbox/Inbox/task.md created
↓
Filesystem watcher detects change
↓
Wait debounce_delay (1s)
↓
Check file is stable (size unchanged)
```

### 2. Import Process

```
Read file content
↓
Parse frontmatter
↓
Detect entity type (task/note/event)
↓
Validate against schema
↓
Check for duplicates
↓
Copy to vault/{type}/
↓
Emit file.imported event
↓
(Optional) Move original to imported/
```

### 3. Event Published

```json
{
  "event_type": "file.imported",
  "source": "filesystem",
  "source_path": "/Users/me/Dropbox/Inbox/task.md",
  "entity_id": "task-20251008-1342",
  "entity_type": "task",
  "vault_path": "vault/tasks/task-20251008-1342.md",
  "trace_id": "a1b2c3d4..."
}
```

---

## Planned Architecture

```
External Directory
     ↓
File Watcher (polling/inotify)
     ↓
Debounce & Stabilize
     ↓
Content Parser
     ↓
Schema Validator
     ↓
Duplicate Check
     ↓
┌────────────────┬─────────────────┐
│  Import to     │  Reject         │
│  Vault         │  (quarantine)   │
└────────────────┴─────────────────┘
     ↓                   ↓
Event Bus          Error Log
```

---

## Use Cases

### 1. Dropbox/iCloud Sync

Monitor sync folder for files created on mobile:

```python
adapter = create_filesystem_adapter(
    watch_dirs=[Path("~/Dropbox/Kira Inbox")],
    vault_path=Path("vault"),
    auto_import=True,
    move_imported=True,
    imported_dir=Path("~/Dropbox/Kira Processed")
)
```

**Workflow:**
1. Create file on iPhone: `Dropbox/Kira Inbox/meeting-notes.md`
2. File syncs to desktop
3. Adapter detects file
4. Imports to `vault/notes/`
5. Moves to `Dropbox/Kira Processed/`

---

### 2. Email Attachments

Import markdown files from email client:

```python
adapter = create_filesystem_adapter(
    watch_dirs=[Path("~/Downloads")],
    vault_path=Path("vault"),
    auto_import=True,
    validate=True,
    ignore_patterns=["*.pdf", "*.jpg", "*.png"]  # Only .md files
)
```

---

### 3. Obsidian Integration

Share vault folder with Obsidian:

```python
adapter = create_filesystem_adapter(
    watch_dirs=[Path("~/Obsidian/Kira/Inbox")],
    vault_path=Path("vault"),
    auto_import=False,  # Manual import via CLI
    validate=True
)

# Manual import
adapter.import_file(Path("~/Obsidian/Kira/Inbox/task.md"))
```

---

## Implementation Notes

### File Watching Methods

**Option 1: Polling** (cross-platform)
```python
while running:
    files = scan_directory(watch_dir)
    for file in files:
        if file.mtime > last_check:
            process_file(file)
    time.sleep(polling_interval)
```

**Option 2: OS Events** (efficient)
- **Linux:** `inotify`
- **macOS:** `FSEvents`
- **Windows:** `ReadDirectoryChangesW`

**Library:** Use `watchdog` for cross-platform support.

---

### Duplicate Detection

```python
def is_duplicate(file_path: Path, vault_path: Path) -> bool:
    # Compute content hash
    content = file_path.read_text()
    content_hash = hashlib.sha256(content.encode()).hexdigest()

    # Check if hash exists in vault
    for entity in vault_path.rglob("*.md"):
        if compute_hash(entity) == content_hash:
            return True

    return False
```

---

### Entity Type Detection

```python
def detect_entity_type(content: str) -> str:
    """Detect entity type from frontmatter or content."""
    frontmatter = parse_frontmatter(content)

    # Check frontmatter
    if "kind" in frontmatter:
        return frontmatter["kind"]

    # Heuristics
    if "due" in frontmatter or "status" in frontmatter:
        return "task"
    elif "start" in frontmatter or "end" in frontmatter:
        return "event"
    else:
        return "note"
```

---

## Roadmap

### Phase 7 (Next Release)

- [ ] Basic file watching with polling
- [ ] Markdown file import
- [ ] Schema validation
- [ ] Event emission
- [ ] Duplicate detection

### Phase 8

- [ ] OS-native file watching (inotify/FSEvents)
- [ ] Move/rename detection
- [ ] Bidirectional sync
- [ ] Conflict resolution

### Future

- [ ] OCR support for images
- [ ] PDF text extraction
- [ ] Audio transcription
- [ ] Video thumbnail generation

---

## Contributing

To implement this adapter:

1. Fork repository
2. Create `src/kira/adapters/filesystem/watcher.py`
3. Implement `FilesystemAdapter` class
4. Add tests in `tests/integration/adapters/test_filesystem.py`
5. Submit PR

**Required Features:**
- Directory watching (polling or OS events)
- Markdown parsing
- Schema validation
- Event publishing
- Duplicate detection

---

## References

- [Watchdog Library](https://github.com/gorakhargosh/watchdog) - Cross-platform file watching
- **ADR-013:** Filesystem Adapter Specification (TBD)
- **ADR-003:** Event Idempotency
- **ADR-005:** Structured Logging

---

**Status:** 🚧 Planned for Phase 7
**Version:** 0.0.0
**Last Updated:** 2025-10-08
