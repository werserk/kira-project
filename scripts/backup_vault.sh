#!/usr/bin/env bash
# Vault Backup Script (Phase 6 - Rollback Plan)
# Usage: ./scripts/backup_vault.sh [output-directory]

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

# Create backup
create_backup() {
    local vault_path=$1
    local output_dir=$2
    local timestamp=$(date +%Y%m%d-%H%M%S)
    local backup_file="${output_dir}/vault-backup-${timestamp}.tar.gz"
    
    print_msg "$BLUE" "📦 Creating backup..."
    print_msg "$BLUE" "   Source: $vault_path"
    print_msg "$BLUE" "   Output: $backup_file"
    
    # Create output directory if needed
    mkdir -p "$output_dir"
    
    # Check if vault exists
    if [ ! -d "$vault_path" ]; then
        die "Vault not found at: $vault_path"
    fi
    
    # Count entities before backup
    local task_count=$(find "$vault_path/tasks" -type f -name "*.md" 2>/dev/null | wc -l || echo "0")
    local note_count=$(find "$vault_path/notes" -type f -name "*.md" 2>/dev/null | wc -l || echo "0")
    local event_count=$(find "$vault_path/events" -type f -name "*.md" 2>/dev/null | wc -l || echo "0")
    
    print_msg "$BLUE" "📊 Backing up:"
    print_msg "$BLUE" "   - Tasks: $task_count"
    print_msg "$BLUE" "   - Notes: $note_count"
    print_msg "$BLUE" "   - Events: $event_count"
    
    # Create tar.gz backup
    tar -czf "$backup_file" "$vault_path" || die "Failed to create backup"
    
    # Verify backup was created
    if [ ! -f "$backup_file" ]; then
        die "Backup file was not created"
    fi
    
    # Get backup size
    local backup_size=$(du -h "$backup_file" | cut -f1)
    
    print_msg "$GREEN" "✅ Backup created successfully!"
    print_msg "$GREEN" "   File: $backup_file"
    print_msg "$GREEN" "   Size: $backup_size"
    
    echo "$backup_file"
}

# Verify backup integrity
verify_backup() {
    local backup_file=$1
    
    print_msg "$BLUE" "🔍 Verifying backup integrity..."
    
    if ! tar -tzf "$backup_file" >/dev/null 2>&1; then
        die "Backup verification failed: corrupted archive"
    fi
    
    print_msg "$GREEN" "✅ Backup integrity verified"
}

# Main function
main() {
    local output_dir="${1:-.}"
    
    print_msg "$BLUE" "═══════════════════════════════════════════"
    print_msg "$BLUE" "   Kira Vault Backup (v0.1.0-alpha)"
    print_msg "$BLUE" "═══════════════════════════════════════════"
    echo ""
    
    # Get vault path
    local vault_path=$(get_vault_path)
    print_msg "$BLUE" "📍 Vault path: $vault_path"
    echo ""
    
    # Create backup
    local backup_file=$(create_backup "$vault_path" "$output_dir")
    echo ""
    
    # Verify backup
    verify_backup "$backup_file"
    echo ""
    
    print_msg "$GREEN" "═══════════════════════════════════════════"
    print_msg "$GREEN" "   ✅ Backup completed successfully!"
    print_msg "$GREEN" "═══════════════════════════════════════════"
    echo ""
    print_msg "$BLUE" "To restore this backup:"
    echo "  ./scripts/restore_vault.sh $backup_file"
    echo ""
    print_msg "$BLUE" "Backup stored at:"
    echo "  $backup_file"
}

# Run main function
main "$@"

