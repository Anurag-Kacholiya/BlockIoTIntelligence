import numpy as np
import pandas as pd

from src.data.preparation.raw_normalize import decode_numeric, feature_columns, normalize, normalize_categorical, schema


def test_hex_booleans_and_decimals_decode():
    s = pd.Series(["0x00000012", "0x0000bb14", "True", "False", "1.0", "0", " 5 "])
    assert decode_numeric(s, empty_as_zero=False).tolist() == [18.0, 47892.0, 1.0, 0.0, 1.0, 0.0, 5.0]


def test_empty_is_zero_only_for_tshark_output():
    s = pd.Series(["", "3"])
    assert decode_numeric(s, empty_as_zero=True).tolist() == [0.0, 3.0]
    assert np.isnan(decode_numeric(s, empty_as_zero=False)[0])


def test_text_in_numeric_column_is_nan():
    assert np.isnan(decode_numeric(pd.Series(["0.debian.pool.ntp.org"]), empty_as_zero=True)[0])


def test_categorical_absent_spellings_merge():
    assert normalize_categorical(pd.Series(["", "0", "0.0", "GET"])).tolist() == ["0", "0", "0", "GET"]


def test_realistic_schema_drops_dns_name_and_keeps_true_text_fields():
    drop, categorical = schema("realistic")
    assert "dns.qry.name" in drop and "frame.time" in drop and "udp.port" in drop
    assert "dns.qry.name.len" not in categorical and "mqtt.conack.flags" not in categorical
    assert "http.request.method" in categorical


def test_normalize_flags_misaligned_rows_invalid():
    row = {c: "0" for c in feature_columns()}
    good = dict(row, **{"tcp.flags": "0x00000018", "http.request.method": "GET"})
    shifted = dict(row, **{"dns.qry.name.len": "_googlecast._tcp.local"})   # text where a number belongs
    feats, ok = normalize(pd.DataFrame([good, shifted]), empty_as_zero=False, schema_name="realistic")
    assert ok.tolist() == [True, False]
    assert feats.loc[0, "tcp.flags"] == 24.0 and feats.loc[0, "http.request.method"] == "GET"
    assert "dns.qry.name" not in feats.columns
