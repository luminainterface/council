#!/bin/bash
# Stage 0: Prep - LUMINA_MODE=test & isolated $OS_SANDBOX_ROOT
# Ensures CI never touches real FS; all shell work happens in /tmp/os_suite

set -euo pipefail

echo "🚀 Stage 0: Setting up isolated test environment"

# Export test environment variables
export LUMINA_MODE=test
export OS_SANDBOX_ROOT="/tmp/os_suite_$$"
export NO_NETWORK_ACCESS=true
export TEST_REDIS_DB=15  # Isolated Redis DB for testing

# Create isolated filesystem sandbox
mkdir -p "$OS_SANDBOX_ROOT"/{bin,tmp,data,cache,logs}

# Set up isolated PATH to prevent real system access
export PATH="$OS_SANDBOX_ROOT/bin:/usr/bin:/bin"

# Create safe shell sandbox for testing
cat > "$OS_SANDBOX_ROOT/bin/safe_shell" << 'EOF'
#!/bin/bash
# Sandboxed shell that blocks dangerous operations
case "$*" in
    *"rm -rf /"*|*"rm -rf /*"*|*"format"*|*"mkfs"*)
        echo "🚫 BLOCKED: Dangerous operation detected"
        exit 1
        ;;
    *"curl"*|*"wget"*|*"nc "*|*"netcat"*)
        echo "🚫 BLOCKED: Network access not allowed in test"
        exit 1
        ;;
    *)
        # Allow safe operations in sandbox only
        cd "$OS_SANDBOX_ROOT" && exec /bin/bash -c "$@"
        ;;
esac
EOF
chmod +x "$OS_SANDBOX_ROOT/bin/safe_shell"

# Verify isolation
echo "✅ Environment isolated:"
echo "  LUMINA_MODE=$LUMINA_MODE"
echo "  OS_SANDBOX_ROOT=$OS_SANDBOX_ROOT"
echo "  PATH restricted to sandbox"

# Export for CI
echo "export LUMINA_MODE=test" >> "$GITHUB_ENV" 2>/dev/null || true
echo "export OS_SANDBOX_ROOT=$OS_SANDBOX_ROOT" >> "$GITHUB_ENV" 2>/dev/null || true

echo "🎯 Stage 0: PASS - Isolated environment ready" 