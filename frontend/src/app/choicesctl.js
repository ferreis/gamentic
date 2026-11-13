import { api, state } from "./ctx.js";
import { render } from "./ui.js";

export async function loadActionChoices() {
  const game = state.active;
  if (!game?.state || game.generating || game.choicesLoading || game.state.actionChoices?.length) return;
  const previousState = game.state;
  game.choicesLoading = true;
  game.state.actionChoicesError = "";
  render();
  try {
    const response = await api.generateChoices(game.id);
    if (state.active !== game || game.generating || game.state !== previousState) return;
    game.state.actionChoices = response.action_choices || [];
    game.state.actionChoicesError = response.action_choices_error || "";
  } catch (error) {
    if (state.active === game && !game.generating && game.state === previousState) {
      game.state.actionChoicesError = error.message || "Não foi possível gerar as opções com a IA. Tente novamente.";
    }
  } finally {
    game.choicesLoading = false;
    if (state.active === game) render();
  }
}
