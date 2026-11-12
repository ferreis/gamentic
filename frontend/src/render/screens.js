// The non-play screens: menu, library (delete/export/import), creator, settings.

import { icon } from "../icons.js";
import { renderScenarioLibrary, renderScenarioStart } from "./scenarios.js";
import { renderArtSettings } from "./artsettings.js";
import { cardCorners, escapeHtml, help, holoFrame, holoFx } from "./common.js";
import { contextMeter, hudStat, iconBtn, modalShell, narratingDots, secHead } from "./widgets.js";

export function menuNode({ act, icon: ic, label, sub, kind }) {
  return `
    <button type="button" class="holo-node node-${kind}" data-act="${act}">
      ${holoFrame()}
      <span class="node-dial">
        <span class="dial-ring"></span>
        <span class="dial-ring ring-2"></span>
        <span class="dial-core">${icon(ic)}</span>
      </span>
      <span class="node-label">${label}</span>
      <span class="node-sub">${sub}</span>
    </button>`;
}

export function renderMenu(state) {
  const online = state.backendOnline;
  const nodes = [
    { kind: "new", act: "new-game", icon: "plus", label: "Novo", sub: "Crie um mundo" },
    { kind: "play", act: "go-library", icon: "play", label: "Jogar", sub: "Entre nos mundos salvos" },
    { kind: "settings", act: "open-settings", icon: "settings", label: "Configurações", sub: "Som e servidor" },
  ];
  return `
    <div class="menu-stage holo-stage" data-stage>
      ${holoFx()}

      <header class="menu-top">
        <span class="hud-tag">// MENU</span>
        ${help("menu")}
        ${hudStat(online)}
      </header>

      <div class="menu-title">
        <h1 class="title-glyph" data-text="GAMENTIC">GAMENTIC</h1>
        <p class="title-sub">Uma aventura de IA auto-hospedada</p>
      </div>

      <nav class="menu-deck">
        ${nodes.map(menuNode).join("")}
      </nav>

      <footer class="menu-foot">
        <span class="foot-chip">v1.0</span>
        <span class="foot-line"></span>
        <span class="foot-chip dim">AVENTURA LOCAL COM IA</span>
      </footer>
    </div>`;
}

// ---------------------------------------------------------------------------
// Library
// ---------------------------------------------------------------------------

export function renderLibrary(state) {
  const { games, backendOnline, backendError } = state;
  let body;
  if (!backendOnline) {
    body = `
      <div class="empty-state offline">
        <div class="empty-icon">${icon("radio")}</div>
        <h2>Servidor offline</h2>
        <p>Não foi possível acessar o servidor do jogo${backendError ? ` (${escapeHtml(backendError)})` : ""}.
           Inicie os serviços e tente novamente.</p>
        <button class="holo-btn" data-act="retry-library">${icon("rotate")}<span>Tentar novamente</span></button>
      </div>`;
  } else if (!games.length) {
    body = `<p class="modal-body">Ainda não há aventuras. Escolha um cenário acima para começar.</p>`;
  } else {
    body = `<div class="holo-grid">
      ${games.map(renderGameCard).join("")}

    </div>`;
  }

  return `
    <div class="holo-stage lib-stage" data-stage>
      ${holoFx()}
      <header class="holo-bar">
        ${iconBtn({ act: "go-menu", icon: "chevronLeft", label: "Menu principal" })}
        <span class="hud-tag">// CENÁRIOS E AVENTURAS</span>
        ${help("library")}
        ${hudStat(backendOnline)}
        <button class="holo-btn lib-import" data-act="import-game" title="Importar uma aventura exportada (modelo ou ponto salvo)" ${state.importing ? "disabled" : ""}>
          ${icon("rotate")}<span>${state.importing ? "Importando..." : "Importar"}</span>
        </button>
        <input type="file" id="importFile" accept=".json,application/json" hidden aria-label="Arquivo de aventura exportada" />
        ${iconBtn({ act: "open-settings", icon: "settings", label: "Configurações" })}
      </header>
      <main class="lib-main">
        ${backendOnline ? renderScenarioLibrary(state.scenarios || [], state.scenariosError) : ""}
        <section class="library-section" aria-labelledby="adventureHeading"><h2 id="adventureHeading">Aventuras</h2>${body}</section>
      </main>
      ${state.scenarioStart ? renderScenarioStart(state.scenarioStart) : ""}
      ${state.confirm ? renderConfirm(state.confirm) : ""}
      ${state.exportChoice ? renderExportChoice(state.exportChoice) : ""}
    </div>`;
}

