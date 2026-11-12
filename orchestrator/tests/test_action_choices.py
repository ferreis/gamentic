import json

from app import db, llm, repo


def proposed_choices():
    return [{"label": f"Caminho {choice_number}", "text": f"Investigar a pista {choice_number}.",
             "mode": "say" if choice_number == 5 else "do"} for choice_number in range(1, 6)]


def test_five_choices_arrive_after_each_turn_without_extra_model_call(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    before = len(fake_llm.calls)
    response = client.post(f"/games/{game_id}/action", json={"action": "Examinar o ambiente."})
    assert response.status_code == 200
    assert len(response.json()["state"]["action_choices"]) == 5
    assert len(fake_llm.calls) - before == 2  # existing interpreter + narrator
    continued = client.post(f"/games/{game_id}/continue", json={})
    assert len(continued.json()["state"]["action_choices"]) == 5


def test_narrator_choices_persist_and_do_not_execute_themselves(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    choices = proposed_choices()
    fake_llm.narrator = llm.LLMReply(content="Uma nova pista aparece.",
        tool_calls=[llm.ToolCall("suggest_actions", {"choices": choices})])
    response = client.post(f"/games/{game_id}/action", json={"segments": [{"type": "do", "text": "Olhar à minha volta."}]})
    assert response.json()["state"]["action_choices"] == choices
    assert client.get(f"/games/{game_id}/state").json()["action_choices"] == choices
    beats = client.get(f"/games/{game_id}/beats").json()["beats"]
    assert all("Investigar a pista" not in beat["text"] for beat in beats)


def test_invalid_repeated_choices_fall_back_and_private_facts_stay_private(client, fake_llm, world):
    world["characters"][0]["knowledge"] = "SEGREDO_NAO_DESCOBERTO"
    game_id = client.post("/games", json=world).json()["game_id"]
    fake_llm.narrator = llm.LLMReply(content="O ambiente está calmo.", tool_calls=[
        llm.ToolCall("suggest_actions", {"choices": [proposed_choices()[0]] * 5})])
    response = client.post(f"/games/{game_id}/continue", json={})
    choices = response.json()["state"]["action_choices"]
    assert len(choices) == 5
    assert len({choice["text"] for choice in choices}) == 5
    assert "SEGREDO_NAO_DESCOBERTO" not in json.dumps(choices)


def test_a_new_turn_never_reuses_stale_choices(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    fake_llm.narrator = llm.LLMReply(content="Há pistas.", tool_calls=[llm.ToolCall("suggest_actions", {"choices": proposed_choices()})])
    client.post(f"/games/{game_id}/continue", json={})
    fake_llm.narrator = llm.LLMReply(content="A cena mudou.")
    response = client.post(f"/games/{game_id}/continue", json={})
    assert response.json()["state"]["action_choices"] != proposed_choices()
