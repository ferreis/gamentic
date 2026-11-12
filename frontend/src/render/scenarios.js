import { icon } from "../icons.js";
import { cardCorners, escapeHtml } from "./common.js";
import { modalShell } from "./widgets.js";

export function renderScenarioLibrary(scenarios, error) {
  return `<section class="library-section" aria-labelledby="scenarioHeading">
    <h2 id="scenarioHeading">Cenários</h2>
    <p class="modal-body">Regras iniciais do mundo. Use o mesmo cenário em várias aventuras independentes.</p>
    ${error ? `<p role="alert">${escapeHtml(error)}</p>` : ""}
    <div class="holo-grid">
      ${scenarios.map(scenario => `<article class="holo-card" data-scenario-id="${escapeHtml(scenario.id)}">
        ${cardCorners()}
        <h3 class="card-title">${escapeHtml(scenario.title)}</h3>
        <p class="card-meta">Cenário reutilizável</p>
        <div class="card-actions"><button class="holo-btn" data-act="select-scenario" data-scenario-id="${escapeHtml(scenario.id)}">
          ${icon("play")}<span>Nova aventura neste cenário</span>
        </button></div>
      </article>`).join("")}
      <button class="holo-card new-card" data-act="new-game">
        <span class="mini-dial">${icon("plus")}</span>
        <span class="card-title">Criar cenário</span>
        <span class="card-meta">Defina o mundo e suas regras</span>
      </button>
    </div>
  </section>`;
}

export function renderScenarioStart(selection) {
  const scenario = selection.scenario;
  return modalShell({
    overlayAct: "close-scenario",
    cls: "scenario-modal",
    title: scenario ? `Nova aventura: ${scenario.title}` : "Abrir cenário",
    titleIcon: "sparkles",
    body: `${selection.error ? `<p class="forge-error" role="alert">${escapeHtml(selection.error)}</p>` : ""}
      ${scenario ? `<p class="modal-body">Cada início cria uma aventura com histórico e progresso próprios.</p>
        <details class="scenario-rules"><summary>Ambientação e regras do cenário</summary>
          <p>${escapeHtml(scenario.setting)}</p><p>${escapeHtml(scenario.rules)}</p>
        </details>
        <form data-form="scenario-start">
          <label for="adventurePremise">Seu personagem e a situação inicial</label>
          <textarea id="adventurePremise" name="adventurePremise" class="holo-input" rows="4" maxlength="4000" required
            placeholder="Ex.: sou uma pessoa recém-chegada a este mundo, sem conhecer suas regras."
            ${selection.busy ? "disabled" : ""}>${escapeHtml(selection.premise)}</textarea>
          <div class="modal-actions">
            <button type="button" class="holo-btn" data-act="close-scenario" ${selection.busy ? "disabled" : ""}>Cancelar</button>
            <button type="submit" class="holo-btn primary" ${selection.busy ? "disabled" : ""}>
              ${icon("play")}<span>${selection.busy ? "Preparando aventura..." : "Iniciar aventura"}</span>
            </button>
          </div>
        </form>` : `<p role="status">${selection.error ? "Feche esta janela e tente novamente." : "Carregando cenário..."}</p>
          <button class="holo-btn" data-act="close-scenario">Fechar</button>`}`,
  });
}