export function renderGameCard(game) {
  return `
    <article class="holo-card" data-game-id="${escapeHtml(game.id)}">
      ${cardCorners()}
      <span class="card-status">${escapeHtml(game.status || "active")}</span>
      <h3 class="card-title">${escapeHtml(game.title)}</h3>
      <p class="card-meta">${escapeHtml(game.created_at || "")}</p>
      <div class="card-actions">
        <button class="holo-btn" data-act="continue-game" data-game-id="${escapeHtml(game.id)}">
          ${icon("play")}<span>Entrar</span>
        </button>
        ${iconBtn({ act: "ask-export", icon: "send", label: "Exportar aventura", title: "Exportar", data: { "game-id": game.id, "game-title": game.title } })}
        ${iconBtn({ act: "ask-delete", icon: "trash", label: "Excluir aventura", title: "Excluir", cls: "danger", data: { "game-id": game.id, "game-title": game.title } })}
      </div>
    </article>`;
}

// Export choice: one adventure, two flavors. Template = the world as designed
// (a fresh start anyone can import); checkpoint = the full save, this moment.
export function renderExportChoice(ex) {
  return modalShell({
    overlayAct: "cancel-export",
    title: `Exportar "${ex.title}"`,
    titleIcon: "send",
    ariaLabel: `Exportar "${ex.title}"`,
    body: `<p class="modal-body">Compartilhe a aventura como um novo começo ou salve este momento como um ponto de salvamento completo. As duas opções baixam um arquivo que a biblioteca pode importar.</p>`,
    actionsCls: "export-actions",
    actions: `
      <button class="holo-btn" data-act="export-game" data-kind="template" data-game-id="${escapeHtml(ex.gameId)}" data-game-title="${escapeHtml(ex.title)}">
        ${icon("sparkles")}<span>Compartilhar como aventura</span>
      </button>
      <button class="holo-btn" data-act="export-game" data-kind="checkpoint" data-game-id="${escapeHtml(ex.gameId)}" data-game-title="${escapeHtml(ex.title)}">
        ${icon("scroll")}<span>Salvar este momento</span>
      </button>
      <button class="holo-btn" data-act="cancel-export">Cancelar</button>`,
  });
}

export function renderConfirm(c) {
  return modalShell({
    overlayAct: "cancel-delete",
    title: "Excluir aventura?",
    titleIcon: "trash",
    body: `<p class="modal-body">"${escapeHtml(c.title)}" será apagada, incluindo personagens, cenas, missões e histórico. Esta ação não pode ser desfeita.</p>`,
    actions: `
      <button class="holo-btn" data-act="cancel-delete">Cancelar</button>
      <button class="holo-btn danger" data-act="confirm-delete" data-game-id="${escapeHtml(c.gameId)}">${icon("trash")}<span>Excluir</span></button>`,
  });
}

// ---------------------------------------------------------------------------
// Creator
// ---------------------------------------------------------------------------

