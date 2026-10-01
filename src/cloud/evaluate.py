"""Classification metrics used by every layer and experiment (ADR §10 Phase 8 "Accuracy")."""

from __future__ import annotations

import numpy as np
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)


def classification_metrics(y_true, y_pred, y_score=None) -> dict[str, float]:
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    p, r, f, _ = precision_recall_fscore_support(y_true, y_pred, average="macro", zero_division=0)
    _, _, fw, _ = precision_recall_fscore_support(y_true, y_pred, average="weighted", zero_division=0)
    out = {
        "accuracy": accuracy_score(y_true, y_pred),
        "precision_macro": p,
        "recall_macro": r,
        "f1_macro": f,
        "f1_weighted": fw,
        "support": float(len(y_true)),
    }
    if y_score is not None and len(np.unique(y_true)) == 2:
        out["roc_auc"] = roc_auc_score(y_true, y_score)
    return {k: float(v) for k, v in out.items()}


def confusion(y_true, y_pred, labels) -> list[list[int]]:
    return confusion_matrix(y_true, y_pred, labels=labels).tolist()
