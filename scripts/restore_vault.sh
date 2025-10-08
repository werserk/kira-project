#!/usr/bin/env bash
# Vault Restore Script (Phase 6 - Rollback Plan)
# Usage: ./scripts/restore_vault.sh <backup-file.tar.gz>

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored message
print_msg() {
    local color=$1
    shift
    echo -e "${color}$*${NC}"
}

# Print error and exit
die() {
    print_msg "$RED" "ERROR: $*" >&2
    exit 1
}

# Check prerequisites
check_prerequisites() {
    print_msg "$BLUE" "🔍 Checking prerequisites..."
    
    command -v tar >/dev/null 2>&1 || die "tar not found. Please install tar."
    
    if [ ! -f ".env" ]; then
        print_msg "$YELLOW" "⚠️  .env not found. Using defaults."
    fi
    
    print_msg "$GREEN" "✅ Prerequisites OK"
}

# Parse vault path from config
get_vault_path() {
    local vault_path="vault"
    
    if [ -f ".env" ]; then
        vault_path=$(grep -E "^KIRA_VAULT_PATH=" .env | cut -d'=' -f2 || echo "vault")
    fi
    
    if [ -f "kira.yaml" ]; then
        # Try to extract vault path from kira.yaml (basic parsing)
        local yaml_path=$(grep -E "^\s*path:" kira.yaml | head -1 | sed 's/.*path:\s*//' | tr -d '"' || echo "")
        if [ -n "$yaml_path" ]; then
            vault_path="$yaml_path"
        fi
    fi
    
    echo "$vault_path"
}

# Create backup of current vault before restore
backup_current_vault() {
    local vault_path=$1
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="vault-pre-restore-${timestamp}.tar.gz"
    
    if [ -d "$vault_path" ]; then
        print_msg "$BLUE" "📦 Creating backup of current vault..."
        tar -czf "$backup_file" "$vault_path" 2>/dev/null || true
        
        if [ -f "$backup_file" ]; then
            print_msg "$GREEN" "✅ Current vault backed up to: $backup_file"
        else
            print_msg "$YELLOW" "⚠️  Could not create pre-restore backup"
        fi
    else
        print_msg "$YELLOW" "⚠️  No existing vault found at: $vault_path"
    fi
}

# Restore vault from backup
restore_vault() {
    local backup_file=$1
    local vault_path=$2
    
    print_msg "$BLUE" "📂 Restoring vault from: $backup_file"
    
    # Validate backup file
    if [ ! -f "$backup_file" ]; then
        die "Backup file not found: $backup_file"
    fi
    
    # Check if it's a valid tar.gz file
    if ! tar -tzf "$backup_file" >/dev/null 2>&1; then
        die "Invalid backup file (not a valid tar.gz): $backup_file"
    fi
    
    # Remove current vault if exists
    if [ -d "$vault_path" ]; then
        print_msg "$YELLOW" "🗑️  Removing current vault..."
        rm -rf "$vault_path"
    fi
    
    # Extract backup
    print_msg "$BLUE" "📦 Extracting backup..."
    tar -xzf "$backup_file" -C . || die "Failed to extract backup"
    
    # Verify restored vault structure
    if [ ! -d "$vault_path" ]; then
        die "Restored vault not found at expected path: $vault_path"
    fi
    
    print_msg "$GREEN" "✅ Vault restored successfully to: $vault_path"
}

# Verify vault integrity
verify_vault() {
    local vault_path=$1
    
    print_msg "$BLUE" "🔍 Verifying vault integrity..."
    
    # Check required directories
    local required_dirs=("inbox" "tasks" "notes" "events")
    local missing_dirs=()
    
    for dir in "${required_dirs[@]}"; do
        if [ ! -d "$vault_path/$dir" ]; then
            missing_dirs+=("$dir")
        fi
    done
    
    if [ ${#missing_dirs[@]} -gt 0 ]; then
        print_msg "$YELLOW" "⚠️  Some directories are missing: ${missing_dirs[*]}"
        print_msg "$YELLOW" "⚠️  You may need to run: poetry run python -m kira.cli vault init"
    else
        print_msg "$GREEN" "✅ Vault structure verified"
    fi
    
    # Count entities
    local task_count=$(find "$vault_path/tasks" -type f -name "*.md" 2>/dev/null | wc -l || echo "0")
    local note_count=$(find "$vault_path/notes" -type f -name "*.md" 2>/dev/null | wc -l || echo "0")
    local event_count=$(find "$vault_path/events" -type f -name "*.md" 2>/dev/null | wc -l || echo "0")
    
    print_msg "$BLUE" "📊 Vault contents:"
    print_msg "$BLUE" "   - Tasks: $task_count"
    print_msg "$BLUE" "   - Notes: $note_count"
    print_msg "$BLUE" "   - Events: $event_count"
}

# Run post-restore validation (optional)
run_validation() {
    local vault_path=$1
    
    print_msg "$BLUE" "🧪 Running validation (optional)..."
    
    # Try to run vault validation if CLI is available
    if command -v poetry >/dev/null 2>&1; then
        if poetry run python -m kira.cli vault validate >/dev/null 2>&1; then
            print_msg "$GREEN" "✅ Vault validation passed"
        else
            print_msg "$YELLOW" "⚠️  Vault validation failed or not available"
        fi
    else
        print_msg "$YELLOW" "⚠️  Poetry not found, skipping validation"
    fi
}

# Main function
main() {
    local backup_file="${1:-}"
    
    print_msg "$BLUE" "═══════════════════════════════════════════"
    print_msg "$BLUE" "   Kira Vault Restore (v0.1.0-alpha)"
    print_msg "$BLUE" "═══════════════════════════════════════════"
    echo ""
    
    # Check arguments
    if [ -z "$backup_file" ]; then
        print_msg "$RED" "Usage: $0 <backup-file.tar.gz>"
        echo ""
        print_msg "$YELLOW" "Examples:"
        echo "  $0 vault-backup-20251008.tar.gz"
        echo "  $0 vault-pre-restore-20251008-143000.tar.gz"
        echo ""
        exit 1
    fi
    
    # Run checks
    check_prerequisites
    
    # Get vault path
    local vault_path=$(get_vault_path)
    print_msg "$BLUE" "📍 Vault path: $vault_path"
    echo ""
    
    # Confirm restore operation
    print_msg "$YELLOW" "⚠️  WARNING: This will replace the current vault with backup from: $backup_file"
    print_msg "$YELLOW" "⚠️  A backup of the current vault will be created before restore."
    echo ""
    read -p "Continue with restore? (yes/no): " -r
    echo ""
    
    if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
        print_msg "$YELLOW" "Restore cancelled by user."
        exit 0
    fi
    
    # Backup current vault
    backup_current_vault "$vault_path"
    echo ""
    
    # Restore from backup
    restore_vault "$backup_file" "$vault_path"
    echo ""
    
    # Verify restored vault
    verify_vault "$vault_path"
    echo ""
    
    # Run validation
    run_validation "$vault_path"
    echo ""
    
    print_msg "$GREEN" "═══════════════════════════════════════════"
    print_msg "$GREEN" "   ✅ Restore completed successfully!"
    print_msg "$GREEN" "═══════════════════════════════════════════"
    echo ""
    print_msg "$BLUE" "Next steps:"
    echo "  1. Verify your data: poetry run python -m kira.cli vault info"
    echo "  2. Run smoke test: make smoke"
    echo "  3. Check vault health: poetry run python -m kira.cli vault validate"
}

# Run main function
main "$@"

