// The play screen: the deck, character columns, the action bar, give modal.

import { presentCharacters, unreadPmCount } from "../adapters.js";
import { icon } from "../icons.js";
import { cardCorners, escapeHtml, help, holoFx, initials, titleCase, unreadBadge } from "./common.js";
import { renderInspectModal } from "./inspect.js";
import { renderProfile } from "./profile.js";
import { renderStory } from "./story.js";
import { renderChoicePicker, renderTurnChoices } from "./choices.js";
import { artImg, artLoading, avatarOrInitials, contextMeter, dispositionBadges, exitBtn, hpBar, iconBtn, modalShell, narratingDots, renderComposer, renderStack, renderViewPending, sceneActionBtn, sceneItemSlot, slotGrid, slotInner, slotTip } from "./widgets.js";

export { renderViewPending };

// ---------------------------------------------------------------------------
// Play
// ---------------------------------------------------------------------------

// Command-deck layout (v0.2 scene-centric, integrated-header redesign):
//   ONE integrated header (scene identity + scene affordances + vitals, no
//   repeated affordances) | story (scene art mixed into the prose) + character
//   columns | player inventory + the say/do composer.
export function renderPlay(state) {
  const g = state.active;
  if (!g || !g.state) {
    return `<main class="play-loading"><div class="empty-icon">${icon("sparkles")}</div><p>Carregando a aventura...</p></main>`;
  }
  const s = g.state;
  // PARTIAL busy-lock: while a turn is in flight, only state-MUTATING surfaces
  // lock (composer/send, action buttons, exits, Continue, Look, the private
  // composer). Everything read-only stays interactive: lightbox, inspect,
  // /explain, scrolling, profiles, settings. No full-screen veil.
  const locked = Boolean(g.generating);

  return `
    <div class="holo-stage play-stage${locked ? " generating" : ""}" data-stage>
      ${holoFx()}
      ${renderPlayDeck(s, locked, g)}

      <div class="play-body">
        <main class="story" id="storyStream" data-help-anchor role="log" aria-live="polite" aria-relevant="additions" aria-label="História">
          <div class="story-help-row">${help("story")}</div>
          ${renderStory(g)}
          ${g.pendingView && !g.lastVia ? renderViewPending() : ""}
          ${locked ? renderNarrating(g) : ""}
          ${renderTurnChoices(g, locked)}
        </main>

        <aside class="char-column">
          <div class="col-head">${icon("mask")}<span>Na cena</span>${help("party")}</div>
          ${renderCharacters(s, locked, g)}
        </aside>
      </div>

      ${renderActionBar(g, s, locked)}
      ${renderChoicePicker(g)}
      ${g.give ? renderGiveModal(s, g.give, locked) : ""}
      ${g.inspect ? renderInspectModal(s, g) : ""}
      ${g.profile ? renderProfile(s, g) : ""}
    </div>`;
}

// Give-picker: choose an item from the player's inventory to hand to a character.
// Renders the same fixed slot-grid language as the pack (owner: "show both text and
// images, with empty gaps showing"): thumbnail or initials, name caption, 6 slots.
export function renderGiveModal(s, give, locked) {
  const dis = locked ? "disabled" : "";
  const items = s.player.inventory || [];
  const pickCell = (it) =>
    `<button type="button" class="slot filled give-pick" data-act="pick-give" data-item="${escapeHtml(it.id || it.name)}" data-target="${escapeHtml(give.name)}" title="${escapeHtml(slotTip(it))}" aria-label="${escapeHtml(it.name)}" ${dis}>
       <span class="give-art">${slotInner(it)}</span>
       <span class="give-name">${escapeHtml(it.name)}</span>
     </button>`;
  const body = items.length
    ? slotGrid(items, 6, "give-items", pickCell)
    : `<p class="modal-body">Você não tem nada para dar.</p>`;
  return modalShell({
    overlayAct: "cancel-give",
    cls: "give-modal",
    ariaLabel: `Dar para ${give.name}`,
    header: `<h3 class="modal-title give"><span class="ic">${icon("gem")}</span><span>Dar para ${escapeHtml(give.name)}</span></h3>`,
    body: `${items.length ? `<p class="modal-body">Escolha um item para entregar.</p>` : ""}
        ${body}`,
    actions: `<button class="holo-btn" data-act="cancel-give" ${dis}>Cancelar</button>`,
  });
}

