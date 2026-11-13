import { escapeHtml } from "./common.js";
import { modalShell } from "./widgets.js";

export function renderTurnChoices(game, locked, inDialog = false) {
  const choices = game.state?.actionChoices || [];
  if (locked || game.revealing) return "";
  if (!choices.length) {
    return `<section class="turn-choices choices-feedback" aria-label="Opções da IA">
      ${game.choicesLoading ? '<p role="status">A IA está preparando cinco opções para este momento da aventura...</p>' : `
        ${game.state?.actionChoicesError ? `<p role="alert">${escapeHtml(game.state.actionChoicesError)}</p>` : ""}
        <button type="button" class="holo-btn" data-act="generate-choices">Gerar cinco opções com IA</button>`}
      <p>Você pode continuar escrevendo livremente no campo abaixo.</p>
    </section>`;
  }
  const headingId = inDialog ? "choicePickerHeading" : "turnChoicesHeading";
  return `<section class="turn-choices${inDialog ? " in-dialog" : ""}" aria-labelledby="${headingId}">
    <h2 id="${headingId}">O que você quer fazer ou dizer?</h2>
    <p>${inDialog ? "Escolha uma opção ou use o botão para escrever livremente." : "Escolha uma opção ou escreva livremente no campo abaixo."}</p>
    <ol>${choices.map((choice, choiceIndex) => `<li>
      <button type="button" class="turn-choice" data-act="choose-action" data-choice-index="${choiceIndex}" title="${escapeHtml(choice.text)}">
        <span class="choice-mode">${choice.mode === "say" ? "Dizer" : "Fazer"}</span>
        <span>${escapeHtml(choice.label)}</span>
      </button>
    </li>`).join("")}</ol>
  </section>`;
}

export function renderChoicePicker(game) {
  if (!game.choicePickerOpen || game.generating) return "";
  return modalShell({
    overlayAct: "close-choice-picker",
    cls: "choice-picker",
    title: "Escolha seu próximo passo",
    body: renderTurnChoices(game, false, true),
    actions: '<button type="button" class="holo-btn" data-act="close-choice-picker">Escrever minha ação ou fala</button>',
  });
}
