.PHONY: test-data test-quick test-integration test-all help

# Default target
help:
	@echo "Available targets:"
	@echo "  test-data        - Setup test data directory"
	@echo "  test-quick       - Run unit tests (no Docker)"
	@echo "  test-integration - Run integration tests (requires Docker)"
	@echo "  test-all         - Run all tests"

# Setup test data
test-data:
	uv run python tests/scripts/setup_test_data.py --force

# Quick unit tests (no Docker required)
test-quick:
	uv run pytest tests/ -v --ignore=tests/integration/

# Integration tests (requires Docker)
test-integration:
	uv run python tests/scripts/run_integration_tests.py --setup

# Run all tests
test-all: test-quick test-integration
