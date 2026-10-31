"""SD-1 size parsing and formatting contracts."""
import pytest


@pytest.mark.parametrize("value,expected", [
    ("1B", 1), ("1KiB", 2**10), ("1MiB", 2**20),
    ("1GiB", 2**30), ("1TiB", 2**40), ("1G", 2**30),
    ("1KB", 1000), ("1MB", 10**6), ("1GB", 10**9),
    ("1TB", 10**12), ("2.5GiB", 2684354560), ("0B", 0),
])
def test_sd1_exact_bytes(value, expected):
    from recap.units import parse
    assert parse(value) == expected


@pytest.mark.parametrize("value", ["50", "-1GiB", "nanGiB", "1XB", "+1GiB"])
def test_sd1_reject_invalid_or_relative_sizes(value):
    from recap.units import parse
    with pytest.raises(ValueError):
        parse(value)


def test_sd1_relative_size_and_human_output():
    from recap.units import parse, format_gib
    assert parse("+10GiB", current=2**30) == 11 * 2**30
    assert parse("10GiB", current=2**30) == 10 * 2**30
    assert format_gib(2684354560) == "2.50 GiB"
