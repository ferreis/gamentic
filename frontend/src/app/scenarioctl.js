import { api, root, state } from "./ctx.js";
import { openGame } from "./game.js";
import { render } from "./ui.js";

export async function selectScenario(scenarioId) {
  const selection = { id: scenarioId, scenario: null, premise: "", busy: false, error: "" };
  state.scenarioStart = selection;
  render();
  try {
    selection.scenario = await api.getScenario(scenarioId);
  } catch (error) {
    selection.error = error.message || "Não foi possível abrir o cenário.";
  }
  if (state.scenarioStart === selection) {
    render();
    root.querySelector('[name="adventurePremise"]')?.focus();
  }
}

export function closeScenario() {
  if (state.scenarioStart?.busy) return;
  state.scenarioStart = null;
  render();
}

export async function startScenarioAdventure() {
  const selection = state.scenarioStart;
  if (!selection?.scenario || selection.busy || !selection.premise.trim()) return;
  selection.busy = true;
  selection.error = "";
  render();
  try {
    const result = await api.startScenario(selection.id, selection.premise.trim());
    state.scenarioStart = null;
    await openGame(result.game_id);
  } catch (error) {
    selection.busy = false;
    selection.error = error.message || "Não foi possível iniciar a aventura. Tente novamente.";
    render();
  }
}
