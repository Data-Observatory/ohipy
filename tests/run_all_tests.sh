#!/usr/bin/env bash
#
# run_all_tests.sh - Full test suite orchestrator for OHI Python
#
# Runs all tests including 44 R/Python parity tests with zero manual prerequisites.
# Handles Docker image building, chl/ repo cloning, fixture generation, and pytest.
#
# Usage:
#   ./run_all_tests.sh              # Full pipeline
#   ./run_all_tests.sh --skip-docker  # Skip Docker checks and fixture generation
#   ./run_all_tests.sh --no-fixtures  # Skip fixture generation (use existing)
#   ./run_all_tests.sh --help         # Show help

set -euo pipefail

# ==============================================================================
# Configuration
# ==============================================================================

readonly SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "${SCRIPT_DIR}/.."

readonly SCRIPT_NAME="run_all_tests.sh"
readonly DOCKER_IMAGE="ohicore-r-env"
readonly DOCKER_CONTEXT="tests/comparative/images/R/"
readonly CHL_REPO="https://github.com/OHI-Science/chl"
readonly CHL_DIR="chl"
readonly NOISE_SCRIPT="tests/parity/setup_fixtures.py"
readonly SCORES_SCRIPT="scripts/run_python_scores.py"

# Color codes (disabled when piped)
if [[ -t 1 ]]; then
    readonly RED='\033[0;31m'
    readonly GREEN='\033[0;32m'
    readonly YELLOW='\033[0;33m'
    readonly BLUE='\033[0;34m'
    readonly NC='\033[0m' # No Color
else
    readonly RED=''
    readonly GREEN=''
    readonly YELLOW=''
    readonly BLUE=''
    readonly NC=''
fi

# Flags
SKIP_DOCKER=false
NO_FIXTURES=false
TIER=""  # "" = integrity+parity, "integrity", "parity", "parity_full", "all"

# Timing
START_TIME=0
PHASE_START=0

# Test counts (populated by run_pytest)
TEST_TOTAL=0
TEST_PASSED=0
TEST_FAILED=0
TEST_SKIPPED=0

# ==============================================================================
# Utility Functions
# ==============================================================================

log_info() {
    echo -e "${BLUE}INFO${NC}: $1"
}

log_ok() {
    echo -e "${GREEN}OK${NC}: $1"
}

log_warn() {
    echo -e "${YELLOW}WARN${NC}: $1"
}

log_error() {
    echo -e "${RED}ERROR${NC}: $1" >&2
}

phase_banner() {
    local phase_num="$1"
    local description="$2"
    echo ""
    echo -e "${GREEN}=== Phase ${phase_num}: ${description} ===${NC}"
    PHASE_START=$(date +%s)
}

phase_elapsed() {
    local end_time=$(date +%s)
    local elapsed=$((end_time - PHASE_START))
    local minutes=$((elapsed / 60))
    local seconds=$((elapsed % 60))
    echo "${minutes}m ${seconds}s"
}

total_elapsed() {
    local end_time=$(date +%s)
    local elapsed=$((end_time - START_TIME))
    local minutes=$((elapsed / 60))
    local seconds=$((elapsed % 60))
    echo "${minutes}m ${seconds}s"
}

