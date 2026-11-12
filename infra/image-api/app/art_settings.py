"""Persistent local art controls, shared by every adventure using this service."""
import json
import logging
import math
import os
from pathlib import Path

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from . import config, workflow

router = APIRouter()
SETTINGS_PATH = Path(os.getenv("IMAGE_SETTINGS_PATH", "/srv/settings/art.json"))
WORKFLOWS = Path(__file__).resolve().parent.parent / "workflows"
CHECKPOINTS = {
    "sd_turbo.safetensors": {"label": "SD-Turbo · rápido", "family": "sd21", "workflow": "sd_turbo_api.json", "steps": 1},
    "animagine-xl-4.0-opt.safetensors": {"label": "Animagine XL 4 · anime", "family": "sdxl", "workflow": "anime_sdxl_api.json", "steps": 28},
    "LCM_AAM_AnyLoRA_AnimeMix.safetensors": {"label": "AnimeMix · anime leve", "family": "sd15", "workflow": "anime_lcm_api.json", "steps": 4},
}
LORAS = {
    "pixel-art-xl.safetensors": {"label": "Pixel art", "family": "sdxl", "prompt": "pixel art"},
    "papercut.safetensors": {"label": "Recorte de papel", "family": "sdxl", "prompt": "papercut"},
}


class LoraSetting(BaseModel):
    name: str
    strength: float = Field(default=0.7, ge=0, le=2, allow_inf_nan=False)


class ArtSettings(BaseModel):
    checkpoint: str = ""
    loras: list[LoraSetting] = Field(default_factory=list, max_length=8)


def current_settings() -> ArtSettings:
    if not SETTINGS_PATH.exists():
        return ArtSettings()
    try:
        return ArtSettings.model_validate_json(SETTINGS_PATH.read_text())
    except (ValueError, OSError) as error:
        raise HTTPException(503, "Não foi possível ler a configuração de arte salva.") from error


async def installed_models() -> tuple[list[str], list[str]]:
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(f"{config.COMFY_URL}/object_info")
            response.raise_for_status()
        node_info = response.json()
        checkpoints = node_info["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
        loras = node_info["LoraLoader"]["input"]["required"]["lora_name"][0]
        return checkpoints, loras
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as error:
        raise HTTPException(503, "Não foi possível consultar os modelos do ComfyUI.") from error


@router.get("/image/settings")
async def get_settings():
    checkpoints, loras = await installed_models()
    return {
        "settings": current_settings().model_dump(),
        "checkpoints": [{"name": name, **profile} for name, profile in CHECKPOINTS.items() if name in checkpoints],
        "loras": [{"name": name, **profile} for name, profile in LORAS.items() if name in loras],
        "scope": "global",
    }


@router.put("/image/settings")
async def save_settings(selection: ArtSettings):
    previous_selection = current_settings()
    checkpoints, loras = await installed_models()
    family = None
    if selection.checkpoint:
        if selection.checkpoint not in CHECKPOINTS or selection.checkpoint not in checkpoints:
            raise HTTPException(422, "Checkpoint indisponível ou sem workflow compatível.")
        family = CHECKPOINTS[selection.checkpoint]["family"]
    elif selection.loras:
        raise HTTPException(422, "Selecione um checkpoint antes de aplicar LoRAs.")
    for selected_lora in selection.loras:
        profile = LORAS.get(selected_lora.name)
        if not profile or selected_lora.name not in loras or profile["family"] != family:
            raise HTTPException(422, "LoRA ausente ou incompatível com o checkpoint.")
    if len({selected.name for selected in selection.loras}) != len(selection.loras):
        raise HTTPException(422, "Não repita a mesma LoRA.")
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        staging_path = SETTINGS_PATH.with_suffix(".tmp")
        staging_path.write_text(selection.model_dump_json())
        staging_path.replace(SETTINGS_PATH)
    except OSError as error:
        raise HTTPException(503, "Não foi possível salvar a configuração de arte.") from error
    if selection != previous_selection:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                response = await client.post(f"{config.COMFY_URL}/free", json={"unload_models": True, "free_memory": True})
                response.raise_for_status()
        except httpx.HTTPError as error:
            logging.getLogger(__name__).warning("Art settings saved; model cache release failed: %s", error)
    return {"settings": selection.model_dump()}


def render_settings(default_template: dict, default_steps: int, prompt: str) -> tuple[dict, int, str]:
    selection = current_settings()
    if not selection.checkpoint:
        return default_template, default_steps, prompt
    profile = CHECKPOINTS.get(selection.checkpoint)
    if profile is None:
        raise HTTPException(503, "O checkpoint salvo não tem workflow compatível.")
    template = workflow.apply_models(
        workflow.load_template(WORKFLOWS / profile["workflow"]), checkpoint_name=selection.checkpoint,
    )
    specifications = [selected.model_dump() for selected in selection.loras]
    template = workflow.apply_loras(template, json.dumps(specifications))
    style_prompts = [LORAS[selected.name]["prompt"] for selected in selection.loras if selected.strength > 0]
    return template, profile["steps"], ", ".join([*style_prompts, prompt])


def image_dimensions(width: int, height: int) -> tuple[int, int]:
    """Keep small SDXL images usable, preserving the requested aspect ratio."""
    selection = current_settings()
    profile = CHECKPOINTS.get(selection.checkpoint, {})
    if profile.get("family") != "sdxl" or min(width, height) >= 512:
        return width, height
    scale = min(512 / min(width, height), 1024 / max(width, height))
    return math.ceil(width * scale / 16) * 16, math.ceil(height * scale / 16) * 16
