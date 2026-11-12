import { api, state } from "./ctx.js";
import { render } from "./ui.js";

export async function loadArtSettings() {
  const game = state.active;
  if (!game || game.artSettingsLoading) return;
  game.artSettingsLoading = true;
  game.artSettingsError = "";
  try {
    const response = await api.artSettings();
    game.artControls = response;
    game.artSelection = structuredClone(response.settings);
  } catch (error) {
    game.artSettingsError = error.message || "Não foi possível consultar os modelos.";
  } finally {
    game.artSettingsLoading = false;
    if (state.active === game && state.view === "settings") render();
  }
}

export function changeArtSetting(element) {
  const game = state.active;
  if (!game?.artSelection || game.artSettingsSaving) return;
  if (element.dataset.artSetting === "checkpoint") {
    game.artSelection.checkpoint = element.value;
    const family = game.artControls.checkpoints.find((checkpoint) => checkpoint.name === element.value)?.family;
    game.artSelection.loras = game.artSelection.loras.filter((selected) =>
      game.artControls.loras.some((available) => available.name === selected.name && available.family === family));
  } else {
    const loraName = element.dataset.loraName;
    const selected = game.artSelection.loras.find((lora) => lora.name === loraName);
    if (element.type === "checkbox") {
      game.artSelection.loras = game.artSelection.loras.filter((lora) => lora.name !== loraName);
      if (element.checked) game.artSelection.loras.push({ name: loraName, strength: 0.7 });
    } else if (selected) {
      const strength = Number(element.value);
      if (!Number.isFinite(strength) || strength < 0 || strength > 2) return;
      selected.strength = strength;
    }
  }
  game.artSettingsMessage = "";
  render();
}

export async function saveArtSettings() {
  const game = state.active;
  if (!game?.artSelection || game.artSettingsSaving) return;
  game.artSettingsSaving = true;
  game.artSettingsError = "";
  render();
  try {
    const response = await api.saveArtSettings(game.artSelection);
    game.artSelection = structuredClone(response.settings);
    game.artSettingsMessage = "Arte salva. As próximas imagens usarão esta configuração.";
  } catch (error) {
    game.artSettingsError = error.message || "Não foi possível salvar a arte.";
  } finally {
    game.artSettingsSaving = false;
    if (state.active === game && state.view === "settings") render();
  }
}