// ---------------------------------------------------------------------------
// The integrated header ("the deck"). ONE structure, three shape levels:
//   nav | scene identity wing (tall, protrudes) | affordance board | vitals wing
// Every affordance renders from exactly ONE state field, in exactly ONE place:
// goal chip (current_goal), mood badge (scene.status, on the scene name),
// scene items/actions/exits, context meter, story clock.
// ---------------------------------------------------------------------------
export function renderPlayDeck(s, locked, g = {}) {
  const dis = locked ? "disabled" : "";
  const p = s.player;
  const scene = s.scene;
  const name = (scene && scene.name) || titleCase(p.location || "Desconhecido");
  const desc = (scene && scene.description) || "";
  const mood = (scene && scene.status) || s.sceneStatus || null;
  const items = (scene && scene.items) || [];
  const actions = (scene && scene.actions) || [];
  const exits = (scene && scene.exits) || [];
  void g;

  return `
    <header class="play-deck">
      <div class="deck-nav">
        ${iconBtn({ act: "go-library", icon: "chevronLeft", label: "Biblioteca", disabled: locked })}
      </div>

      <div class="deck-scene">
        ${cardCorners()}
        <div class="scene-id">
          ${mood ? `<span class="mood-badge mood-${escapeHtml(mood)}">${escapeHtml(mood)}</span>` : ""}
          ${s.time ? `<span class="time-chip" title="Hora da história, não a sua">${icon("clock")}<span>${escapeHtml(s.time.label)}</span></span>` : ""}
        </div>
        <h2 class="scene-name"><button type="button" class="scene-name-btn" data-act="inspect-scene" title="O que é este lugar" ${dis}>${escapeHtml(name)}</button>${help("scene")}</h2>
        ${desc ? `<p class="scene-desc">${escapeHtml(desc)}</p>` : ""}
      </div>

      <div class="deck-board">
        <div class="board-cell">
          <span class="rail-label">${icon("gem")}<span>Itens da cena</span></span>
          ${slotGrid(items, 6, "scene-items", sceneItemSlot, s.imagesEnabled)}
        </div>
        <i class="board-sep" aria-hidden="true"></i>
        <div class="board-cell">
          <span class="rail-label">${icon("zap")}<span>Ações</span></span>
          <div class="act-row">
            ${actions.map((a) => sceneActionBtn(a, locked)).join("")}
            ${!actions.length ? `<span class="muted small">Não há nada óbvio para fazer.</span>` : ""}
          </div>
        </div>
        <i class="board-sep" aria-hidden="true"></i>
        <div class="board-cell">
          <span class="rail-label">${icon("compass")}<span>Saídas</span></span>
          <div class="act-row">
            ${exits.map((e) => exitBtn(e, locked)).join("")}
            ${!exits.length ? `<span class="dead-end">${icon("x")}<span>Beco sem saída: nenhuma saída revelada</span></span>` : ""}
          </div>
        </div>
      </div>

      <div class="deck-vitals" data-hud>
        <div class="vital-row">
          <div class="hud-life" data-hud-life>
            ${icon("heart")}
            ${hpBar(p.life, p.maxLife, { variant: "player" })}
            <span class="hud-num" data-hud-num="life">${p.life}/${p.maxLife}</span>
          </div>
          <div class="hud-points">${icon("star")}<span class="hud-num" data-hud-num="points">${p.points}</span></div>
          ${help("hud")}
        </div>
        ${contextMeter(s.context)}
        ${s.currentGoal ? `<button type="button" class="hud-goal" data-act="inspect-goal" title="Objetivo atual — toque para ver as missões" ${dis}>${icon("compass")}<span>${escapeHtml(s.currentGoal)}</span></button>` : ""}
      </div>

      <div class="deck-nav">
        ${iconBtn({ act: "open-settings", icon: "settings", label: "Menu", title: "Menu e configurações" })}
      </div>
    </header>`;
}

