import pytest

from app import db, llm, repo


SCENARIO = {
    "title": "Mundo dos pactos",
    "setting": "Cidades cercadas por florestas e ruínas.",
    "rules": "Toda magia exige um pacto e cobra uma lembrança. Não existe ressurreição.",
    "tone": "Mistério e descoberta",
    "art_style": "Ilustração em aquarela",
    "narrator_persona": "Narração sóbria.",
}


def test_saving_scenario_does_not_create_game_or_call_model(client, monkeypatch):
    def unexpected_call(*arguments, **keywords):
        pytest.fail("Salvar regras não deve executar modelo ou criar mídia.")
    monkeypatch.setattr(llm, "chat", unexpected_call)
    scenario_id = client.post("/scenarios", json=SCENARIO).json()["scenario_id"]
    assert client.get("/games").json()["games"] == []
    assert client.get(f"/scenarios/{scenario_id}").json()["rules"] == SCENARIO["rules"]
    assert client.get("/scenarios").json()["scenarios"][0]["id"] == scenario_id


def test_creator_saves_reusable_scenario_and_retry_is_idempotent(client, fake_llm, monkeypatch):
    fake_llm.creator_text = llm.LLMReply(content="As regras estão definidas. [ready]")
    client.post("/create/message", json={"session_id": "blueprint", "message": SCENARIO["rules"]})
    original_chat = llm.chat
    scenario_calls = []
    def scenario_chat(messages, tools=None, **keywords):
        if tools and tools[0]["function"]["name"] == "save_scenario":
            scenario_calls.append(messages)
            return llm.LLMReply(content="", tool_calls=[llm.ToolCall("save_scenario", SCENARIO)])
        return original_chat(messages, tools=tools, **keywords)
    monkeypatch.setattr(llm, "chat", scenario_chat)
    first = client.post("/create/scenario", json={"session_id": "blueprint"})
    second = client.post("/create/scenario", json={"session_id": "blueprint"})
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert len(scenario_calls) == 1
    assert client.get("/games").json()["games"] == []


def test_unready_scenario_and_truncated_adventure_keep_source(client, fake_llm, world):
    client.post("/create/message", json={"session_id": "not-ready", "message": "Uma floresta."})
    assert client.post("/create/scenario", json={"session_id": "not-ready"}).status_code == 409
    assert client.get("/create/not-ready").status_code == 200
    scenario_id = client.post("/scenarios", json=SCENARIO).json()["scenario_id"]
    fake_llm.finalize = llm.LLMReply(content="", finish_reason="length", tool_calls=[llm.ToolCall("save_world", world)])
    assert client.post(f"/scenarios/{scenario_id}/start", json={"premise": "Um viajante."}).status_code == 409
    assert client.get("/games").json()["games"] == []
    assert client.get(f"/scenarios/{scenario_id}").json()["rules"] == SCENARIO["rules"]


def test_same_scenario_starts_independent_games_with_canonical_rules(client, fake_llm, world):
    scenario_id = client.post("/scenarios", json=SCENARIO).json()["scenario_id"]
    fake_llm.finalize = llm.LLMReply(content="", tool_calls=[llm.ToolCall("save_world", world)])
    first_id = client.post(f"/scenarios/{scenario_id}/start", json={"premise": "Uma cartógrafa perdida."}).json()["game_id"]
    with db.get_conn() as conn:
        repo.add_item(conn, first_id, "Chave conquistada", "Exclusiva da primeira aventura")
        repo.append_memory(conn, first_id, "SEGREDO DA PRIMEIRA PARTIDA")
        repo.advance_time(conn, first_id, 500)
    second_id = client.post(f"/scenarios/{scenario_id}/start", json={"premise": "Um ferreiro da capital."}).json()["game_id"]
    assert first_id != second_id
    opening_call = next(call for call in fake_llm.calls if "save_world" in call["names"])
    opening_properties = opening_call["tools"][0]["function"]["parameters"]["properties"]
    assert "setting" not in opening_properties and "rules" not in opening_properties
    assert opening_call["max_tokens"] <= 4096
    first_state = client.get(f"/games/{first_id}/state").json()
    second_state = client.get(f"/games/{second_id}/state").json()
    assert second_state["player"]["inventory"] == []
    assert second_state["time"]["minutes"] == 0
    assert first_state["characters"][0]["id"] != second_state["characters"][0]["id"]
    with db.get_conn() as conn:
        second_game = repo.get_game(conn, second_id)
        assert SCENARIO["rules"] in second_game["setting"]
        assert "ferreiro" in second_game["setting"]
        assert "cartógrafa" not in second_game["setting"]
        assert second_game["memory"] == ""
    assert client.get(f"/scenarios/{scenario_id}").json()["setting"] == SCENARIO["setting"]
    client.delete(f"/games/{first_id}")
    assert client.get(f"/scenarios/{scenario_id}").status_code == 200


def test_invalid_start_never_creates_an_adventure(client, fake_llm):
    assert client.post("/scenarios/unknown/start", json={"premise": "Uma viajante."}).status_code == 404
    scenario_id = client.post("/scenarios", json=SCENARIO).json()["scenario_id"]
    assert client.post(f"/scenarios/{scenario_id}/start", json={"premise": "   "}).status_code == 422
    assert not fake_llm.calls
