"""Install image models from pinned upstream URLs, preserving valid local weights."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = Path(__file__).with_name("manifest.json")


def read_environment(configuration_file: Path) -> dict[str, str]:
    configuration = {}
    if configuration_file.is_file():
        for line in configuration_file.read_text(encoding="utf-8").splitlines():
            stripped_line = line.strip()
            if not stripped_line or stripped_line.startswith("#") or "=" not in stripped_line:
                continue
            setting_name, setting_content = stripped_line.removeprefix("export ").split("=", 1)
            configuration[setting_name.strip()] = setting_content.strip().strip("\"'")
    configuration.update(os.environ)
    return configuration


def matches_model(model_path: Path, specification: dict) -> bool:
    if not model_path.is_file() or model_path.stat().st_size != specification["size"]:
        return False
    with model_path.open("rb") as model_file:
        return hashlib.file_digest(model_file, "sha256").hexdigest() == specification["sha256"]


def install_model(models_directory: Path, specification: dict) -> None:
    model_path = (models_directory / specification["path"]).resolve()
    if not model_path.is_relative_to(models_directory.resolve()):
        raise ValueError("Caminho de modelo fora da pasta configurada.")
    if matches_model(model_path, specification):
        print(f"[pronto] {specification['path']}", flush=True)
        return
    model_path.parent.mkdir(parents=True, exist_ok=True)
    pending_path = model_path.with_name(model_path.name + ".part")
    if pending_path.exists() and pending_path.stat().st_size >= specification["size"]:
        if matches_model(pending_path, specification):
            pending_path.replace(model_path)
            return
        pending_path.unlink()
    print(f"[baixando] {specification['path']}", flush=True)
    subprocess.run([
        "curl", "--fail", "--location", "--retry", "3", "--continue-at", "-",
        "--output", str(pending_path), specification["url"],
    ], check=True)
    if not matches_model(pending_path, specification):
        raise ValueError(f"Tamanho ou SHA-256 não confere: {specification['path']}. O modelo anterior foi preservado.")
    pending_path.replace(model_path)
    print(f"[instalado] {specification['path']}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--models-dir", type=Path)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--workflow", default="")
    arguments = parser.parse_args()
    try:
        configuration = read_environment(arguments.env_file)
        models_directory = arguments.models_dir or Path(configuration.get("COMFY_MODELS_DIR") or "models/comfyui")
        if not models_directory.is_absolute():
            models_directory = ROOT / models_directory
        manifest = json.loads(arguments.manifest.read_text(encoding="utf-8"))
        if manifest.get("version") != 1:
            raise ValueError("Versão de catálogo não suportada.")
        for specification in manifest["models"]:
            install_model(models_directory, specification)
        if Path(arguments.workflow).name == "flux2_klein_api.json":
            subprocess.run(
                ["bash", str(ROOT / "infra/comfyui/fetch-models.sh"), str(models_directory)],
                env={**configuration, "ENV_FILE": str(arguments.env_file.resolve())}, check=True,
            )
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"Erro ao instalar modelos: {error}\n")


if __name__ == "__main__":
    main()
