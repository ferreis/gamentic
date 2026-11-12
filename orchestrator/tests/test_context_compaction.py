import json

import pytest

from app import context, creator, db, llm, prompts, repo
from app.config import settings


def test_tool_schemas_are_counted_and_latest_overflow_is_not_skipped():
    messages = [{"role": "user", "content": "Olá"}]
    large_tool = [{"function": {"description": "regras " * 3000}}]
    assert context.estimate_tokens(messages, large_tool) > context.estimate_tokens(messages) + 5000
    history = [{"text": "antigo"}, {"text": "novo " * 100}]
    assert context.keep_recent(history, lambda beat: beat["text"], 10) == []


def test_long_beat_is_folded_in_bounded_batches_without_changing_log(client, fake_llm, world, monkeypatch):
    game_id = client.post("/games", json=world).json()["game_id"]
    monkeypatch.setattr(settings, "CONTEXT_FOLD_BATCH_TOKENS", 200)
    fake_llm.summary = llm.LLMReply(content="- Fatos antigos preservados.")
    with db.get_conn() as conn:
        repo.add_beat(conn, game_id, "narrator", "Narrador", "narration", "INICIO " + "história " * 250 + " FIM", "crypt entrance", turn_index=2)
        repo.add_beat(conn, game_id, "narrator", "Narrador", "narration", "MESMO_TURNO", "crypt entrance", turn_index=2)
        repo.add_beat(conn, game_id, "narrator", "Narrador", "narration", "AGORA", "crypt entrance", turn_index=3)
        count_before = len(repo.all_beats(conn, game_id))
        retained = context.prepare_beats(conn, game_id, repo.recent_beats(conn, game_id, 1), 200)
        assert [beat["text"] for beat in retained] == ["AGORA"]
        assert repo.get_game(conn, game_id)["summarized_through"] == 2
        assert len(repo.all_beats(conn, game_id)) == count_before
    summary_calls = [call for call in fake_llm.calls if call["system"].startswith("You maintain the story recap")]
    assert len(summary_calls) > 1
    combined_source = "\n".join(call["user"] for call in summary_calls)
    assert "INICIO" in combined_source and "FIM" in combined_source and "MESMO_TURNO" in combined_source


def test_partial_summary_never_advances_cursor(client, fake_llm, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    fake_llm.summary = llm.LLMReply(content="Resumo incompleto", finish_reason="length")
    with db.get_conn() as conn:
        repo.add_beat(conn, game_id, "narrator", "Narrador", "narration", "ATUAL", "crypt entrance", turn_index=2)
    with pytest.raises(context.ContextLimitError), db.get_conn() as conn:
        context.prepare_beats(conn, game_id, repo.recent_beats(conn, game_id, 1), 100)
    with db.get_conn() as conn:
        assert repo.get_game(conn, game_id)["summarized_through"] == 0
        assert len(repo.all_beats(conn, game_id)) == 2


def test_interview_compacts_all_old_messages_and_preserves_original(monkeypatch):
    monkeypatch.setattr(settings, "LLM_CONTEXT_SIZE", 4000)
    monkeypatch.setattr(settings, "CONTEXT_FOLD_BATCH_TOKENS", 500)
    history = [{"role": "user" if index % 2 == 0 else "assistant", "content": f"DECISAO_{index} " + "mundo " * 150} for index in range(24)]
    with db.get_conn() as conn:
        creator._save(conn, "long-session", history)
    calls = []
    def compact_chat(messages, **keywords):
        calls.append(messages)
        return llm.LLMReply(content="- Magia custa lembranças. Tom sóbrio. Sem ressurreição.")
    monkeypatch.setattr(llm, "chat", compact_chat)
    summary, through = creator.compact_session_history("long-session", history)
    assert through > 0 and "lembranças" in summary
    assert len(calls) > 1
    for messages in calls:
        assert context.estimate_tokens(messages) < 3000
    with db.get_conn() as conn:
        assert creator.get_session(conn, "long-session") == history
        assert json.loads(conn.execute("SELECT history FROM creator_sessions WHERE id='long-session'").fetchone()["history"]) == history
    final_messages = prompts.build_creator_messages(history[through:], "Continuar", summary)
    assert context.estimate_tokens(final_messages) < 3000


def test_context_failure_is_recoverable_api_error(client, monkeypatch):
    def impossible(*arguments, **keywords):
        raise context.ContextLimitError("O histórico foi preservado.")
    monkeypatch.setattr(creator, "message", impossible)
    response = client.post("/create/message", json={"session_id": "limit", "message": "Olá"})
    assert response.status_code == 409
    assert "preservado" in response.json()["detail"]


def test_synchronous_fold_does_not_overwrite_newer_memory(client, fake_llm, world, monkeypatch):
    game_id = client.post("/games", json=world).json()["game_id"]
    with db.get_conn() as conn:
        repo.add_beat(conn, game_id, "narrator", "Narrador", "narration", "Atual", "crypt entrance", turn_index=3)
    with db.get_conn() as conn:
        def racing_summary(*arguments, **keywords):
            repo.set_story_summary(conn, game_id, "Memória concorrente mais recente", 2)
            return "Resumo antigo"
        monkeypatch.setattr(context, "summarize", racing_summary)
        with pytest.raises(context.ContextLimitError):
            context.prepare_beats(conn, game_id, repo.recent_beats(conn, game_id, 1), 100)
        assert repo.get_game(conn, game_id)["story_summary"] == "Memória concorrente mais recente"


def test_character_compaction_uses_only_witnessed_events(client, fake_llm, world):
    world["characters"].append({"name": "Breno", "persona": "Um guarda reservado."})
    game_id = client.post("/games", json=world).json()["game_id"]
    with db.get_conn() as conn:
        characters = repo.get_characters(conn, game_id)
        mara, breno = characters[0], characters[1]
        repo.add_beat(conn, game_id, "player", "Você", "dialogue", "SEGREDO_SO_DE_BRENO", "crypt entrance", turn_index=2, private_with=breno["id"])
        repo.add_beat(conn, game_id, "narrator", "Narrador", "narration", "Evento público", "crypt entrance", turn_index=3)
        repo.add_beat(conn, game_id, "narrator", "Narrador", "narration", "Agora", "crypt entrance", turn_index=4)
        recent = repo.witnessed_beats_for_character(conn, game_id, mara["id"], 1)
        context.prepare_beats(conn, game_id, recent, 100, character=mara)
    private_folds = [call for call in fake_llm.calls if call["system"].startswith("You maintain the private memory")]
    assert private_folds
    assert all("SEGREDO_SO_DE_BRENO" not in str(call["messages"]) for call in private_folds)


def test_legacy_finalize_uses_persisted_compact_history(client, fake_llm, world):
    history = [{"role": "user", "content": "PREFIXO_BRUTO_NAO_REENVIAR"}, {"role": "assistant", "content": "Recente [ready]"}]
    with db.get_conn() as conn:
        creator._save(conn, "finalize-compact", history)
        conn.execute("UPDATE creator_sessions SET summary=?, summarized_through=1 WHERE id=?", ("DECISAO_PRESERVADA", "finalize-compact"))
    fake_llm.finalize = llm.LLMReply(content="", tool_calls=[llm.ToolCall("save_world", world)])
    assert client.post("/create/finalize", json={"session_id": "finalize-compact"}).status_code == 200
    final_call = next(call for call in fake_llm.calls if "save_world" in call["names"])
    assert "DECISAO_PRESERVADA" in str(final_call["messages"])
    assert "PREFIXO_BRUTO_NAO_REENVIAR" not in str(final_call["messages"])
