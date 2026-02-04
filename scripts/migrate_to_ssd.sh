#!/bin/bash

# Migrate Docker and Plex from HDD to SSD
#
# Current state:
#   Docker CE daemon.json data-root: /media/bengrady4/Files2/docker (HDD)
#   Snap Docker also running (conflict)
#   Plex: /var/lib/plexmediaserver -> /media/bengrady4/Files2/plexmediaserver (HDD symlink)
#
# Target state:
#   Docker CE data-root: /var/lib/docker (SSD, default)
#   Snap Docker disabled
#   Plex metadata: /var/lib/plexmediaserver on SSD (no symlink)
#
# Usage:
#   sudo ./migrate_to_ssd.sh              # interactive, prompts before each step
#   sudo ./migrate_to_ssd.sh --yes        # non-interactive, runs all steps
#   sudo ./migrate_to_ssd.sh --resume     # skip prompts, resume from last completed step
#
# Disconnect-safe usage:
#   sudo nohup ./migrate_to_ssd.sh --yes &
#   # Check progress: tail -f /var/log/migrate_to_ssd.log
#   # Check state:    cat /var/tmp/migrate_to_ssd.state

set -uo pipefail

# ── Config ───────────────────────────────────────────────────────

HDD_DOCKER="/media/bengrady4/Files2/docker"
HDD_PLEX="/media/bengrady4/Files2/plexmediaserver"
SSD_DOCKER="/var/lib/docker"
SSD_PLEX="/var/lib/plexmediaserver"
DAEMON_JSON="/etc/docker/daemon.json"
STATE_FILE="/var/tmp/migrate_to_ssd.state"
LOG_FILE="/var/log/migrate_to_ssd.log"

AUTO_YES=false
RESUME=false

for arg in "$@"; do
    case "$arg" in
        --yes)    AUTO_YES=true ;;
        --resume) AUTO_YES=true; RESUME=true ;;
        --help|-h)
            sed -n '/^# Usage:/,/^$/p' "$0"
            exit 0
            ;;
    esac
done

# ── Logging ──────────────────────────────────────────────────────
# All output goes to both the terminal (if attached) and the log file.

