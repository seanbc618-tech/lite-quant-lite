"""Deterministic Qlib strategy helpers for comparable research runs."""
from __future__ import annotations

import numpy as np
import pandas as pd
from qlib.contrib.strategy import TopkDropoutStrategy


def break_score_ties(scores: pd.Series) -> pd.Series:
    """Return deterministic sortable scores, using instrument name for ties."""
    adjusted = scores.copy()
    valid = scores.dropna()
    if not valid.duplicated(keep=False).any():
        return adjusted

    ordered = pd.DataFrame(
        {"score": valid, "_instrument_key": valid.index.map(str)},
        index=valid.index,
    ).sort_values(["score", "_instrument_key"], ascending=[False, True], kind="mergesort")
    adjusted.loc[ordered.index] = np.arange(len(ordered), 0, -1, dtype=float)
    return adjusted


class _TieBreakingSignal:
    def __init__(self, signal: object) -> None:
        self._signal = signal

    def get_signal(self, *args: object, **kwargs: object) -> pd.Series | pd.DataFrame | None:
        prediction = self._signal.get_signal(*args, **kwargs)
        if isinstance(prediction, pd.DataFrame):
            adjusted = prediction.copy()
            adjusted.iloc[:, 0] = break_score_ties(adjusted.iloc[:, 0])
            return adjusted
        if isinstance(prediction, pd.Series):
            return break_score_ties(prediction)
        return prediction


class DeterministicTopkDropoutStrategy(TopkDropoutStrategy):
    """TopK dropout strategy with deterministic instrument tie-breaking."""

    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.signal = _TieBreakingSignal(self.signal)
