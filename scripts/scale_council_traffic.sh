#!/bin/bash
# 🚦 Council Traffic Scaling Script
# Scales council traffic percentage without container rebuild

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Default values
CONTAINER_NAME="api-canary"
CURRENT_PERCENT=""
TARGET_PERCENT=""

usage() {
    cat << EOF
🚦 Council Traffic Scaling Script

Usage: $0 [OPTIONS] TARGET_PERCENT

Scale council traffic to TARGET_PERCENT (0-100) with zero downtime.

Arguments:
    TARGET_PERCENT    Target traffic percentage (0-100)

Options:
    -c, --container   Container name (default: api-canary)
    -h, --help        Show this help message

Examples:
    $0 25             # Scale to 25% traffic
    $0 100            # Full rollout
    $0 0              # Disable council (emergency)
    
    # Custom container
    $0 -c my-api 50   # Scale my-api container to 50%

EOF
}

log() {
    echo "[$(date '+%H:%M:%S')] $*" >&2
}

error() {
    log "ERROR: $*"
    exit 1
}

get_current_percent() {
    local current
    current=$(docker exec "$CONTAINER_NAME" \
        sh -c 'echo $COUNCIL_TRAFFIC_PERCENT' 2>/dev/null || echo "0")
    echo "${current:-0}"
}

validate_percent() {
    local percent="$1"
    if ! [[ "$percent" =~ ^[0-9]+$ ]] || [ "$percent" -lt 0 ] || [ "$percent" -gt 100 ]; then
        error "Invalid percentage: $percent. Must be 0-100."
    fi
}

update_traffic_percent() {
    local target="$1"
    
    log "Updating COUNCIL_TRAFFIC_PERCENT from $CURRENT_PERCENT% to $target%..."
    
    # Update environment variable in container
    docker exec "$CONTAINER_NAME" \
        sh -c "sed -i 's/COUNCIL_TRAFFIC_PERCENT=[0-9]*/COUNCIL_TRAFFIC_PERCENT=$target/' /app/.env"
    
    # Reload configuration with SIGHUP (zero downtime)
    log "Sending SIGHUP to reload configuration..."
    docker exec "$CONTAINER_NAME" \
        sh -c 'kill -HUP 1'
    
    # Wait for reload
    sleep 2
    
    # Verify the change
    local new_percent
    new_percent=$(get_current_percent)
    
    if [ "$new_percent" = "$target" ]; then
        log "✅ Successfully scaled to $target% traffic"
    else
        error "Failed to update traffic percentage. Current: $new_percent%, Expected: $target%"
    fi
}

health_check() {
    log "Running health check..."
    
    local health_url="http://localhost:8000/healthz"
    local max_attempts=5
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if docker exec "$CONTAINER_NAME" \
            curl -s -f "$health_url" > /dev/null 2>&1; then
            log "✅ Health check passed"
            return 0
        fi
        
        log "Health check attempt $attempt/$max_attempts failed, retrying..."
        sleep 2
        ((attempt++))
    done
    
    error "Health check failed after $max_attempts attempts"
}

validate_metrics() {
    local target="$1"
    
    log "Validating metrics for $target% traffic..."
    
    # Check if prometheus metrics are accessible
    if docker exec "$CONTAINER_NAME" \
        curl -s "http://localhost:8000/metrics" | grep -q "swarm_council"; then
        log "✅ Council metrics are being exported"
    else
        log "⚠️ Council metrics not found (may take a moment to appear)"
    fi
    
    # Check council status endpoint
    if docker exec "$CONTAINER_NAME" \
        curl -s "http://localhost:8000/council/status" | grep -q "council_enabled"; then
        log "✅ Council status endpoint accessible"
    else
        log "⚠️ Council status endpoint not responding"
    fi
}

main() {
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case $1 in
            -c|--container)
                CONTAINER_NAME="$2"
                shift 2
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            -*)
                error "Unknown option: $1"
                ;;
            *)
                if [ -z "$TARGET_PERCENT" ]; then
                    TARGET_PERCENT="$1"
                else
                    error "Too many arguments"
                fi
                shift
                ;;
        esac
    done
    
    # Validate arguments
    if [ -z "$TARGET_PERCENT" ]; then
        usage
        exit 1
    fi
    
    validate_percent "$TARGET_PERCENT"
    
    # Check if container exists and is running
    if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
        error "Container '$CONTAINER_NAME' is not running"
    fi
    
    # Get current percentage
    CURRENT_PERCENT=$(get_current_percent)
    
    log "🚦 Council Traffic Scaling"
    log "Container: $CONTAINER_NAME"
    log "Current traffic: $CURRENT_PERCENT%"
    log "Target traffic: $TARGET_PERCENT%"
    
    if [ "$CURRENT_PERCENT" = "$TARGET_PERCENT" ]; then
        log "✅ Already at target percentage ($TARGET_PERCENT%)"
        exit 0
    fi
    
    # Perform the scaling
    update_traffic_percent "$TARGET_PERCENT"
    
    # Validate the deployment
    health_check
    validate_metrics "$TARGET_PERCENT"
    
    log "🎉 Council traffic successfully scaled to $TARGET_PERCENT%"
    log ""
    log "Next steps:"
    log "  • Monitor metrics for 24h before next scaling"
    log "  • Watch: curl http://localhost:8000/healthz"
    log "  • Metrics: curl http://localhost:8000/metrics | grep council"
    
    if [ "$TARGET_PERCENT" -lt 100 ] && [ "$TARGET_PERCENT" -gt 0 ]; then
        log "  • Scale further: $0 $((TARGET_PERCENT * 2))"
    fi
}

main "$@" 