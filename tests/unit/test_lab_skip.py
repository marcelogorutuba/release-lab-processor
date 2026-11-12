import pytest


def test_lab_probe_skipped():
    pytest.skip("lab probe: a skipped test must not be green")
