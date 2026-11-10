"""Find image owners and replace their URLs without changing adventure content."""
import json
import struct
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .. import db, repo
from ..config import settings
from . import image_prompts

IMAGE_COLUMNS = {
    "scenes": ("image_url",),
    "characters": ("face_url", "body_front_url", "body_side_url"),
    "beats": ("image_url",),
}
ITEM_COLUMNS = {"scenes": "items", "characters": "inventory", "player_state": "inventory"}


def owned_image_path(game_id: str, image_url: str) -> Path | None:
    path = unquote(urlsplit(image_url).path)
    prefix = f"/media/{game_id}/"
    if not path.startswith(prefix):
        return None
    directory = (Path(settings.GAMES_DATA_DIR) / game_id / "images").resolve()
    image_path = (directory / path[len(prefix):]).resolve()
    return image_path if image_path.parent == directory else None


def image_recipe(game_id: str, image_url: str, fallback: str) -> tuple[str, int, int]:
    """Recover historical composition from our PNG, with a caption fallback for imports."""
    width, height = settings.IMAGE_SCENE_W, settings.IMAGE_SCENE_H
    image_path = owned_image_path(game_id, image_url)
    if image_path is None or not image_path.is_file():
        return fallback, width, height
    try:
        with image_path.open("rb") as image_file:
            if image_file.read(8) != b"\x89PNG\r\n\x1a\n":
                return fallback, width, height
            for chunk_index in range(100):
                header = image_file.read(8)
                if len(header) != 8:
                    break
                length, chunk_type = struct.unpack(">I4s", header)
                if length > 1024 * 1024:
                    image_file.seek(length + 4, 1)
                    continue
                payload = image_file.read(length)
                image_file.read(4)
                if chunk_type == b"IHDR":
                    width, height = struct.unpack(">II", payload[:8])
                if chunk_type == b"tEXt" and payload.startswith(b"prompt\x00"):
                    graph = json.loads(payload.split(b"\x00", 1)[1])
                    for node in graph.values():
                        if node.get("_meta", {}).get("title") == "Positive Prompt":
                            return node["inputs"]["text"], width, height
    except (OSError, ValueError, KeyError, TypeError, struct.error):
        pass
    return fallback, width, height


def collect_images(connection, game_id: str) -> list[dict]:
    """Snapshot every referenced image, including old scenes and private image beats."""
    batches = []
    seen_urls = set()

    def add_single(image_url, prompt):
        if image_url and image_url not in seen_urls:
            seen_urls.add(image_url)
            batches.append({"kind": "image", "images": {"image_url": image_url}, "prompt": prompt})

    for character in repo.get_characters(connection, game_id):
        images = {field: character[field] for field in IMAGE_COLUMNS["characters"]
                  if character[field] and character[field] not in seen_urls}
        if images:
            seen_urls.update(images.values())
            batches.append({"kind": "character", "images": images,
                            "descriptor": image_prompts.character_descriptor(character)})
    scenes = connection.execute("SELECT * FROM scenes WHERE game_id=?", (game_id,)).fetchall()
    for scene in scenes:
        add_single(scene["image_url"], image_prompts.scene_prompt(scene, ""))
    for table, column in ITEM_COLUMNS.items():
        for owner in connection.execute(f"SELECT {column} FROM {table} WHERE game_id=?", (game_id,)):
            for entry in db.loads(owner[column], []):
                add_single(entry.get("image_url"), image_prompts.item_prompt(
                    entry.get("name", "object"), entry.get("description", ""), ""))
    for beat in connection.execute("SELECT image_url, text FROM beats WHERE game_id=?", (game_id,)):
        add_single(beat["image_url"], beat["text"] or "Illustration of this story moment")
    return batches


def _replace_item_urls(entries: list, replacements: dict) -> bool:
    changed = False
    for entry in entries:
        if entry.get("image_url") in replacements:
            entry["image_url"] = replacements[entry["image_url"]]
            changed = True
    return changed


def replace_references(connection, game_id: str, replacements: dict) -> set[str]:
    """Update all owners together; items may have moved during generation."""
    replaced_urls = set()
    for table, columns in IMAGE_COLUMNS.items():
        for column in columns:
            for previous_url, next_url in replacements.items():
                result = connection.execute(
                    f"UPDATE {table} SET {column}=? WHERE game_id=? AND {column}=?",
                    (next_url, game_id, previous_url))
                if result.rowcount:
                    replaced_urls.add(previous_url)
    for table, column in ITEM_COLUMNS.items():
        owner_key = "game_id" if table == "player_state" else "id"
        owners = connection.execute(f"SELECT {owner_key}, {column} FROM {table} WHERE game_id=?", (game_id,)).fetchall()
        for owner in owners:
            entries = db.loads(owner[column], [])
            present_urls = {entry.get("image_url") for entry in entries} & replacements.keys()
            if _replace_item_urls(entries, replacements):
                connection.execute(f"UPDATE {table} SET {column}=? WHERE {owner_key}=?",
                                   (json.dumps(entries, ensure_ascii=False), owner[owner_key]))
                replaced_urls.update(present_urls)
    return replaced_urls


def is_referenced(connection, image_url: str) -> bool:
    for table, columns in IMAGE_COLUMNS.items():
        for column in columns:
            if connection.execute(f"SELECT 1 FROM {table} WHERE {column}=? LIMIT 1", (image_url,)).fetchone():
                return True
    for table, column in ITEM_COLUMNS.items():
        if connection.execute(f"SELECT 1 FROM {table} WHERE instr({column}, ?) > 0 LIMIT 1", (image_url,)).fetchone():
            return True
    return False
