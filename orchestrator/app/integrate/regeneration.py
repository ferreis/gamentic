"""One background art regeneration per adventure, with progress and safe swaps."""
import logging
import threading
import time
import uuid

import httpx

from .. import db, media, repo
from . import events, image_catalog

_jobs: dict[str, dict] = {}
_lock = threading.Lock()
_log = logging.getLogger("gamentic.regeneration")


def status(game_id: str) -> dict:
    with _lock:
        return dict(_jobs.get(game_id, {"status": "idle", "total": 0, "completed": 0, "failed": 0, "skipped": 0}))


def reserve(game_id: str) -> tuple[dict, list[dict]]:
    with _lock:
        if _jobs.get(game_id, {}).get("status") == "running":
            raise ValueError("Já existe uma regeneração em andamento nesta aventura.")
        with db.get_conn() as connection:
            batches = image_catalog.collect_images(connection, game_id)
            main_image = repo.current_scene(connection, game_id)["image_url"]
        batches.sort(key=lambda batch: main_image not in batch["images"].values())
        individual_images = []
        scheduled_urls = set()
        for batch in batches:
            seed = uuid.uuid4().int % (2 ** 32)
            for image_field, previous_url in batch["images"].items():
                if previous_url in scheduled_urls:
                    continue
                scheduled_urls.add(previous_url)
                individual_images.append({**batch, "images": {image_field: previous_url},
                                          "view": image_field.removesuffix("_url"), "seed": seed})
        batches = individual_images
        total = len({image_url for batch in batches for image_url in batch["images"].values()})
        job = {"id": uuid.uuid4().hex, "status": "running" if total else "completed",
               "total": total, "completed": 0, "failed": 0, "skipped": 0,
               "started_at": time.time(), "current_image": "", "last_error": ""}
        _jobs[game_id] = job
        return dict(job), batches


def _progress(game_id: str, **changes) -> None:
    with _lock:
        _jobs[game_id].update(changes)
        current = dict(_jobs[game_id])
    events.publish(game_id, "image-regeneration", regeneration=current)


def _store_replacements(game_id: str, job_id: str, images: dict) -> int:
    """Download first, then take the write lock; a deleted game cannot be resurrected."""
    downloaded = {}
    for previous_url, generated_url in images.items():
        content = media.fetch_image_bytes(generated_url)
        if not content:
            raise ValueError("Não foi possível baixar uma imagem gerada.")
        filename = f"regen-{job_id}-{uuid.uuid4().hex}.png"
        next_url = f"/media/{game_id}/{filename}"
        downloaded[previous_url] = (next_url, content)
    written_paths = []
    unused_previous = []
    try:
        with db.get_conn() as connection:
            connection.execute("BEGIN IMMEDIATE")
            if not repo.get_game(connection, game_id):
                return 0
            replacements = {previous: replacement[0] for previous, replacement in downloaded.items()}
            changed = image_catalog.replace_references(connection, game_id, replacements)
            for previous_url in changed:
                next_url, content = downloaded[previous_url]
                image_path = image_catalog.owned_image_path(game_id, next_url)
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(content)
                written_paths.append(image_path)
                if not image_catalog.is_referenced(connection, previous_url):
                    unused_previous.append(previous_url)
    except Exception:
        for image_path in written_paths:
            image_path.unlink(missing_ok=True)
        raise
    for previous_url in unused_previous:
        image_path = image_catalog.owned_image_path(game_id, previous_url)
        if image_path:
            try:
                image_path.unlink(missing_ok=True)
            except OSError:
                _log.warning("Could not remove replaced image")
    return len(changed)


def run(game_id: str, batches: list[dict]) -> None:
    job = status(game_id)
    completed = failed = skipped = 0
    try:
        with db.get_conn() as connection:
            game = repo.get_game(connection, game_id)
            if not game:
                _progress(game_id, status="cancelled")
                return
            style = game["art_style"] or game["tone"] or ""
        for batch in batches:
            with db.get_conn() as connection:
                if not repo.get_game(connection, game_id):
                    _progress(game_id, status="cancelled")
                    return
            batch_size = len(set(batch["images"].values()))
            generated = None
            try:
                _progress(game_id, current_image=f"Imagem {completed + failed + skipped + 1} de {job['total']}")
                if batch["kind"] == "character":
                    generated = media.generate_character_view(batch["descriptor"], batch["view"], style=style, seed=batch["seed"])
                    if not generated or not generated.get("image_url"):
                        raise ValueError("A geração do retrato não foi concluída.")
                    replacements = {previous: generated["image_url"] for previous in batch["images"].values()}
                else:
                    previous_url = batch["images"]["image_url"]
                    prompt, width, height = image_catalog.image_recipe(game_id, previous_url, batch["prompt"])
                    generated = media.generate_scene_image(
                        f"RECREATE THESE SUBJECTS AND COMPOSITION: {prompt}",
                        width=width, height=height, style=style, raise_errors=True)
                    if not generated or not generated.get("image_url"):
                        raise ValueError("A geração da imagem não foi concluída.")
                    replacements = {previous_url: generated["image_url"]}
                updated = _store_replacements(game_id, job["id"], replacements)
                completed += updated
                skipped += batch_size - updated
            except Exception as error:
                failed += batch_size
                _log.exception("Image regeneration failed for %s", game_id)
                reason = str(error)
                if isinstance(error, httpx.HTTPStatusError):
                    try:
                        reason = str(error.response.json().get("detail") or error.response.status_code)
                    except (ValueError, AttributeError):
                        reason = f"O gerador respondeu com erro {error.response.status_code}."
                elif isinstance(error, httpx.TimeoutException):
                    reason = "O gerador ultrapassou o tempo de espera configurado. A imagem anterior foi mantida."
                _progress(game_id, last_error=reason[:400])
            finally:
                generated_urls = {generated.get(field) for field in (
                    "image_url", "face_url", "body_front_url", "body_side_url") if generated and generated.get(field)}
                with db.get_conn() as connection:
                    unused_generated = [image_url for image_url in generated_urls
                                        if not image_catalog.is_referenced(connection, image_url)]
                for image_url in unused_generated:
                    media.delete_staging_image(image_url)
            _progress(game_id, completed=completed, failed=failed, skipped=skipped)
        _progress(game_id, status="completed" if not failed else "partial", current_image="")
    except Exception:
        _log.exception("Image regeneration interrupted for %s", game_id)
        _progress(game_id, status="failed", completed=completed, failed=failed)