show_help() {
    cat <<EOF
Usage: ${SCRIPT_NAME} [OPTIONS]

Run the full OHI test suite including 44 R/Python parity tests.

Options:
  --skip-docker    Skip Docker checks and fixture generation (for offline testing)
  --no-fixtures    Skip R fixture generation (use existing fixtures)
  --tier TIER      Run specific test tier: integrity, parity, parity_full, all
                   (default: integrity + parity, skips parity_full)
  --help           Show this help message

Tiers:
  integrity        Fast data integrity tests (no Docker) - unit tests
  parity           Baseline R-vs-Python parity tests
  parity_full      Comprehensive 44-variation parity tests (requires Docker)
  all              All tiers including parity_full

Phases:
  1. Preflight checks (uv, Docker, image, chl repo)
  2. Generate noisy layers (1%, 5%, 10%)
  3. Generate R fixtures (44 tests)
  4. Generate Python scores
  5. Run pytest
  6. Summary

Examples:
  ${SCRIPT_NAME}                    # integrity + parity (default)
  ${SCRIPT_NAME} --skip-docker      # Skip Docker, run unit tests only
  ${SCRIPT_NAME} --no-fixtures      # Use existing fixtures
  ${SCRIPT_NAME} --tier integrity   # Fast unit tests only
  ${SCRIPT_NAME} --tier parity      # Baseline parity only
  ${SCRIPT_NAME} --tier all         # All tiers including parity_full

Exit Codes:
  0  All tests passed
  1  One or more tests failed or preflight check failed
EOF
}

# ==============================================================================
# Preflight Checks
# ==============================================================================

check_uv() {
    log_info "Checking for uv..."
    if command -v uv &> /dev/null; then
        log_ok "uv found: $(command -v uv)"
        return 0
    else
        log_error "uv not found. Please install uv: https://docs.astral.sh/uv/"
        return 1
    fi
}

check_docker_binary() {
    log_info "Checking for Docker binary..."
    if command -v docker &> /dev/null; then
        log_ok "Docker binary found: $(command -v docker)"
        return 0
    else
        log_error "Docker binary not found. Please install Docker."
        return 1
    fi
}

check_docker_daemon() {
    log_info "Checking Docker daemon..."
    if docker info &> /dev/null; then
        log_ok "Docker daemon is running"
        return 0
    else
        log_error "Docker daemon is not running. Please start Docker."
        return 1
    fi
}

check_docker_image() {
    log_info "Checking for Docker image: ${DOCKER_IMAGE}..."
    if docker image inspect "${DOCKER_IMAGE}" &> /dev/null; then
        log_ok "Docker image exists: ${DOCKER_IMAGE}"
        return 0
    else
        log_warn "Docker image not found: ${DOCKER_IMAGE}"
        log_info "Building Docker image from ${DOCKER_CONTEXT}..."
        if docker build -t "${DOCKER_IMAGE}" "${DOCKER_CONTEXT}"; then
            log_ok "Docker image built successfully"
            return 0
        else
            log_error "Failed to build Docker image"
            return 1
        fi
    fi
}

check_chl_repo() {
    log_info "Checking for chl/ repository..."
    if [[ -d "${CHL_DIR}/comunas/conf" ]]; then
        log_ok "chl/ repository exists with required files"
        return 0
    else
        log_warn "chl/ repository not found or incomplete"
        log_info "Cloning ${CHL_REPO}..."
        if git clone --depth 1 "${CHL_REPO}" "${CHL_DIR}"; then
            log_ok "chl/ repository cloned successfully"
            return 0
        else
            log_error "Failed to clone chl/ repository"
            return 1
        fi
    fi
}

run_preflight() {
    phase_banner 1 "Preflight Checks"
    
    local success="true"
    
    # Always check uv
    check_uv || success="false"
    
    if [[ "${SKIP_DOCKER}" == "true" ]]; then
        log_warn "Skipping Docker checks (--skip-docker)"
    else
        check_docker_binary || success="false"
        if [[ "${success}" == "true" ]]; then
            check_docker_daemon || success="false"
        fi
        if [[ "${success}" == "true" ]]; then
            check_docker_image || success="false"
        fi
        if [[ "${success}" == "true" ]]; then
            check_chl_repo || success="false"
        fi
    fi
    
    echo ""
    log_info "Preflight elapsed: $(phase_elapsed)"
    
    if [[ "${success}" == "true" ]]; then
        log_ok "Preflight checks passed"
        return 0
    else
        log_error "Preflight checks failed"
        return 1
    fi
}

# ==============================================================================
# Phase Functions
# ==============================================================================

