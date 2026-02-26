"""Basic smoke tests for OHIRunner."""


def test_runner_import():
    """Test that OHIRunner can be imported."""
    from ohipy.runner import OHIRunner

    assert OHIRunner is not None


def test_runner_instantiation(runner):
    """Test that OHIRunner can be instantiated."""
    assert runner is not None
