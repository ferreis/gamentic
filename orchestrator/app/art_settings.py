"""Forward local image controls through the same origin as the game API."""
import httpx
from fastapi import APIRouter, HTTPException

from .providers import resolve

router = APIRouter()


async def forward_settings(method: str, payload: dict | None = None):
    provider = resolve("image")
    if provider.provider != "comfy":
        raise HTTPException(409, "Checkpoint e LoRAs estão disponíveis somente no ComfyUI local.")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.request(method, f"{provider.base_url.rstrip('/')}/image/settings", json=payload)
        if response.is_error:
            raise HTTPException(response.status_code, response.json().get("detail", "Falha na configuração de arte."))
        return response.json()
    except (httpx.HTTPError, ValueError) as error:
        raise HTTPException(503, "O serviço local de imagens está indisponível.") from error


@router.get("/images/settings")
async def get_art_settings():
    return await forward_settings("GET")


@router.put("/images/settings")
async def save_art_settings(payload: dict):
    return await forward_settings("PUT", payload)
