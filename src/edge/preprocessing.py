"""Edge preprocessing: encoding and scaling, fitted on the training split only (dataset plan steps 9-10)."""

from __future__ import annotations

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler


def build_preprocessor(numeric: list[str], categorical: list[str]) -> ColumnTransformer:
    transformers = [("num", StandardScaler(), numeric)]
    if categorical:
        # Unseen categories at inference (e.g. new injection payload strings) encode as all-zeros.
        transformers.append(("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical))
    return ColumnTransformer(transformers, verbose_feature_names_out=False)