export function renderCreator(state) {
  const c = state.creator;
  const messages = c.messages
    .map(
      (m) =>
        `<div class="forge-msg ${m.role === "user" ? "from-user" : "from-builder"}">
           <span class="forge-who">${m.role === "user" ? "Você" : "Criador de mundos"}</span>
           <p>${escapeHtml(m.text)}</p>
         </div>`,
    )
    .join("");
  const thinking = c.busy
    ? `<div class="forge-msg from-builder thinking"><span class="forge-who">Criador de mundos</span>
         ${narratingDots("moldando o mundo...")}
       </div>`
    : "";
  const restored = c.restored
    ? `<div class="forge-restored">${icon("rotate")}<span>Retomamos de onde você parou. Esta conversa foi preservada.</span></div>`
    : "";

  return `
    <div class="holo-stage forge-stage" data-stage>
      ${holoFx()}
      <header class="holo-bar">
        ${iconBtn({ act: "go-library", icon: "chevronLeft", label: "Voltar", title: "Voltar para aventuras" })}
        <span class="hud-tag">// CRIAR</span>
        ${help("creator")}
        <button class="holo-btn forge-restart" data-act="creator-restart" title="Descartar esta conversa e criar um novo mundo" ${c.busy ? "disabled" : ""}>
          ${icon("rotate")}<span>Recomeçar</span>
        </button>
      </header>

      <main class="forge-main">
        <div class="forge-thread" id="creatorThread">${restored}${messages}${thinking}</div>
      </main>

      <footer class="forge-bar">
        ${c.error ? `<p class="forge-error">${escapeHtml(c.error)}</p>` : ""}
        <form class="forge-form" data-form="creator">
          <input name="creatorText" class="holo-input" autocomplete="off"
                 placeholder="Descreva seu mundo: um farol assombrado, uma cripta inundada, uma cidade neon em decadência..."
                 ${c.busy ? "disabled" : ""} />
          <button class="holo-btn" type="submit" ${c.busy ? "disabled" : ""}>${icon("send")}<span>Enviar</span></button>
        </form>
        <button class="holo-btn primary forge-begin" data-act="save-scenario" ${c.busy || !c.ready ? "disabled" : ""}
                title="${c.ready ? "Salvar as regras deste cenário" : "O criador de mundos libera esta opção quando o mundo estiver pronto"}">
          ${icon("flame")}<span>${c.busy ? "Salvando..." : c.ready ? "Salvar cenário" : "Salvar cenário (ainda não está pronto)"}</span>
        </button>
      </footer>
      ${c.finalizing ? renderCrafting() : ""}
    </div>`;
}

// Full-screen takeover while the backend forges the world (finalize can take a
// while: it builds scenes, characters, portraits, voices). Blocks the chat.
export function renderCrafting() {
  const lines = [
    "Organizando a ambientação",
    "Consolidando as regras",
    "Salvando o cenário",
  ];
  return `
    <div class="craft-overlay" role="status" aria-live="polite">
      <div class="craft-core">
        <span class="craft-ring r1"></span>
        <span class="craft-ring r2"></span>
        <span class="craft-ring r3"></span>
        <span class="craft-orbit"><span class="craft-spark"></span></span>
        <span class="craft-orbit slow"><span class="craft-spark alt"></span></span>
        <span class="craft-glyph">${icon("sigil")}</span>
      </div>
      <h2 class="craft-title">Salvando seu cenário</h2>
      <div class="craft-status">
        ${lines.map((t, i) => `<span style="--i:${i}">${escapeHtml(t)}</span>`).join("")}
      </div>
      <div class="craft-bar"><span></span></div>
    </div>`;
}

// (Quick-action chips were removed on purpose: each affordance comes from ONE
// state field and renders in ONE place - synthesized suggestion chips restated
// the goal / scene actions / character actions and read as noise.)

// ---------------------------------------------------------------------------
// Settings (tucked away; NOT shown during play)
// ---------------------------------------------------------------------------

export function holoSwitch(key, on) {
  return `<span class="holo-switch">
            <input type="checkbox" data-setting="${key}" ${on ? "checked" : ""} />
            <span class="switch-track"></span>
          </span>`;
}

