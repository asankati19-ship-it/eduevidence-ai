import pytest

from scripts.run_e2e_demo import matched_facts


ANCHOR = "10 percentage points per 24-hour period"


@pytest.mark.parametrize("answer", [
    "The penalty is 10 percentage points per each 24-hour period or part thereof.",
    "The penalty is 10 percentage points deducted per 24-hour period or part of it.",
])
def test_late_work_scorer_accepts_observed_paraphrases(answer):
    assert matched_facts([ANCHOR], answer) == [ANCHOR]


def test_late_work_scorer_rejects_wrong_amount_or_interval():
    assert matched_facts([ANCHOR], "The penalty is 5 percentage points deducted per 12-hour period.") == []