mkdir -p "$(dirname "$LOG_FILE")"
exec > >(tee -a "$LOG_FILE") 2>&1

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${GREEN}[INFO]${NC} $*"; }
warn() { echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${YELLOW}[WARN]${NC} $*"; }
err()  { echo -e "$(date '+%Y-%m-%d %H:%M:%S') ${RED}[ERROR]${NC} $*"; }

# ── Signal handling ──────────────────────────────────────────────
# Ignore SIGHUP so the script keeps running if the terminal disconnects.
# SIGINT/SIGTERM trigger a clean message and exit.

trap '' HUP
trap 'err "Interrupted by signal. State preserved at $STATE_FILE. Re-run with --resume."; exit 130' INT TERM

# ── State tracking ───────────────────────────────────────────────
# Each completed step is recorded so the script can resume after
# a disconnect, reboot, or error.

step_done() {
    grep -qxF "$1" "$STATE_FILE" 2>/dev/null
}

mark_done() {
    echo "$1" >> "$STATE_FILE"
    log "Step completed: $1"
}

# ── Helpers ──────────────────────────────────────────────────────

confirm() {
    if $AUTO_YES; then
        log "(auto-yes) $1"
        return 0
    fi
    # If stdin is not a terminal, default to yes
    if [[ ! -t 0 ]]; then
        log "(non-interactive, defaulting yes) $1"
        return 0
    fi
    read -rp "$1 [y/N] " response
    [[ "$response" =~ ^[Yy]$ ]]
}

if [[ $EUID -ne 0 ]]; then
    err "This script must be run as root (sudo)."
    exit 1
fi

echo ""
echo "============================================"
echo "  HDD -> SSD Migration Script"
echo "  $(date)"
echo "============================================"
echo ""

df -h / | tail -1 | awk '{print "SSD: " $4 " free out of " $2}'

if [[ -f "$STATE_FILE" ]]; then
    log "Resuming. Completed steps:"
    sed 's/^/  /' "$STATE_FILE"
fi
echo ""

# ── Docker Migration ─────────────────────────────────────────────

migrate_docker() {
    log "=== Docker Migration ==="

    # Check if already fully done
    if step_done "docker_complete"; then
        log "Docker migration already completed. Skipping."
        return 0
    fi

    # Check current state
    local current_root
    current_root=$(docker info 2>/dev/null | grep "Docker Root Dir" | awk -F': ' '{print $2}' || true)
    log "Current Docker root: $current_root"

    if [[ "$current_root" == "$SSD_DOCKER" ]] && ! snap list docker &>/dev/null; then
        log "Docker is already on the SSD and snap Docker is not installed. Skipping."
        mark_done "docker_complete"
        return 0
    fi

    if ! confirm "Migrate Docker to SSD? This will stop all containers."; then
        warn "Skipping Docker migration."
        return 0
    fi

    # Step: Stop services
    if ! step_done "docker_stopped"; then
        log "Stopping Docker CE..."
        systemctl stop docker docker.socket 2>/dev/null || true

        if snap list docker &>/dev/null; then
            log "Stopping and disabling snap Docker..."
            snap stop docker 2>/dev/null || true
            snap disable docker 2>/dev/null || true
        fi
        mark_done "docker_stopped"
    else
        log "Docker services already stopped. Skipping."
    fi

    # Step: Update daemon.json
    if ! step_done "docker_config_updated"; then
        log "Updating $DAEMON_JSON (removing HDD data-root)..."
        if [[ -f "$DAEMON_JSON" ]]; then
            cp "$DAEMON_JSON" "${DAEMON_JSON}.bak.$(date +%s)"
            log "Backed up existing daemon.json"
        fi

        cat > "$DAEMON_JSON" <<'EOF'
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "50m",
    "max-file": "3"
  }
}
EOF
        mark_done "docker_config_updated"
    else
        log "daemon.json already updated. Skipping."
    fi

    # Step: Copy snap Docker data (rsync is safe to re-run)
    if ! step_done "docker_snap_copied"; then
        local snap_docker="/var/snap/docker/common/var-lib-docker"
        if [[ -d "$snap_docker" ]]; then
            local snap_size
            snap_size=$(du -sm "$snap_docker" 2>/dev/null | awk '{print $1}')
            if [[ "$snap_size" -gt 10 ]]; then
                log "Snap Docker has ${snap_size}MB of data. Copying to $SSD_DOCKER..."
                rsync -a --info=progress2 "$snap_docker/" "$SSD_DOCKER/"
            else
                log "Snap Docker dir is minimal (${snap_size}MB). Nothing to copy."
            fi
        fi
        mark_done "docker_snap_copied"
    else
        log "Snap Docker data already copied. Skipping."
    fi

    # Step: Copy HDD Docker data (rsync is safe to re-run)
    if ! step_done "docker_hdd_copied"; then
        if [[ -d "$HDD_DOCKER" ]]; then
            local hdd_size
            hdd_size=$(du -sm "$HDD_DOCKER" 2>/dev/null | awk '{print $1}')
            if [[ "$hdd_size" -gt 10 ]]; then
                log "HDD Docker has ${hdd_size}MB of data. Copying to $SSD_DOCKER..."
                rsync -a --info=progress2 "$HDD_DOCKER/" "$SSD_DOCKER/"
            else
                log "HDD Docker dir is empty/minimal (${hdd_size}MB). Nothing to copy."
            fi
        fi
        mark_done "docker_hdd_copied"
    else
        log "HDD Docker data already copied. Skipping."
    fi

    # Step: Start Docker and verify
    if ! step_done "docker_started"; then
        log "Starting Docker CE..."
        systemctl start docker

        local new_root
        new_root=$(docker info 2>/dev/null | grep "Docker Root Dir" | awk -F': ' '{print $2}')
        if [[ "$new_root" == "$SSD_DOCKER" ]]; then
            log "Docker root is now: $new_root (SSD)"
        else
            err "Docker root is: $new_root (expected $SSD_DOCKER)"
            err "Leaving state so you can investigate. Re-run with --resume after fixing."
            return 1
        fi

        log "Running containers:"
        docker ps --format "  {{.Names}} ({{.Status}})"
        mark_done "docker_started"
    else
        log "Docker already started and verified. Skipping."
    fi

    mark_done "docker_complete"
    log "Docker migration complete."
    warn "Old HDD data at $HDD_DOCKER can be removed once you verify everything works."
}

