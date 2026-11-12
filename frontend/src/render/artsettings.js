import { escapeHtml } from "./common.js";

export function renderArtSettings(game) {
  const controls = game.artControls;
  const selection = game.artSelection;
  const saving = game.artSettingsSaving;
  if (!controls || !selection) return `<p class="set-note" role="status">${escapeHtml(game.artSettingsError || "Consultando checkpoints e LoRAs...")}</p>`;
  const family = controls.checkpoints.find((checkpoint) => checkpoint.name === selection.checkpoint)?.family;
  const availableLoras = controls.loras.filter((lora) => lora.family === family);
  return `<div class="art-model-settings">
    <p class="set-note">Configuração compartilhada por todas as aventuras. Vale para as próximas imagens.</p>
    <label class="set-label">Checkpoint (modelo base)
      <select class="holo-input" data-art-setting="checkpoint" ${saving ? "disabled" : ""}>
        <option value="">Padrão do servidor</option>
        ${controls.checkpoints.map((checkpoint) => `<option value="${escapeHtml(checkpoint.name)}" ${checkpoint.name === selection.checkpoint ? "selected" : ""}>${escapeHtml(checkpoint.label)}</option>`).join("")}
      </select>
    </label>
    <p class="set-note">LoRAs de estilo: ative uma ou combine várias. Intensidade de 0 a 2.</p>
    ${family === "sdxl" ? `<p class="set-note">Animagine usa 28 passos. Na CPU, pode levar alguns minutos. AnimeMix é a opção mais leve.</p>` : ""}
    ${availableLoras.map((lora) => {
      const selected = selection.loras.find((candidate) => candidate.name === lora.name);
      return `<div class="set-row">
        <label><input type="checkbox" data-art-setting="lora" data-lora-name="${escapeHtml(lora.name)}" ${selected ? "checked" : ""} ${saving ? "disabled" : ""}> ${escapeHtml(lora.label)}</label>
        ${selected ? `<label class="set-label">Intensidade de ${escapeHtml(lora.label)} <input class="holo-input" type="number" min="0" max="2" step="0.1" value="${selected.strength}" data-art-setting="strength" data-lora-name="${escapeHtml(lora.name)}" ${saving ? "disabled" : ""}></label>` : ""}
      </div>`;
    }).join("")}
    ${!availableLoras.length ? `<p class="set-note">Nenhuma LoRA de estilo compatível instalada para este checkpoint.</p>` : ""}
    <button type="button" class="holo-btn" data-act="save-art-settings" ${saving ? "disabled" : ""}>${saving ? "Salvando..." : "Salvar configuração de arte"}</button>
    <p class="set-note" role="status">${escapeHtml(game.artSettingsError || game.artSettingsMessage || "")}</p>
  </div>`;
}
