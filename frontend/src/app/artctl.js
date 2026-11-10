// Regenerate existing adventure art; refresh historical images without replaying turns.
import { mapBeats, mapGameState, mapProfile, voiceForBeat } from "../adapters.js";
import { api, state } from "./ctx.js";
import { showToast } from "./cues.js";
import { render } from "./ui.js";

let progressTimer = null;
let progressOwner = null;

export function stopImageRegenerationWatch(game = null) {
  if (game && progressOwner !== game) return;
  if (progressTimer) clearTimeout(progressTimer);
  progressTimer = null;
  progressOwner = null;
}

async function refreshRegeneratedArt(game) {
  if (state.active !== game || game.generating) return false;
  const previousState = game.state;
  const profile = game.profile;
  const requests = [api.getState(game.id), api.getBeats(game.id)];
  if (profile) requests.push(api.characterProfile(game.id, profile.charId));
  const responses = await Promise.allSettled(requests);
  if (state.active !== game || game.generating || game.state !== previousState) return false;
  if (responses[0].status !== "fulfilled" || responses[1].status !== "fulfilled") return false;
  game.state = mapGameState(responses[0].value);
  const previousBeats = new Map(game.beats.map((beat) => [beat.id, beat]));
  game.beats = mapBeats(responses[1].value.beats || []).map((beat) => ({
    ...previousBeats.get(beat.id), ...beat, voiceId: voiceForBeat(beat, game.state),
  }));
  if (profile && game.profile === profile && responses[2].status === "fulfilled") {
    profile.data = mapProfile(responses[2].value);
  }
  if (!game.revealing || state.view === "settings") render();
  return true;
}

export async function loadImageRegeneration(game = state.active) {
  if (!game || state.active !== game || game.imageRegenerationLoading) return;
  game.imageRegenerationLoading = true;
  try {
    const previous = game.imageRegeneration;
    const progress = await api.imageRegenerationStatus(game.id);
    if (state.active !== game) return;
    if (game.imageRegeneration?.id !== previous?.id && progress.id !== game.imageRegeneration?.id) return;
    game.imageRegeneration = progress;
    game.imageRegenerationError = "";
    if (previous?.status === "running" && progress.status === "idle") {
      game.imageRegenerationError = "A regeneração foi interrompida. Você pode tentar novamente.";
      game.regeneratedArtOwed = true;
    }
    if (progress.completed && (progress.id !== previous?.id || progress.completed !== previous?.completed)) {
      game.regeneratedArtOwed = true;
    }
    if (game.regeneratedArtOwed) game.regeneratedArtOwed = !(await refreshRegeneratedArt(game));
    if (state.view === "settings" && (progress.status !== "idle" || previous?.status === "running")) render();
  } catch (error) {
    if (state.active === game) {
      game.imageRegenerationError = error.message || "Não foi possível consultar a geração de imagens.";
      if (state.view === "settings") render();
    }
  } finally {
    game.imageRegenerationLoading = false;
    stopImageRegenerationWatch(game);
    if (state.active === game && (game.imageRegeneration?.status === "running" || game.regeneratedArtOwed)) {
      progressOwner = game;
      progressTimer = setTimeout(() => loadImageRegeneration(game), 2500);
    }
  }
}

export async function regenerateAllImages() {
  const game = state.active;
  if (!game || !game.state || game.imageRegenerationStarting || game.imageRegeneration?.status === "running") return;
  game.imageRegenerationStarting = true;
  game.imageRegenerationError = "";
  render();
  try {
    const progress = await api.regenerateImages(game.id);
    if (state.active !== game) return;
    game.imageRegeneration = progress;
    showToast(progress.total ? "Regeneração iniciada. Você pode continuar jogando." : "Esta aventura ainda não tem imagens para regenerar.");
    await loadImageRegeneration(game);
  } catch (error) {
    if (state.active === game) {
      game.imageRegenerationError = error.message || "Não foi possível iniciar a regeneração.";
      showToast(game.imageRegenerationError);
      if (error.status === 409) await loadImageRegeneration(game);
    }
  } finally {
    game.imageRegenerationStarting = false;
    if (state.active === game) render();
  }
}