export function renderCharacters(s, locked, g = {}) {
  const present = presentCharacters(s);
  const presentIds = new Set(present.map((c) => c.id));
  // everyone known but not standing here: followers lagging, those left behind, the fallen.
  const elsewhere = (s.characters || []).filter((c) => c.name && !presentIds.has(c.id));

  const here = present.length
    ? `<div class="char-deck cols-${present.length}">${present.map((c) => renderCharColumn(c, s, locked, g)).join("")}</div>`
    : `<p class="muted small char-empty">Não há mais ninguém aqui agora.</p>`;

  const roster = elsewhere.length
    ? `<div class="cast-roster">
         <div class="col-head sub">${icon("eye")}<span>Em outro lugar</span></div>
         ${elsewhere.map((c) => castRow(c, g)).join("")}
       </div>`
    : "";

  return here + roster;
}

// A character is a tall vertical card column: the full-body reference art fills
// the column, identity reads off a plate at its foot, and only the Carrying
// row hangs below. Everything else - description, actions, whisper - lives in
// the FULL-SCREEN profile; the card just hints at it ("expand to interact").
export function renderCharColumn(c, s, locked, g = {}) {
  void locked;
  const hp =
    c.life != null && c.maxLife
      ? hpBar(c.life, c.maxLife, { cls: "char-hp", title: `${c.life}/${c.maxLife}` })
      : "";
  // unseen private messages from this character get a count dot on their card
  const unread = unreadBadge(unreadPmCount(g, c.id), "on-card");
  return `
    <article class="char-col${c.alive ? "" : " dead"}" data-char-id="${escapeHtml(c.id)}" style="--speaker:${escapeHtml(c.color)}">
      <button type="button" class="col-art" data-act="open-profile" data-char-id="${escapeHtml(c.id)}" data-char-name="${escapeHtml(c.name)}" title="Abrir perfil de ${escapeHtml(c.name)}" aria-label="Abrir perfil de ${escapeHtml(c.name)}">
        ${bodyArt(c, s)}
        <div class="col-grad" aria-hidden="true"></div>
        ${unread}
        <span class="col-badges">
          ${dispositionBadges(c)}
        </span>
        <div class="col-plate">
          <span class="char-name">${escapeHtml(c.name)}${c.following ? ` <span class="follow-tag" title="Segue você">${icon("compass")}</span>` : ""}</span>
          ${hp}
        </div>
      </button>
      ${contextMeter(c.context, { mini: true, label: `${c.name}'s memory` })}
      <div class="char-inv">
        <span class="inv-mini-label">Carregando</span>
        ${slotGrid(c.inventory, 3, "char-items", undefined, s.imagesEnabled)}
      </div>
      <span class="char-hint">${icon("panel")}<span>expand to interact</span></span>
    </article>`;
}

// Full-body art for a character column, honoring the loading rule:
// url -> the image; null + images_enabled -> a loader (art is generating);
// null + images off -> a static color+initial figure, no loader.
export function bodyArt(c, s) {
  if (c.bodyUrl) {
    const caption = [c.name, c.description].filter(Boolean).join(" - ");
    return artImg({ url: c.bodyUrl, alt: c.name, caption, cls: "col-body" });
  }
  if (s.imagesEnabled) {
    return artLoading("col-body", "criando imagem", `${c.name} (imagem em criação)`);
  }
  return `<div class="col-body art-off" role="img" aria-label="${escapeHtml(c.name)}">
            <span class="col-initial">${escapeHtml(initials(c.name))}</span>
          </div>`;
}

export function castRow(c, g = {}) {
  const avatar = avatarOrInitials({ url: c.faceUrl, name: c.name, color: c.color, fallbackCls: "cast-fallback" });
  let where;
  if (!c.alive) where = "morto";
  else if (c.following) where = "com você";
  else if (c.present === false) where = "ausente";
  else if (c.location) where = `em ${titleCase(c.location)}`;
  else where = "em outro lugar";
  // an absent character can still whisper the player: their row carries the
  // same unread alert as a present card
  const unread = unreadBadge(unreadPmCount(g, c.id), "on-row");
  return `<button type="button" class="cast-row${c.alive ? "" : " dead"}" data-act="open-profile" data-char-id="${escapeHtml(c.id)}" data-char-name="${escapeHtml(c.name)}" style="--speaker:${escapeHtml(c.color)}" title="${escapeHtml(c.name)} - ${escapeHtml(where)}">
            <span class="cast-portrait">${avatar}</span>
            <span class="cast-id"><span class="cast-name">${escapeHtml(c.name)}</span><span class="cast-where">${escapeHtml(where)}</span></span>
            ${unread}
          </button>`;
}


export function renderActionBar(g, s, locked) {
  const cmp = g.composer || { mode: "do", stack: [] };
  const dis = locked ? "disabled" : "";
  return `
    <footer class="play-actionbar">
      <div class="player-inv">
        <span class="rail-label">${icon("gem")}<span>Você</span>${help("inventory")}</span>
        ${slotGrid(s.player.inventory, 6, "player-items", undefined, s.imagesEnabled)}
        <span class="action-help">
          ${s.actionChoices?.length ? `<button type="button" class="holo-btn choice-launcher" data-act="open-choice-picker"
            title="Escolher uma das cinco sugestões" ${locked || g.revealing ? "disabled" : ""}>5 opções</button>` : ""}
          ${help("action")}
        </span>
      </div>
      ${renderStack(cmp.stack, "cmp")}
      <form class="action-form" data-form="action">
        ${renderComposer({
          id: "cmp",
          mode: cmp.mode,
          locked,
          modes: ["say", "do", "look"],
          placeholders: {
            do: "Faça ou diga qualquer coisa... (Enter envia)",
            say: "O que você diz?",
            look: "Olhar o quê? (vazio = observar toda a cena)",
          },
          submitLabel: "Enviar",
        })}
      </form>
      <div class="turn-aux">
        <input type="text" id="wishInput" class="holo-input wish-input" autocomplete="off" maxlength="200"
               placeholder="O que você deseja que aconteça a seguir? (opcional)" aria-label="O que você deseja que aconteça a seguir?"
               title="Um desejo para o narrador. Histórias fáceis tendem a realizá-lo; histórias difíceis podem ignorá-lo."
               value="${escapeHtml(g.wish || "")}" ${dis} />
        <button type="button" class="holo-btn continue-btn" data-act="continue-story"
                title="Deixe a história avançar sozinha, sem entrada" ${dis}>
          ${icon("play")}<span>Continuar</span>
        </button>
      </div>
    </footer>`;
}

export function renderNarrating(g) {
  const p = g && g.livePhase;
  const label = !p
    ? "o narrador está pensando..."
    : p.phase === "interpret"
      ? "lendo suas palavras..."
      : p.phase === "character"
        ? `${p.name || "alguém"} está respondendo...`
        : p.phase === "choices"
          ? "a IA está preparando cinco opções..."
        : "o narrador está escrevendo...";
  const stop = g && g.stopping
    ? `<button type="button" class="holo-btn small stop-btn" disabled>${icon("x")}<span>interrompendo...</span></button>`
    : `<button type="button" class="holo-btn small stop-btn" data-act="stop-turn" title="Cancele este turno como se não tivesse sido enviado; suas palavras voltam">${icon("x")}<span>Parar</span></button>`;
  return `<div class="narrating-row">${narratingDots(label)}${stop}</div>`;
}
