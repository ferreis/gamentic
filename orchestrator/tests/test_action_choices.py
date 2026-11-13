import json

from app import db, llm, repo


def proposed_choices(prefix="Pista"):
    return [{"label": f"{prefix} {choice_number}", "text": f"Investigar {prefix.lower()} {choice_number}.",
             "mode": "say" if choice_number == 5 else "do"} for choice_number in range(1, 6)]


def choice_reply(choices):
    return llm.LLMReply(content="", tool_calls=[llm.ToolCall("suggest_actions", {"choices": choices})])


def choice_calls(fake_llm):
    return [call for call in fake_llm.calls if call["names"] == ["suggest_actions"]]


def test_dedicated_ai_generates_five_choices_after_each_complete_turn(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    first_choices = proposed_choices("Portão")
    fake_llm.choices = choice_reply(first_choices)
    response = client.post(f"/games/{game_id}/action", json={"action": "Examinar o portão."})
    assert response.status_code == 200
    assert response.json()["state"]["action_choices"] == first_choices
    first_request = choice_calls(fake_llm)[-1]
    assert "Examinar o portão" in first_request["user"]
    assert "You step forward" in first_request["user"]
    assert "cue_character" not in first_request["names"]
    second_choices = proposed_choices("Túnel")
    fake_llm.choices = choice_reply(second_choices)
    continued = client.post(f"/games/{game_id}/continue", json={})
    assert continued.json()["state"]["action_choices"] == second_choices
    assert len(choice_calls(fake_llm)) == 2


def test_saved_ai_choices_are_cached_without_repeated_generation(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    assert client.get(f"/games/{game_id}/state").json()["action_choices"] == []
    choices = proposed_choices()
    fake_llm.choices = choice_reply(choices)
    first = client.post(f"/games/{game_id}/choices")
    assert first.json()["action_choices"] == choices
    assert client.post(f"/games/{game_id}/choices").json()["action_choices"] == choices
    assert client.get(f"/games/{game_id}/state").json()["action_choices"] == choices
    assert len(choice_calls(fake_llm)) == 1
    assert client.post("/games/unknown/choices").status_code == 404


def test_invalid_or_failed_generation_never_uses_fixed_choices_and_can_retry(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    fake_llm.choices = choice_reply([proposed_choices()[0]] * 5)
    response = client.post(f"/games/{game_id}/continue", json={})
    assert response.status_code == 200
    assert response.json()["beats"]
    assert response.json()["state"]["action_choices"] == []
    assert response.json()["state"]["action_choices_error"]
    fake_llm.choices = choice_reply(proposed_choices("Resgate"))
    assert client.post(f"/games/{game_id}/choices").json()["action_choices"] == proposed_choices("Resgate")
    beats = client.get(f"/games/{game_id}/beats").json()["beats"]
    assert all("Investigar resgate" not in beat["text"] for beat in beats)


def test_choices_agent_never_receives_private_facts_or_private_beats(client, fake_llm, world):
    world["characters"][0]["knowledge"] = "SEGREDO_DA_PERSONAGEM"
    game_id = client.post("/games", json=world).json()["game_id"]
    with db.get_conn() as conn:
        character = repo.get_characters(conn, game_id)[0]
        repo.add_beat(conn, game_id, "player", "Você", "dialogue", "CONVERSA_PRIVADA", world["start_location"], private_with=character["id"])
    client.post(f"/games/{game_id}/choices")
    source = json.dumps(choice_calls(fake_llm)[-1]["messages"])
    assert "SEGREDO_DA_PERSONAGEM" not in source and "CONVERSA_PRIVADA" not in source


def test_truncated_generation_keeps_story_and_exposes_retry(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    fake_llm.choices = llm.LLMReply(content="incompleto", finish_reason="length")
    response = client.post(f"/games/{game_id}/action", json={"action": "Avançar com cuidado."})
    assert response.status_code == 200
    assert response.json()["state"]["action_choices"] == []
    assert response.json()["state"]["action_choices_error"]


def test_json_output_is_accepted_from_ai_without_tool_call(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    fake_llm.choices = llm.LLMReply(content=json.dumps({"choices": proposed_choices()}))
    assert client.post(f"/games/{game_id}/choices").json()["action_choices"] == proposed_choices()


def test_background_images_do_not_regenerate_choices(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    first = client.post(f"/games/{game_id}/choices").json()["action_choices"]
    with db.get_conn() as conn:
        repo.add_beat(conn, game_id, "system", None, "image", "Arte pronta", world["start_location"], image_url="/image.png")
    assert client.post(f"/games/{game_id}/choices").json()["action_choices"] == first
    assert len(choice_calls(fake_llm)) == 1


def test_cancelling_choices_generation_preserves_previous_turn(client, fake_llm, world, monkeypatch):
    game_id = client.post("/games", json=world).json()["game_id"]
    previous = client.post(f"/games/{game_id}/choices").json()["action_choices"]
    before_beats = client.get(f"/games/{game_id}/beats").json()["beats"]
    def cancel_choices(messages, tools=None, **options):
        if tools and tools[0]["function"]["name"] == "suggest_actions":
            raise llm.LLMCancelled()
        return fake_llm(messages, tools=tools, **options)
    monkeypatch.setattr(llm, "chat", cancel_choices)
    response = client.post(f"/games/{game_id}/continue", json={})
    assert response.json()["stopped"] is True
    assert response.json()["state"]["action_choices"] == previous
    assert client.get(f"/games/{game_id}/beats").json()["beats"] == before_beats