export function renderSettings(state) {
  const st = state.settings;
  const pct = Math.round((Number(st.masterVolume) || 0) * 100);
  return `
    <div class="holo-stage set-stage" data-stage>
      ${holoFx()}
      <header class="holo-bar">
        ${iconBtn({ act: "close-settings", icon: "chevronLeft", label: "Voltar" })}
        <span class="hud-tag">// SYSTEM</span>
        ${help("settings")}
      </header>
      <main class="set-main">
        <div class="set-col">
        <section class="holo-panel">
          ${cardCorners()}
          ${secHead("h3", "panel-head", "mic", "Áudio")}

          <label class="set-row">
            <span class="set-label">Voz<small>Narração e falas dos personagens</small></span>
            ${holoSwitch("voiceEnabled", st.voiceEnabled)}
          </label>

          <label class="set-row">
            <span class="set-label">Voz do narrador<small>Reproduzir narração automaticamente</small></span>
            ${holoSwitch("autoplayNarrator", st.autoplayNarrator)}
          </label>

          <label class="set-row">
            <span class="set-label">Vozes dos personagens<small>Reproduzir falas automaticamente</small></span>
            ${holoSwitch("autoplayCharacters", st.autoplayCharacters)}
          </label>

          <label class="set-row">
            <span class="set-label">Volume geral<small>Volume de todo o jogo</small></span>
            <span class="holo-range">
              <input type="range" min="0" max="1" step="0.05" data-setting="masterVolume" value="${Number(st.masterVolume) || 0}" />
              <span class="range-val">${pct}%</span>
            </span>
          </label>
        </section>

        ${state.active && state.active.state ? renderMemorySettings(state.active) : ""}
        </div>

        <div class="set-col">
        ${state.active && state.active.state ? renderGameSettings(state.active) : ""}
        <section class="holo-panel danger-zone">
          ${cardCorners()}
          ${secHead("h3", "panel-head", "flame", "Perigo")}
          <div class="set-row">
            <span class="set-label">Apagar toda a memória<small>Todas as aventuras, históricos, personagens e imagens. Não pode ser desfeito.</small></span>
            <button type="button" class="holo-btn danger" data-act="ask-wipe">${icon("trash")}<span>Apagar toda a memória</span></button>
          </div>
        </section>
        </div>

        <p class="set-foot">${icon("radio")}<span>Servidor conectado automaticamente // mídia via proxy da mesma origem</span></p>
      </main>
      ${state.wipe ? renderWipeConfirm(state.wipe) : ""}
    </div>`;
}

// The wipe-all double confirm: the first click ARMS the button, the second
// erases. There is no undo, so the dialog says exactly what it deletes.
export function renderWipeConfirm(w) {
  return modalShell({
    overlayAct: "cancel-wipe",
    title: "Apagar toda a memória?",
    titleIcon: "flame",
    body: `<p class="modal-body">Isso exclui TODAS as aventuras, históricos, personagens e imagens. Não é possível desfazer.</p>
        ${w.stage > 1 ? `<p class="modal-body wipe-armed">Última chance. Clique mais uma vez para apagar tudo.</p>` : ""}`,
    actions: `
      <button class="holo-btn" data-act="cancel-wipe" ${w.busy ? "disabled" : ""}>Cancelar</button>
      <button class="holo-btn danger" data-act="confirm-wipe" ${w.busy ? "disabled" : ""}>
        ${icon("trash")}<span>${w.busy ? "Apagando..." : w.stage > 1 ? "Sim, apagar tudo" : "Apagar tudo"}</span>
      </button>`,
  });
}

