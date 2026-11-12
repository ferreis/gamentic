import httpx
import respx


@respx.mock
def test_art_settings_are_forwarded_to_local_image_service(client, monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "comfy")
    monkeypatch.setenv("IMAGE_BASE_URL", "http://images.test")
    selection = {"checkpoint": "anime.safetensors", "loras": []}
    respx.get("http://images.test/image/settings").mock(return_value=httpx.Response(200, json={"settings": selection}))
    save_request = respx.put("http://images.test/image/settings").mock(return_value=httpx.Response(200, json={"settings": selection}))
    assert client.get("/images/settings").json()["settings"] == selection
    assert client.put("/images/settings", json=selection).json()["settings"] == selection
    assert b'anime.safetensors' in save_request.calls.last.request.content


@respx.mock
def test_model_compatibility_errors_are_preserved(client, monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "comfy")
    monkeypatch.setenv("IMAGE_BASE_URL", "http://images.test")
    respx.put("http://images.test/image/settings").mock(return_value=httpx.Response(422, json={"detail": "LoRA incompatível"}))
    response = client.put("/images/settings", json={"checkpoint": "anime", "loras": []})
    assert response.status_code == 422
    assert response.json()["detail"] == "LoRA incompatível"


def test_cloud_provider_does_not_offer_local_model_controls(client, monkeypatch):
    monkeypatch.setenv("IMAGE_PROVIDER", "openai")
    assert client.get("/images/settings").status_code == 409