# ── Plex Migration ───────────────────────────────────────────────

migrate_plex() {
    log "=== Plex Migration ==="

    if step_done "plex_complete"; then
        log "Plex migration already completed. Skipping."
        return 0
    fi

    # Check current state
    local real_path
    real_path=$(readlink -f "$SSD_PLEX" 2>/dev/null || echo "$SSD_PLEX")
    log "Current Plex data path: $real_path"

    if [[ ! -L "$SSD_PLEX" ]] && [[ "$real_path" == "$SSD_PLEX" ]] && [[ -d "$SSD_PLEX/Library" ]]; then
        log "Plex data is already on the SSD (not a symlink). Skipping."
        mark_done "plex_complete"
        return 0
    fi

    local plex_size
    plex_size=$(du -sh "$HDD_PLEX" 2>/dev/null | awk '{print $1}')
    log "Plex data size: $plex_size"

    # Check SSD has enough space
    local ssd_free_mb
    ssd_free_mb=$(df -m / | tail -1 | awk '{print $4}')
    local plex_size_mb
    plex_size_mb=$(du -sm "$HDD_PLEX" 2>/dev/null | awk '{print $1}')

    if [[ "$plex_size_mb" -gt "$ssd_free_mb" ]]; then
        err "Not enough space on SSD. Need ${plex_size_mb}MB, have ${ssd_free_mb}MB free."
        return 1
    fi

    if ! confirm "Migrate Plex metadata ($plex_size) to SSD? This will stop Plex."; then
        warn "Skipping Plex migration."
        return 0
    fi

    # Step: Stop Plex
    if ! step_done "plex_stopped"; then
        log "Stopping Plex..."
        systemctl stop plexmediaserver
        mark_done "plex_stopped"
    else
        log "Plex already stopped. Skipping."
    fi

    # Step: Remove symlink and create real directory
    if ! step_done "plex_symlink_removed"; then
        if [[ -L "$SSD_PLEX" ]]; then
            log "Removing symlink at $SSD_PLEX..."
            rm "$SSD_PLEX"
        fi
        mkdir -p "$SSD_PLEX"
        mark_done "plex_symlink_removed"
    else
        log "Symlink already removed. Skipping."
        mkdir -p "$SSD_PLEX"
    fi

    # Step: Copy data (rsync is safe to re-run / resume)
    if ! step_done "plex_data_copied"; then
        log "Copying Plex data from HDD to SSD ($plex_size)..."
        rsync -a --info=progress2 "$HDD_PLEX/" "$SSD_PLEX/"

        # Remove the self-referencing symlink if it exists
        if [[ -L "$SSD_PLEX/plexmediaserver" ]]; then
            rm "$SSD_PLEX/plexmediaserver"
        fi
        mark_done "plex_data_copied"
    else
        log "Plex data already copied. Skipping."
    fi

    # Step: Fix ownership and start
    if ! step_done "plex_started"; then
        log "Fixing ownership..."
        chown -R plex:plex "$SSD_PLEX"

        log "Starting Plex..."
        systemctl start plexmediaserver

        sleep 3
        if systemctl is-active --quiet plexmediaserver; then
            log "Plex is running."
        else
            err "Plex failed to start. Check: journalctl -u plexmediaserver"
            err "Leaving state so you can investigate. Re-run with --resume after fixing."
            return 1
        fi
        mark_done "plex_started"
    else
        log "Plex already started and verified. Skipping."
    fi

    mark_done "plex_complete"
    log "Plex migration complete."
    warn "Old HDD data at $HDD_PLEX can be removed once you verify everything works."
}

# ── Main ─────────────────────────────────────────────────────────

migrate_docker
echo ""
migrate_plex

echo ""
echo "============================================"
log "All migrations complete."
log "Verify your services work, then optionally clean up:"
echo "  sudo rm -rf $HDD_DOCKER"
echo "  sudo rm -rf $HDD_PLEX"
echo "  sudo rm $STATE_FILE"
echo "============================================"
