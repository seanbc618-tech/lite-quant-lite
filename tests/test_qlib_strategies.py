from __future__ import annotations

import numpy as np
import pandas as pd

from us_quant.qlib_strategies import break_score_ties


def test_break_score_ties_ranks_equal_scores_by_symbol():
    scores = pd.Series([0.5, 0.5, 0.2], index=["MSFT", "AAPL", "NVDA"])

    adjusted = break_score_ties(scores)

    assert list(adjusted.sort_values(ascending=False).index) == ["AAPL", "MSFT", "NVDA"]


def test_break_score_ties_preserves_order_of_distinct_scores():
    scores = pd.Series([0.4, 0.5, 0.2], index=["AAPL", "MSFT", "NVDA"])

    adjusted = break_score_ties(scores)

    assert list(adjusted.sort_values(ascending=False).index) == ["MSFT", "AAPL", "NVDA"]
    assert adjusted.equals(scores)


def test_break_score_ties_does_not_cross_an_adjacent_higher_score():
    higher = np.nextafter(0.5, np.inf)
    scores = pd.Series([0.5, 0.5, higher], index=["MSFT", "AAPL", "ZZZ"])

    adjusted = break_score_ties(scores)

    assert list(adjusted.sort_values(ascending=False).index) == ["ZZZ", "AAPL", "MSFT"]


def test_break_score_ties_accepts_qlib_named_instrument_index():
    scores = pd.Series([0.5, 0.5], index=pd.Index(["MSFT", "AAPL"], name="instrument"))

    adjusted = break_score_ties(scores)

    assert list(adjusted.sort_values(ascending=False).index) == ["AAPL", "MSFT"]
