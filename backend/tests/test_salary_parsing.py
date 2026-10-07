"""Pay stated in a listing is turned into one comparable yearly USD figure, or left unknown."""

import pytest

from backend.app.modules.rank.salary_benchmark import yearly_usd


@pytest.mark.parametrize("text, expected", [
    ("35000 - 50000 USD", (35000, 50000)),
    ("$90k - $105k", (90000, 105000)),
    ("125000 - 180000 USD", (125000, 180000)),
    ("$45-$120/Hour", (93600, 249600)),
    ("1000 - 1300 USD", (12000, 15600)),      # too low to be yearly: read as monthly
    ("80000 - 250000", (80000, 250000)),
    ("$70,000", (70000, 70000)),
])
def test_stated_pay_becomes_a_yearly_usd_range(text, expected):
    assert yearly_usd(text) == expected


@pytest.mark.parametrize("text", ["Not disclosed", "", None, "50000 - 80000 MXN", "€60k", "Competitive", "2026"])
def test_unknown_or_non_dollar_pay_is_left_unknown(text):
    assert yearly_usd(text) is None