run_noisy_layers() {
    phase_banner 2 "Generate Noisy Layers"
    
    if [[ "${SKIP_DOCKER}" == "true" ]]; then
        log_warn "Skipping noisy layers (--skip-docker)"
        return 0
    fi
    
    log_info "Generating noisy layers (1%, 5%, 10%)..."
    if uv run python "${NOISE_SCRIPT}" --generate-noise-only; then
        log_ok "Noisy layers generated"
        log_info "Phase elapsed: $(phase_elapsed)"
        return 0
    else
        log_error "Failed to generate noisy layers"
        log_info "Phase elapsed: $(phase_elapsed)"
        return 1
    fi
}

run_fixtures() {
    phase_banner 3 "Generate R Fixtures"
    
    if [[ "${SKIP_DOCKER}" == "true" ]]; then
        log_warn "Skipping fixture generation (--skip-docker)"
        return 0
    fi
    
    if [[ "${NO_FIXTURES}" == "true" ]]; then
        log_warn "Skipping fixture generation (--no-fixtures)"
        return 0
    fi
    
    log_info "Generating R fixtures (44 tests)..."
    if OHI_AUTO_GENERATE_FIXTURES=1 uv run python "${NOISE_SCRIPT}"; then
        log_ok "R fixtures generated"
        log_info "Phase elapsed: $(phase_elapsed)"
        return 0
    else
        log_error "Failed to generate R fixtures"
        log_info "Phase elapsed: $(phase_elapsed)"
        return 1
    fi
}

run_python_scores() {
    phase_banner 4 "Generate Python Scores"
    
    log_info "Running Python score calculation..."
    if uv run python "${SCORES_SCRIPT}"; then
        log_ok "Python scores generated"
        log_info "Phase elapsed: $(phase_elapsed)"
        return 0
    else
        log_error "Failed to generate Python scores"
        log_info "Phase elapsed: $(phase_elapsed)"
        return 1
    fi
}

run_pytest() {
    phase_banner 5 "Run pytest"
    
    local tier_selected=false
    local pytest_exit_code=0
    
    run_pytest_tier() {
        local marker="$1"
        local description="$2"
        local tier_start
        
        echo ""
        echo -e "${BLUE}--- Running ${description} ---${NC}"
        tier_start=$(date +%s)
        
        local pytest_output
        pytest_output=$(OHI_AUTO_GENERATE_FIXTURES=1 uv run pytest tests/ -m "${marker}" -v --tb=short 2>&1) && pytest_exit_code=0 || pytest_exit_code=$?
        
        echo "$pytest_output"
        
        local tier_end=$(date +%s)
        local tier_elapsed=$((tier_end - tier_start))
        local minutes=$((tier_elapsed / 60))
        local seconds=$((tier_elapsed % 60))
        echo -e "${BLUE}--- ${description} completed: ${minutes}m ${seconds}s ---${NC}"
        
        # Parse and accumulate test counts
        local summary_line
        summary_line=$(echo "$pytest_output" | grep -E '[0-9]+ (passed|failed)' | tail -1)
        
        if [[ -n "$summary_line" ]]; then
            local tier_passed tier_failed tier_skipped
            tier_passed=$(echo "$summary_line" | grep -oE '[0-9]+ passed' | grep -oE '[0-9]+' || echo "0")
            tier_failed=$(echo "$summary_line" | grep -oE '[0-9]+ failed' | grep -oE '[0-9]+' || echo "0")
            tier_skipped=$(echo "$summary_line" | grep -oE '[0-9]+ skipped' | grep -oE '[0-9]+' || echo "0")
            TEST_PASSED=$((TEST_PASSED + tier_passed))
            TEST_FAILED=$((TEST_FAILED + tier_failed))
            TEST_SKIPPED=$((TEST_SKIPPED + tier_skipped))
        fi
        
        return $pytest_exit_code
    }
    
    case "${TIER}" in
        integrity)
            run_pytest_tier "integrity" "Integrity tests" || pytest_exit_code=$?
            tier_selected=true
            ;;
        parity)
            run_pytest_tier "parity" "Parity tests" || pytest_exit_code=$?
            tier_selected=true
            ;;
        parity_full)
            run_pytest_tier "parity_full" "Parity full tests" || pytest_exit_code=$?
            tier_selected=true
            ;;
        all)
            run_pytest_tier "integrity" "Integrity tests" || pytest_exit_code=$?
            run_pytest_tier "parity" "Parity tests" || pytest_exit_code=$?
            run_pytest_tier "parity_full" "Parity full tests" || pytest_exit_code=$?
            tier_selected=true
            ;;
        *)
            # Default: integrity + parity (skip parity_full)
            run_pytest_tier "integrity" "Integrity tests" || pytest_exit_code=$?
            run_pytest_tier "parity" "Parity tests" || pytest_exit_code=$?
            tier_selected=true
            ;;
    esac
    
    TEST_TOTAL=$((TEST_PASSED + TEST_FAILED + TEST_SKIPPED))
    
    echo ""
    log_info "Phase elapsed: $(phase_elapsed)"
    
    if [[ $pytest_exit_code -eq 0 ]]; then
        log_ok "pytest passed"
        return 0
    else
        log_error "pytest failed"
        return 1
    fi
}

