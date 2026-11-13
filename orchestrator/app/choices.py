"""A dedicated AI proposes next actions from player-visible events after each turn."""
import json
import logging

from . import db, llm

_log = logging.getLogger("gamentic.choices")
CHOICES_TOOL = [{"type": "function", "function": {
    "name": "suggest_actions",
    "description": "Offer exactly five distinct next actions or spoken replies for the player after this turn. Use only facts the player has discovered. Suggestions never execute actions. Include alternatives with different intentions; never expose secrets or guarantee success.",
    "parameters": {"type": "object", "properties": {
        "choices": {"type": "array", "minItems": 5, "maxItems": 5, "items": {
            "type": "object", "properties": {
                "label": {"type": "string", "maxLength": 160},
                "text": {"type": "string", "maxLength": 500},
                "mode": {"type": "string", "enum": ["do", "say"]},
            }, "required": ["label", "text", "mode"]}},
    }, "required": ["choices"]}}}]

GENERATION_ERROR = "Não foi possível gerar as opções com a IA. Tente novamente ou escreva sua própria ação ou fala."


def save(conn, game_id: str, proposed_choices: list) -> bool:
    from . import repo
    if not isinstance(proposed_choices, list) or len(proposed_choices) != 5:
        return False
    accepted = []
    seen_texts = set()
    seen_labels = set()
    for candidate in proposed_choices:
        if not isinstance(candidate, dict):
            return False
        label = candidate.get("label")
        text = candidate.get("text")
        mode = candidate.get("mode")
        if not isinstance(label, str) or not isinstance(text, str) or mode not in ("do", "say"):
            return False
        label, text = label.strip(), text.strip()
        if (not label or not text or len(label) > 160 or len(text) > 500
                or text.casefold() in seen_texts or label.casefold() in seen_labels):
            return False
        seen_texts.add(text.casefold())
        seen_labels.add(label.casefold())
        accepted.append({"label": label, "text": text, "mode": mode})
    payload = {"scene_id": repo.current_scene(conn, game_id)["id"], "turn_index": story_version(conn, game_id),
               "source": "ai", "choices": accepted}
    conn.execute("UPDATE games SET action_choices=? WHERE id=?", (json.dumps(payload), game_id))
    return True


def available(conn, game_id: str) -> list[dict]:
    from . import repo
    game = repo.get_game(conn, game_id)
    scene = repo.current_scene(conn, game_id)
    stored = db.loads(game["action_choices"], {})
    if (isinstance(stored, dict) and stored.get("source") == "ai"
            and stored.get("scene_id") == scene["id"] and stored.get("turn_index") == story_version(conn, game_id)):
        proposed = stored.get("choices", [])
        if isinstance(proposed, list) and len(proposed) == 5 and all(
                isinstance(choice, dict) and choice.get("mode") in ("do", "say")
                and isinstance(choice.get("label"), str) and isinstance(choice.get("text"), str)
                and choice["label"].strip() and choice["text"].strip() for choice in proposed):
            return proposed
    return []


def story_version(conn, game_id: str) -> int:
    return conn.execute("SELECT COALESCE(MAX(turn_index),0) FROM beats WHERE game_id=? AND kind!='image'",
                        (game_id,)).fetchone()[0]


def generation_error(conn, game_id: str) -> str:
    from . import repo
    stored = db.loads(repo.get_game(conn, game_id)["action_choices"], {})
    return stored.get("error", "") if isinstance(stored, dict) and stored.get("turn_index") == story_version(conn, game_id) else ""


def _messages(conn, game_id: str) -> list[dict]:
    from . import prompts, repo
    scene = repo.current_scene(conn, game_id)
    player = repo.get_player(conn, game_id)
    public_beats = conn.execute(
        "SELECT speaker_name,kind,text FROM beats WHERE game_id=? AND private_with IS NULL AND kind!='image' "
        "ORDER BY turn_index DESC,seq DESC LIMIT 12", (game_id,)).fetchall()
    context = {
        "location": scene["name"], "scene_description": (scene["description"] or "")[:1200],
        "visible_items": [{"name": visible_item["name"], "description": (visible_item.get("description") or "")[:240]}
                          for visible_item in repo.visible_items(scene["items"])],
        "known_exits": db.loads(scene["exits"], []),
        "present_characters": [{"name": character["name"], "description": (character["description"] or "")[:240]}
                               for character in repo.present_characters(conn, game_id, player["location"]) if character["alive"]],
        "player_inventory": [{"name": possession["name"], "description": (possession.get("description") or "")[:240]}
                             for possession in repo.visible_items(player["inventory"])],
        "player_life": player["life"],
        "current_goal": (repo.get_game(conn, game_id)["current_goal"] or "")[:500],
        "recent_public_events": [{"speaker": beat["speaker_name"], "kind": beat["kind"], "text": (beat["text"] or "")[-1200:]}
                                 for beat in reversed(public_beats)],
    }
    return [{"role": "system", "content": prompts.render("choices.system.md")},
            {"role": "user", "content": "ESTADO VISÍVEL AO JOGADOR E FIM DO TURNO:\n" + json.dumps(context, ensure_ascii=False)}]


def generate(conn, game_id: str, cancel=None) -> list[dict]:
    """Generate once per story version; no canned actions and no calls during GET /state."""
    from . import repo
    cached = available(conn, game_id)
    if cached:
        return cached
    version = story_version(conn, game_id)
    scene_id = repo.current_scene(conn, game_id)["id"]
    proposed = None
    try:
        reply = llm.chat(_messages(conn, game_id), tools=CHOICES_TOOL, max_tokens=1200,
                         thinking=False, cancel=cancel)
        if reply.finish_reason != "length":
            call = next((call for call in reply.tool_calls if call.name == "suggest_actions"), None)
            if call:
                proposed = call.arguments.get("choices")
            elif reply.content:
                from .engine.parsing import _strip_think
                raw = _strip_think(reply.content).strip()
                if raw.startswith("```"):
                    raw = "\n".join(raw.splitlines()[1:-1]).strip()
                decoded = json.loads(raw)
                proposed = decoded.get("choices") if isinstance(decoded, dict) else decoded
    except llm.LLMCancelled:
        raise
    except Exception:
        _log.exception("AI choice generation failed for %s", game_id)
    # An initial-page request may overlap a turn. Never overwrite newer suggestions.
    if not conn.in_transaction:
        conn.execute("BEGIN IMMEDIATE")
    if story_version(conn, game_id) != version or repo.current_scene(conn, game_id)["id"] != scene_id:
        return available(conn, game_id)
    cached = available(conn, game_id)
    if cached:
        return cached
    if save(conn, game_id, proposed):
        return available(conn, game_id)
    payload = {"scene_id": scene_id, "turn_index": version, "choices": [], "error": GENERATION_ERROR}
    conn.execute("UPDATE games SET action_choices=? WHERE id=?", (json.dumps(payload), game_id))
    return []
