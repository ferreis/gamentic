import json
from pathlib import Path

import pytest

from app import db, media, repo
from app.config import settings
from app.integrate import regeneration


@pytest.fixture(autouse=True)
def isolated_images(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "GAMES_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(settings, "IMAGE_ENABLED", True)
    monkeypatch.setattr(regeneration, "_jobs", {})
    monkeypatch.setattr(media, "generate_character_images", lambda *arguments, **options: None)
    monkeypatch.setattr(media, "generate_scene_image", lambda *arguments, **options: None)
    monkeypatch.setattr(media, "fetch_image_bytes", lambda image_url: b"replacement image")
    monkeypatch.setattr(media, "delete_staging_image", lambda image_url: None)


def attach_scene_image(game_id, filename="scene.png"):
    image_url = f"/media/{game_id}/{filename}"
    image_path = Path(settings.GAMES_DATA_DIR) / game_id / "images" / filename
    image_path.parent.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(b"original image")
    with db.get_conn() as connection:
        scene = repo.current_scene(connection, game_id)
        repo.set_scene_image(connection, scene["id"], image_url)
    return image_url, image_path


def test_regenerates_all_owners_including_shared_items_and_old_private_beats(client, world, monkeypatch):
    world["art_style"] = "Anime visual novel illustration"
    game_id = client.post("/games", json=world).json()["game_id"]
    original_scene_url, original_scene_path = attach_scene_image(game_id)
    item_url = f"/media/{game_id}/key.png"
    private_url = f"/media/{game_id}/private.png"
    with db.get_conn() as connection:
        character = repo.get_characters(connection, game_id)[0]
        character_id = character["id"]
        repo.set_character_images(connection, character_id, face_url=f"/media/{game_id}/face.png",
                                  body_front_url=f"/media/{game_id}/front.png", body_side_url=f"/media/{game_id}/side.png")
        inventory = [{"id": "key", "name": "Key", "description": "Brass", "qty": 7, "image_url": item_url}]
        connection.execute("UPDATE player_state SET inventory=? WHERE game_id=?", (json.dumps(inventory), game_id))
        repo.add_beat(connection, game_id, "system", None, "image", "A key was found.", world["start_location"], image_url=item_url)
        repo.add_beat(connection, game_id, character_id, character["name"], "image", "A private memory.", world["start_location"], image_url=private_url, private_with=character_id)
        before_beats = [dict(beat) for beat in repo.all_beats(connection, game_id, 0)]
        previous_game = dict(repo.get_game(connection, game_id))
    scene_requests = []

    def generate_scene(prompt, **options):
        scene_requests.append((prompt, options))
        return {"image_url": "/generated.png"}

    monkeypatch.setattr(media, "generate_scene_image", generate_scene)
    monkeypatch.setattr(media, "generate_character_images", lambda *arguments, **options: {
        "face_url": "/new-face", "body_front_url": "/new-front", "body_side_url": "/new-side"})
    response = client.post(f"/games/{game_id}/images/regenerate")
    assert response.status_code == 202
    progress = client.get(f"/games/{game_id}/images/regeneration").json()
    assert progress["status"] == "completed"
    assert progress["total"] == progress["completed"] == 6
    assert len(scene_requests) == 3  # scene, one shared item image, private memory
    assert all(options["style"] == world["art_style"] for prompt, options in scene_requests)
    with db.get_conn() as connection:
        assert dict(repo.get_game(connection, game_id)) == previous_game
        assert repo.current_scene(connection, game_id)["image_url"] != original_scene_url
        updated_inventory = json.loads(repo.get_player(connection, game_id)["inventory"])
        assert {key: entry for key, entry in updated_inventory[0].items() if key != "image_url"} == {
            "id": "key", "name": "Key", "description": "Brass", "qty": 7}
        after_beats = [dict(beat) for beat in repo.all_beats(connection, game_id, 0)]
        for before, after in zip(before_beats, after_beats):
            assert {key: entry for key, entry in before.items() if key != "image_url"} == {
                key: entry for key, entry in after.items() if key != "image_url"}
        item_beat = next(beat for beat in after_beats if beat["text"] == "A key was found.")
        assert item_beat["image_url"] == updated_inventory[0]["image_url"]
        assert not regeneration.image_catalog.is_referenced(connection, original_scene_url)
    assert not original_scene_path.exists()


def test_failure_keeps_the_original_image_and_counts_it(client, world):
    game_id = client.post("/games", json=world).json()["game_id"]
    previous_url, previous_path = attach_scene_image(game_id)
    response = client.post(f"/games/{game_id}/images/regenerate")
    assert response.status_code == 202
    progress = client.get(f"/games/{game_id}/images/regeneration").json()
    assert progress["status"] == "partial"
    assert progress["failed"] == 1 and progress["completed"] == 0
    with db.get_conn() as connection:
        assert repo.current_scene(connection, game_id)["image_url"] == previous_url
    assert previous_path.read_bytes() == b"original image"


def test_deleted_game_is_not_resurrected_by_late_image_generation(client, world, monkeypatch):
    import shutil
    game_id = client.post("/games", json=world).json()["game_id"]
    attach_scene_image(game_id)

    def delete_during_generation(*arguments, **options):
        with db.get_conn() as connection:
            repo.delete_game(connection, game_id)
        shutil.rmtree(Path(settings.GAMES_DATA_DIR) / game_id)
        return {"image_url": "/late.png"}

    monkeypatch.setattr(media, "generate_scene_image", delete_during_generation)
    assert client.post(f"/games/{game_id}/images/regenerate").status_code == 202
    assert not (Path(settings.GAMES_DATA_DIR) / game_id).exists()


def test_rejects_duplicate_job_disabled_images_and_unknown_game(client, world, monkeypatch):
    game_id = client.post("/games", json=world).json()["game_id"]
    attach_scene_image(game_id)
    regeneration.reserve(game_id)
    assert client.post(f"/games/{game_id}/images/regenerate").status_code == 409
    monkeypatch.setattr(settings, "IMAGE_ENABLED", False)
    assert client.post(f"/games/{game_id}/images/regenerate").status_code == 409
    assert client.get("/games/unknown/images/regeneration").status_code == 404


def test_references_in_other_adventures_are_not_changed_or_deleted(client, world, monkeypatch):
    first_game = client.post("/games", json=world).json()["game_id"]
    second_game = client.post("/games", json=world).json()["game_id"]
    previous_url, previous_path = attach_scene_image(first_game)
    with db.get_conn() as connection:
        second_scene = repo.current_scene(connection, second_game)
        repo.set_scene_image(connection, second_scene["id"], previous_url)
    monkeypatch.setattr(media, "generate_scene_image", lambda *arguments, **options: {"image_url": "/new.png"})
    client.post(f"/games/{first_game}/images/regenerate")
    with db.get_conn() as connection:
        assert repo.current_scene(connection, second_game)["image_url"] == previous_url
    assert previous_path.exists()


def test_item_moved_during_generation_keeps_its_new_owner_and_quantity(client, world, monkeypatch):
    game_id = client.post("/games", json=world).json()["game_id"]
    inventory = [{"id": "key", "name": "Key", "qty": 3, "image_url": f"/media/{game_id}/key.png"}]
    with db.get_conn() as connection:
        character_id = repo.get_characters(connection, game_id)[0]["id"]
        connection.execute("UPDATE player_state SET inventory=? WHERE game_id=?", (json.dumps(inventory), game_id))

    def move_during_generation(*arguments, **options):
        with db.get_conn() as connection:
            connection.execute("UPDATE player_state SET inventory='[]' WHERE game_id=?", (game_id,))
            connection.execute("UPDATE characters SET inventory=? WHERE id=?", (json.dumps(inventory), character_id))
        return {"image_url": "/new-key.png"}

    monkeypatch.setattr(media, "generate_scene_image", move_during_generation)
    assert client.post(f"/games/{game_id}/images/regenerate").status_code == 202
    with db.get_conn() as connection:
        assert json.loads(repo.get_player(connection, game_id)["inventory"]) == []
        moved = json.loads(repo.get_character(connection, character_id)["inventory"])[0]
        assert moved["qty"] == 3
        assert moved["image_url"] != inventory[0]["image_url"]