// Story memory (PATCH /games/{id}/settings): how the narrator remembers. The
// mental model in the copy: recent story rides verbatim, everything older is
// auto-compressed into a recap, so the story is never lost. Three controls;
// 0 always returns a control to its default. context_tokens is the one that
// actually CAPS turn latency, so the live meter sits next to it.
function renderMemorySettings(g) {
  const st = g.state.settings || {};
  const saving = g.settingsSaving ? "disabled" : "";
  const memRow = (key, value, label, sub, min, max, step) => `
    <label class="set-row mem-row">
      <span class="set-label">${escapeHtml(label)}<small>${escapeHtml(sub)}</small></span>
      <input type="number" class="holo-input mem-input" data-mem-setting="${key}" aria-label="${escapeHtml(label)}"
             value="${Number(value) || 0}" min="0" max="${max}" step="${step}" ${saving} />
    </label>`;
  return `
    <section class="holo-panel memory-settings">
      ${cardCorners()}
      ${secHead("h3", "panel-head", "gauge", "Memória da história")}
      <p class="set-note">O narrador relê a história recente palavra por palavra e resume automaticamente o conteúdo mais antigo. Use 0 para voltar ao padrão.</p>
      ${memRow("history_beats", st.historyBeats, "Profundidade da memória", "Quanto da história recente permanece literal (8-400). Mais profundidade traz mais continuidade e turnos mais lentos.", 8, 400, 4)}
      ${memRow("summary_every", st.summaryEvery, "Resumir automaticamente a cada N turnos", "Com que frequência capítulos antigos entram no resumo (2-50).", 2, 50, 1)}
      ${memRow("context_tokens", st.contextTokens, "Orçamento de contexto (automático)", "Limite de leitura do narrador (4000-120000; 0 = desativado). Isso limita a demora do turno.", 4000, 120000, 1000)}
      ${contextMeter(g.state.context)}
    </section>`;
}

// Per-adventure settings (PATCH /games/{id}/settings), shown only when settings
// is opened from inside a game. Difficulty is how much the world bends toward
// the player; the narrator gender redesigns the voice from the next line.
export const DIFFICULTY_COPY = {
  easy: "A história favorece você: tentativas dão certo, o perigo avisa antes e desejos se realizam.",
  normal: "Um mundo justo: o narrador avalia suas tentativas e desejos pelos próprios méritos.",
  hard: "O mundo é rigoroso: tentativas podem falhar, erros têm custo e desejos são apenas sussurros.",
};

export function renderGameSettings(g) {
  const gs = g.state.settings || { difficulty: "normal", narratorGender: "", characterImages: "sometimes" };
  const saving = g.settingsSaving ? "disabled" : "";
  const radio = (group, value, current, label, sub) => `
    <label class="set-radio${current === value ? " active" : ""}">
      <input type="radio" name="${group}" value="${escapeHtml(value)}" data-game-setting="${group}"
             ${current === value ? "checked" : ""} ${saving} />
      <span class="set-label">${escapeHtml(label)}${sub ? `<small>${escapeHtml(sub)}</small>` : ""}</span>
    </label>`;

  return `
    <section class="holo-panel game-settings">
      ${cardCorners()}
      ${secHead("h3", "panel-head", "sigil", "Esta aventura")}

      <fieldset class="set-group" data-group="difficulty">
        <legend class="set-legend">Dificuldade</legend>
        ${radio("difficulty", "easy", gs.difficulty, "Fácil", DIFFICULTY_COPY.easy)}
        ${radio("difficulty", "normal", gs.difficulty, "Normal", DIFFICULTY_COPY.normal)}
        ${radio("difficulty", "hard", gs.difficulty, "Difícil", DIFFICULTY_COPY.hard)}
      </fieldset>

      <fieldset class="set-group" data-group="narrator_gender">
        <legend class="set-legend">Voz do narrador</legend>
        ${radio("narrator_gender", "", gs.narratorGender, "Padrão", "A voz com que o mundo nasceu")}
        ${radio("narrator_gender", "female", gs.narratorGender, "Feminina", "Passa a valer na próxima fala")}
        ${radio("narrator_gender", "male", gs.narratorGender, "Masculina", "Passa a valer na próxima fala")}
      </fieldset>

      <fieldset class="set-group" data-group="character_images">
        <legend class="set-legend">Imagens dos personagens</legend>
        <p class="set-note">Personagens podem mostrar o que estão fazendo em imagens ocasionais, criadas em segundo plano.</p>
        ${radio("character_images", "off", gs.characterImages, "Desativadas", "Apenas imagens do narrador e dos seus olhares")}
        ${radio("character_images", "sometimes", gs.characterImages, "Às vezes", "Momentos raros, para continuarem especiais")}
        ${radio("character_images", "often", gs.characterImages, "Frequentemente", "Sempre que o momento valer a pena")}
      </fieldset>

      ${renderArtRegeneration(g)}

      <fieldset class="set-group" data-group="turn_pacing">
        <legend class="set-legend">Ritmo do turno</legend>
        <p class="set-note">Defina quantos personagens podem participar de um turno e quantas vezes cada um pode agir. A opção Padrão deixa o narrador definir o ritmo.</p>
        ${pacingSelect("turn_voices", gs.turnVoices, "Vozes por turno", "Personagens que podem falar ou agir em um turno (1-4).", 4, saving)}
        ${pacingSelect("turn_acts", gs.turnActs, "Ações por voz", "Quantas vezes cada personagem pode agir antes do fim do turno (1-3).", 3, saving)}
      </fieldset>

    </section>`;
}

