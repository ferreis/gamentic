import json

from app import llm, media
from app.config import settings
from app.visual_prompts import compact_english_prompt


def test_character_provider_receives_compact_english_instead_of_portuguese_story(monkeypatch):
    visual_fields = {"style": "Epic science-fantasy painting", "subject": "young human man",
                     "clothing": "a dark armored jacket", "lighting": "dramatic blue light"}
    generated_prompt = "Epic science-fantasy painting, fully clothed young human man, wearing a dark armored jacket, dramatic blue light"
    model_calls = []
    provider_calls = []

    def translate(messages, **options):
        model_calls.append((messages, options))
        return llm.LLMReply(content=json.dumps(visual_fields))

    class CaptureProvider:
        def character_set(self, descriptor, style, seed):
            provider_calls.append((descriptor, style, seed))
            return {"face_url": "/face.png"}

    monkeypatch.setattr(settings, "IMAGE_ENABLED", True)
    monkeypatch.setattr(settings, "IMAGE_PROMPT_WORDS", 36)
    monkeypatch.setattr(llm, "chat", translate)
    monkeypatch.setattr(media, "_provider", lambda: CaptureProvider())
    result = media.generate_character_images("Herdeiro observador, 0% de sincronização", "Pintura épica de fantasia científica", seed=42)
    assert result == {"face_url": "/face.png"}
    assert model_calls[0][1]["output_language"] == "en"
    assert "fully clothed" in model_calls[0][0][0]["content"]
    assert "Pintura épica" in model_calls[0][0][-1]["content"]
    assert provider_calls == [(generated_prompt, "", 42)]


def test_unfinished_translation_does_not_send_raw_portuguese_to_image_model(monkeypatch):
    monkeypatch.setattr(settings, "IMAGE_ENABLED", True)
    monkeypatch.setattr(settings, "IMAGE_PROMPT_WORDS", 36)
    monkeypatch.setattr(llm, "chat", lambda *arguments, **options: llm.LLMReply(content="", finish_reason="length"))

    provider_requests = []

    def unexpected_provider():
        provider_requests.append(True)
        raise AssertionError("The image provider must not receive an unfinished prompt")

    monkeypatch.setattr(media, "_provider", unexpected_provider)
    assert media.generate_scene_image("O hangar é escuro.") is None
    assert not provider_requests


def test_long_style_cannot_displace_character_or_outfit(monkeypatch):
    visual_fields = {
        "style": "Epic science fantasy digital painting with steel crystal walls towers hangars ruins ancient machinery",
        "subject": "young human woman with silver hair green eyes alert expression military heir standing in a palace",
        "clothing": "dark pilot uniform with steel armor plates",
        "lighting": "cold blue rim light from the ceiling",
    }
    monkeypatch.setattr(llm, "chat", lambda *arguments, **options: llm.LLMReply(content=json.dumps(visual_fields)))
    prompt = compact_english_prompt("Irmã gêmea, 93% de sincronização", 36, character=True)
    assert len(prompt.split()) <= 36
    assert prompt.startswith("Epic science fantasy digital painting with, fully clothed young human woman")
    assert "wearing dark pilot uniform with steel armor plates" in prompt
    assert "hangars" not in prompt
