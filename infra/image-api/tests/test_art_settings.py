import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import art_settings, workflow


@pytest.fixture
def art_client(tmp_path, monkeypatch):
    from fastapi import FastAPI
    monkeypatch.setattr(art_settings, "SETTINGS_PATH", tmp_path / "art.json")
    application = FastAPI()
    application.include_router(art_settings.router)
    return TestClient(application)


def mock_catalog():
    respx.post(f"{art_settings.config.COMFY_URL}/free").mock(return_value=httpx.Response(200, json={}))
    return respx.get(f"{art_settings.config.COMFY_URL}/object_info").mock(return_value=httpx.Response(200, json={
        "CheckpointLoaderSimple": {"input": {"required": {"ckpt_name": [list(art_settings.CHECKPOINTS)]}}},
        "LoraLoader": {"input": {"required": {"lora_name": [[*art_settings.LORAS, "sdxl_lightning_4step_lora.safetensors"]]}}},
    }))


@respx.mock
def test_selection_persists_and_loras_reach_both_model_and_clip(art_client):
    mock_catalog()
    selection = {"checkpoint": "animagine-xl-4.0-opt.safetensors", "loras": [
        {"name": "pixel-art-xl.safetensors", "strength": 0.6},
        {"name": "papercut.safetensors", "strength": 0.3},
    ]}
    assert art_client.put("/image/settings", json=selection).status_code == 200
    assert art_client.get("/image/settings").json()["settings"] == selection
    graph, steps, prompt = art_settings.render_settings({}, 1, "a castle")
    assert steps == 28
    assert graph["7"]["inputs"]["cfg"] == 5.0
    assert all(node.get("class_type") != "LoraLoaderModelOnly" for node in graph.values())
    assert prompt == "pixel art, papercut, a castle"
    style_nodes = {node["inputs"]["lora_name"]: (node_id, node) for node_id, node in graph.items() if node["class_type"] == "LoraLoader"}
    pixel_id, pixel_node = style_nodes["pixel-art-xl.safetensors"]
    paper_id, paper_node = style_nodes["papercut.safetensors"]
    assert pixel_node["inputs"]["model"] == ["1", 0]
    assert pixel_node["inputs"]["strength_clip"] == 0.6
    assert paper_node["inputs"]["model"] == [pixel_id, 0]
    assert paper_node["inputs"]["clip"] == [pixel_id, 1]
    assert graph["7"]["inputs"]["model"] == [paper_id, 0]
    assert graph["3"]["inputs"]["clip"] == [paper_id, 1]
    assert art_settings.image_dimensions(384, 384) == (512, 512)
    assert art_settings.image_dimensions(320, 576) == (512, 928)


@respx.mock
@pytest.mark.parametrize("checkpoint", ["sd_turbo.safetensors", "LCM_AAM_AnyLoRA_AnimeMix.safetensors", ""])
def test_incompatible_lora_is_rejected_without_saving(art_client, checkpoint):
    mock_catalog()
    response = art_client.put("/image/settings", json={"checkpoint": checkpoint, "loras": [{"name": "pixel-art-xl.safetensors"}]})
    assert response.status_code == 422
    assert not art_settings.SETTINGS_PATH.exists()


@respx.mock
def test_reset_returns_to_server_workflow(art_client):
    mock_catalog()
    assert art_client.put("/image/settings", json={"checkpoint": "LCM_AAM_AnyLoRA_AnimeMix.safetensors"}).status_code == 200
    graph, steps, prompt = art_settings.render_settings({}, 1, "castle")
    assert graph["7"]["inputs"]["sampler_name"] == "lcm"
    assert art_client.put("/image/settings", json={}).status_code == 200
    assert art_settings.render_settings({"original": {}}, 1, "castle") == ({"original": {}}, 1, "castle")


@pytest.mark.parametrize("specifications", ['{}', '[{"name":"style","strength":NaN}]', '[{"name":"style","strength":3}]'])
def test_invalid_lora_config_is_rejected(specifications):
    with pytest.raises(workflow.WorkflowError):
        workflow.apply_loras({}, specifications)