function renderArtRegeneration(game) {
  const progress = game.imageRegeneration || {};
  const running = game.imageRegenerationStarting || progress.status === "running";
  const completed = Math.max(0, Number(progress.completed) || 0);
  const failed = Math.max(0, Number(progress.failed) || 0);
  const total = Math.max(0, Number(progress.total) || 0);
  const processed = completed + failed + Math.max(0, Number(progress.skipped) || 0);
  const disabled = running || game.state.imagesEnabled === false;
  const summary = progress.status === "completed" || progress.status === "partial"
    ? `${completed} imagens atualizadas.${failed ? ` ${failed} não puderam ser geradas; as anteriores foram mantidas.` : ""}`
    : progress.status === "failed" ? "A geração foi interrompida. Você pode tentar novamente." : "";
  return `<fieldset class="set-group art-regeneration">
    <legend>Arte da aventura</legend>
    ${renderArtSettings(game)}
    <p class="set-note">Refaz as imagens já geradas com o modelo e o estilo atuais. História e progresso são preservados.</p>
    <button type="button" class="holo-btn" data-act="regenerate-all-images" ${disabled ? "disabled" : ""}>
      ${icon("image")}<span>${running ? "Regenerando imagens..." : "Regenerar todas as imagens"}</span>
    </button>
    <div role="status" aria-live="polite">
      ${running && total ? `<p class="set-note">${processed} de ${total} imagens processadas.</p>
      <progress aria-label="Progresso da regeneração" max="${total}" value="${processed}"></progress>` : ""}
      ${summary ? `<p class="set-note">${escapeHtml(summary)}</p>` : ""}
      ${game.imageRegenerationError ? `<p class="set-note">${escapeHtml(game.imageRegenerationError)}</p>` : ""}
      ${game.state.imagesEnabled === false ? `<p class="set-note">A geração de imagens está desativada.</p>` : ""}
    </div>
  </fieldset>`;
}

// One turn-pacing select: Default (sends 0, back to the narrator's own pace)
// plus the explicit 1..max values. Shows the EFFECTIVE value from state.
function pacingSelect(key, value, label, sub, max, saving) {
  const options = [];
  for (let v = 1; v <= max; v++) {
    options.push(`<option value="${v}" ${Number(value) === v ? "selected" : ""}>${v}</option>`);
  }
  return `
    <label class="set-row">
      <span class="set-label">${escapeHtml(label)}<small>${escapeHtml(sub)}</small></span>
      <select class="holo-input pace-select" data-game-setting="${key}" aria-label="${escapeHtml(label)}" ${saving}>
        <option value="0">Padrão</option>
        ${options.join("")}
      </select>
    </label>`;
}