run_summary() {
    phase_banner 6 "Summary"
    
    if [[ $TEST_TOTAL -gt 0 ]]; then
        echo ""
        echo "Test Results:"
        echo "  Total:   $TEST_TOTAL"
        echo "  Passed:  $TEST_PASSED"
        echo "  Failed:  $TEST_FAILED"
        echo "  Skipped: $TEST_SKIPPED"
    fi
    
    log_info "Total elapsed: $(total_elapsed)"
    
    if [[ "${SKIP_DOCKER}" == "true" ]]; then
        log_warn "Docker-dependent tests were skipped (--skip-docker)"
    fi
    
    if [[ "${NO_FIXTURES}" == "true" ]]; then
        log_warn "Fixture generation was skipped (--no-fixtures)"
    fi
}

# ==============================================================================
# Main
# ==============================================================================

main() {
    START_TIME=$(date +%s)
    
    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --no-fixtures)
                NO_FIXTURES=true
                shift
                ;;
            --tier)
                if [[ -z "${2:-}" ]]; then
                    log_error "--tier requires a value (integrity, parity, parity_full, all)"
                    show_help
                    exit 1
                fi
                case "$2" in
                    integrity|parity|parity_full|all)
                        TIER="$2"
                        ;;
                    *)
                        log_error "Invalid tier: $2 (valid: integrity, parity, parity_full, all)"
                        show_help
                        exit 1
                        ;;
                esac
                shift 2
                ;;
            --all)
                TIER="all"
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
    
    echo "========================================"
    echo "  OHI Full Test Suite"
    echo "========================================"
    echo ""
    
    local success="true"
    
    # Phase 1: Preflight
    run_preflight || success="false"
    
    # Phase 2: Noisy layers (skip if preflight failed or --skip-docker)
    if [[ "${success}" == "true" ]]; then
        run_noisy_layers || success="false"
    fi
    
    # Phase 3: R fixtures (skip if preflight failed or --skip-docker/--no-fixtures)
    if [[ "${success}" == "true" ]]; then
        run_fixtures || success="false"
    fi
    
    # Phase 4: Python scores
    if [[ "${success}" == "true" ]]; then
        run_python_scores || success="false"
    fi
    
    # Phase 5: pytest
    if [[ "${success}" == "true" ]]; then
        run_pytest || success="false"
    fi
    
    # Phase 6: Summary (always run)
    run_summary
    
    echo ""
    if [[ "${success}" == "true" ]]; then
        log_ok "All tests passed!"
        exit 0
    else
        log_error "One or more phases failed"
        exit 1
    fi
}

main "$@"
