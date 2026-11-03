from src.cloud.model_registry import layer_dir
from src.common.config import ROOT, active_view, load_config
from src.common.schemas import Layer


def test_view_defaults_to_config_and_env_overrides(monkeypatch):
    monkeypatch.delenv("BLOCKIOT_VIEW", raising=False)
    assert active_view() == load_config("models")["training"]["view"]
    monkeypatch.setenv("BLOCKIOT_VIEW", "real_time")
    assert active_view() == "real_time"


def test_mid_term_models_keep_their_folder_and_other_views_get_their_own(monkeypatch):
    primary = load_config("datasets")["edge_iiotset"]["primary"]
    monkeypatch.setenv("BLOCKIOT_VIEW", primary)
    assert layer_dir(Layer.EDGE) == ROOT / "models" / "edge"
    monkeypatch.setenv("BLOCKIOT_VIEW", "real_time")
    assert layer_dir(Layer.EDGE) == ROOT / "models" / "real_time" / "edge"
