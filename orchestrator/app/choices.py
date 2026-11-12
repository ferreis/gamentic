"""Five optional next actions, proposed in the narrator's existing call."""
import json

from . import db


def save(conn, game_id: str, proposed_choices: list) -> bool:
    from . import repo
    if not isinstance(proposed_choices, list) or len(proposed_choices) != 5:
        return False
    accepted = []
    seen_texts = set()
    for candidate in proposed_choices:
        if not isinstance(candidate, dict):
            return False
        label = candidate.get("label")
        text = candidate.get("text")
        mode = candidate.get("mode")
        if not isinstance(label, str) or not isinstance(text, str) or mode not in ("do", "say"):
            return False
        label, text = label.strip(), text.strip()
        if not label or not text or len(label) > 160 or len(text) > 500 or text.casefold() in seen_texts:
            return False
        seen_texts.add(text.casefold())
        accepted.append({"label": label, "text": text, "mode": mode})
    payload = {"scene_id": repo.current_scene(conn, game_id)["id"], "choices": accepted}
    conn.execute("UPDATE games SET action_choices=? WHERE id=?", (json.dumps(payload), game_id))
    return True


def available(conn, game_id: str) -> list[dict]:
    from . import repo
    game = repo.get_game(conn, game_id)
    scene = repo.current_scene(conn, game_id)
    stored = db.loads(game["action_choices"], {})
    if isinstance(stored, dict) and stored.get("scene_id") == scene["id"]:
        proposed = stored.get("choices", [])
        if isinstance(proposed, list) and len(proposed) == 5 and all(
                isinstance(choice, dict) and choice.get("mode") in ("do", "say")
                and isinstance(choice.get("label"), str) and isinstance(choice.get("text"), str)
                and choice["label"].strip() and choice["text"].strip() for choice in proposed):
            return proposed
    # Models may omit optional tools. Fill from PLAYER-VISIBLE state without another call.
    suggested = []
    for exit_route in db.loads(scene["exits"], [])[:2]:
        suggested.append({"label": f"Seguir por {exit_route['label']}", "mode": "do",
                          "text": f"Seguir por {exit_route['label']} em direção a {exit_route['target']}."})
    for character in repo.present_characters(conn, game_id, scene["name"])[:2]:
        if character["alive"]:
            suggested.append({"label": f"Conversar com {character['name']}", "mode": "say",
                              "text": f"{character['name']}, o que você acha que devemos fazer agora?"})
    for visible_item in repo.visible_items(scene["items"])[:1]:
        suggested.append({"label": f"Examinar {visible_item['name']}", "mode": "do",
                          "text": f"Examinar {visible_item['name']} com atenção."})
    suggested.extend([
        {"label": "Observar os arredores", "mode": "do", "text": f"Observar com atenção os arredores de {scene['name']}."},
        {"label": "Procurar pistas", "mode": "do", "text": "Procurar detalhes ou marcas no terreno à minha volta."},
        {"label": "Ouvir o ambiente", "mode": "do", "text": "Ficar em silêncio por um instante e ouvir os sons ao redor."},
        {"label": "Conferir meus pertences", "mode": "do", "text": "Conferir meus pertences antes de continuar."},
        {"label": "Pensar no próximo passo", "mode": "do", "text": "Refletir sobre o que já descobri e decidir meu próximo passo."},
    ])
    return suggested[:5]
