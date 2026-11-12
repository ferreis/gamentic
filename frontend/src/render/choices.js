import { escapeHtml } from "./common.js";

export function renderTurnChoices(game, locked) {
  const choices = game.state?.actionChoices || [];
  if (!choices.length || locked || game.revealing) return "";
  return `<section class="turn-choices" aria-labelledby="turnChoicesHeading">
    <h2 id="turnChoicesHeading">O que você quer fazer ou dizer?</h2>
    <p>Escolha uma opção ou escreva livremente no campo abaixo.</p>
    <ol>${choices.map((choice, choiceIndex) => `<li>
      <button type="button" class="turn-choice" data-act="choose-action" data-choice-index="${choiceIndex}" title="${escapeHtml(choice.text)}">
        <span class="choice-mode">${choice.mode === "say" ? "Dizer" : "Fazer"}</span>
        <span>${escapeHtml(choice.label)}</span>
      </button>
    </li>`).join("")}</ol>
  </section>`;
}
