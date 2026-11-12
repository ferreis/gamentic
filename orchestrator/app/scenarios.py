"""Reusable world blueprints, kept separate from every playable adventure."""
import json
from copy import deepcopy
from uuid import uuid4

from . import creator, db, llm, prompts
from .config import settings
from .models import ScenarioSheet, WorldSheet


SCENARIO_TOOL = [{"type": "function", "function": {
    "name": "save_scenario",
    "description": "Save only the reusable world's initial setting and rules, without starting an adventure.",
    "parameters": ScenarioSheet.model_json_schema(),
}}]

# World rules already exist. Generate only the new adventure's opening state.
START_TOOL = deepcopy(prompts.FINALIZE_TOOL)
for canonical_field in ("setting", "tone", "art_style", "narrator_persona"):
    START_TOOL[0]["function"]["parameters"]["properties"].pop(canonical_field, None)


def save(conn, sheet: ScenarioSheet, source_session_id: str | None = None) -> str:
    scenario_id = uuid4().hex[:12]
    conn.execute("INSERT INTO scenarios (id,title,sheet,source_session_id) VALUES (?,?,?,?)",
                 (scenario_id, sheet.title, sheet.model_dump_json(), source_session_id))
    return scenario_id


def get(conn, scenario_id: str) -> dict | None:
    record = conn.execute("SELECT * FROM scenarios WHERE id=?", (scenario_id,)).fetchone()
    if not record:
        return None
    return {**json.loads(record["sheet"]), "id": record["id"], "created_at": record["created_at"]}


def list_scenarios(conn) -> list[dict]:
    return [dict(record) for record in conn.execute(
        "SELECT id,title,created_at FROM scenarios ORDER BY created_at DESC, rowid DESC")]


def _extraction_messages(history: list[dict], summary: str) -> list[dict]:
    transcript = "\n".join(f"{entry['role'].upper()}: {entry['content']}" for entry in history)
    return [
        {"role": "system", "content": prompts.render("scenario.system.md")},
        {"role": "user", "content": f"DECISÕES ANTERIORES:\n{summary}\n\nENTREVISTA:\n{transcript}"},
    ]


def finalize(session_id: str) -> str:
    # A network retry after success returns the same blueprint without another model call.
    with db.get_conn() as conn:
        existing = conn.execute("SELECT id FROM scenarios WHERE source_session_id=?", (session_id,)).fetchone()
        if existing:
            return existing["id"]
        history = creator.get_session(conn, session_id)
    if not history:
        raise ValueError("A conversa de criação não foi encontrada.")
    last_reply = next((entry["content"] for entry in reversed(history) if entry["role"] == "assistant"), "")
    if not creator.is_ready(last_reply):
        raise ValueError("Conclua as regras do cenário com o criador antes de salvar.")
    summary, through = creator.compact_session_history(session_id, history, _extraction_messages, SCENARIO_TOOL)
    reply = llm.chat(_extraction_messages(history[through:], summary), tools=SCENARIO_TOOL,
                     max_tokens=min(settings.WORLD_MAX_TOKENS, settings.LLM_MAX_TOKENS), thinking=False)
    call = next((call for call in reply.tool_calls if call.name == "save_scenario"), None)
    if not call or reply.finish_reason == "length":
        raise ValueError("O cenário não foi concluído. A conversa foi preservada; tente novamente.")
    sheet = ScenarioSheet(**call.arguments)
    with db.get_conn() as conn:
        existing = conn.execute("SELECT id FROM scenarios WHERE source_session_id=?", (session_id,)).fetchone()
        if existing:
            return existing["id"]
        scenario_id = save(conn, sheet, session_id)
        conn.execute("DELETE FROM creator_sessions WHERE id=?", (session_id,))
    return scenario_id


def adventure_sheet(scenario: dict, premise: str) -> WorldSheet:
    messages = [
        {"role": "system", "content": prompts.render("finalize.system.md") + "\n\n" + prompts.render("scenario.start.md")},
        {"role": "user", "content": json.dumps({"scenario": scenario, "adventure_premise": premise}, ensure_ascii=False)},
    ]
    reply = llm.chat(messages, tools=START_TOOL,
                     max_tokens=min(settings.WORLD_MAX_TOKENS, settings.LLM_MAX_TOKENS), thinking=False)
    call = next((call for call in reply.tool_calls if call.name == "save_world"), None)
    if not call or reply.finish_reason == "length":
        raise ValueError("A aventura não foi concluída. O cenário continua salvo; tente novamente.")
    sheet = WorldSheet(**call.arguments)
    # Canonical world rules always come from the saved blueprint, never from a played save.
    sheet.setting = (f"{scenario['setting']}\n\nREGRAS FIXAS DO CENÁRIO:\n{scenario['rules']}"
                     f"\n\nPERSONAGEM E PREMISSA DESTA AVENTURA:\n{premise}")
    sheet.tone = scenario["tone"]
    sheet.art_style = scenario["art_style"]
    sheet.narrator_persona = scenario["narrator_persona"] or sheet.narrator_persona
    return sheet
