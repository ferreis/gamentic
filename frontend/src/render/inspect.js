// Tap-to-inspect: the detail modal over items, the goal, quests, receipts.

import { icon } from "../icons.js";
import { escapeHtml, titleCase } from "./common.js";
import { artImg, iconBtn, modalShell, narratingDots } from "./widgets.js";

// ---------------------------------------------------------------------------
// Tap-to-inspect: every small thing on screen (items, characters, the goal,
// quests, system receipts) expands into a detail modal with the facts already
// in /state plus an "ask what this is" narrator aside (POST /explain,
// spoiler-safe by construction). Its image click opens the lightbox.
// ---------------------------------------------------------------------------
export function renderInspectModal(s, g) {
  const ins = g.inspect; // { kind, key, beatId, asking, answer }
  const locked = Boolean(g.generating);
  const view = inspectView(s, g, ins);
  const ask = `
    <div class="ins-ask">
      ${
        ins.asking
          ? narratingDots("o narrador está pensando...")
          : ins.answer != null
            ? `<p class="ins-answer">${escapeHtml(ins.answer)}</p>`
            : ""
      }
      <button type="button" class="holo-btn" data-act="inspect-ask" ${ins.asking ? "disabled" : ""}>
        ${icon("sparkles")}<span>${ins.answer != null ? "Perguntar novamente" : "Perguntar o que é isto"}</span>
      </button>
    </div>`;

  // the inspect modal has its own header shape: an ins-title plus a close
  // button, and the action row uses ins-actions (not modal-actions), so the
  // body carries those itself rather than going through modalShell's actions.
  return modalShell({
    overlayAct: "close-inspect",
    cls: "inspect-modal",
    ariaLabel: view.title,
    header: `<header class="ins-head">
          <h3 class="ins-title">${escapeHtml(view.title)}</h3>
          ${iconBtn({ act: "close-inspect", icon: "x", label: "Fechar" })}
        </header>`,
    body: `${view.body}
        ${view.actions ? `<div class="ins-actions">${view.actions}</div>` : ""}
        ${ask}`,
  });
}

export function inspectView(s, g, ins) {
  if (ins.kind === "item") return inspectItem(s, ins, g);
  if (ins.kind === "scene") return inspectScene(s);
  if (ins.kind === "goal") return inspectGoal(s);
  if (ins.kind === "quest") return inspectQuest(s, ins);
  if (ins.kind === "beat") return inspectBeat(g, ins);
  return { title: "Desconhecido", body: `<p class="modal-body">Não há nada para ver.</p>`, actions: "" };
}

export function findInspectItem(s, key) {
  const pools = [
    ...(((s.scene && s.scene.items) || []).map((it) => ({ ...it, where: "aqui na cena", inScene: true }))),
    ...((s.player.inventory || []).map((it) => ({ ...it, where: "na sua mochila" }))),
    ...((s.characters || []).flatMap((c) => (c.inventory || []).map((it) => ({ ...it, where: `com ${c.name}` })))),
  ];
  return pools.find((it) => (it.id && it.id === key) || it.name === key) || null;
}

export function inspectImage(url, alt, caption = "") {
  // not wrapped in a button: the global lightbox listener picks the click up.
  // `caption` is the thing's description, shown when the image expands.
  const full = [alt, caption].filter(Boolean).join(" - ");
  return url
    ? `<div class="ins-figure">${artImg({ url, alt, caption: full })}</div>`
    : "";
}

export function inspectItem(s, ins, g) {
  const it = findInspectItem(s, ins.key);
  if (!it) return { title: "Sumiu", body: `<p class="modal-body">Isto não está mais aqui.</p>`, actions: "" };
  const locked = Boolean(g.generating);
  const tags = [
    it.where,
    it.qty > 1 ? `x${it.qty}` : "",
    it.inScene ? (it.fixed ? "parte da cena" : "pode ser levado") : "",
  ].filter(Boolean);
  const actions = it.inScene
    ? it.fixed
      ? `<button type="button" class="holo-btn" data-act="examine-item" data-item-name="${escapeHtml(it.name)}" ${locked ? "disabled" : ""}>${icon("eye")}<span>Examinar ${escapeHtml(it.name)}</span></button>`
      : `<button type="button" class="holo-btn primary" data-act="take-item" data-item-name="${escapeHtml(it.name)}" ${locked ? "disabled" : ""}>${icon("plus")}<span>Pegar ${escapeHtml(it.name)}</span></button>`
    : "";
  return {
    title: it.name,
    body: `
      ${inspectImage(it.imageUrl, it.name, it.description)}
      <p class="ins-tags">${tags.map((t) => `<span class="ins-tag">${escapeHtml(t)}</span>`).join("")}</p>
      ${it.description ? `<p class="modal-body">${escapeHtml(it.description)}</p>` : ""}`,
    actions,
  };
}

// (characters no longer use the inspect modal: tapping one opens the
// full-screen profile, which is richer and carries the whisper channel)

// The scene itself: description, mood, and the place's deeper story (the
// narrator writes `background` as the game goes; empty = nothing yet).
function inspectScene(s) {
  const scene = s.scene;
  if (!scene) return { title: "Lugar nenhum", body: `<p class="modal-body">Não há lugar para descrever.</p>`, actions: "" };
  return {
    title: scene.name || "Este lugar",
    body: `
      ${inspectImage(scene.imageUrl, scene.name, scene.description)}
      <p class="ins-tags"><span class="mood-badge mood-${escapeHtml(scene.status)}">${escapeHtml(titleCase(scene.status))}</span></p>
      ${scene.description ? `<p class="modal-body">${escapeHtml(scene.description)}</p>` : ""}
      ${
        scene.background
          ? `<h4 class="ins-sub">O que é este lugar</h4>
             <p class="modal-body scene-background">${escapeHtml(scene.background)}</p>`
          : ""
      }`,
    actions: "",
  };
}

export function inspectGoal(s) {
  const quests = (s.quests || []).filter((q) => q.status === "active");
  const questRows = quests
    .map(
      (q) => `
        <button type="button" class="ins-quest" data-act="inspect-quest" data-quest-id="${escapeHtml(q.id)}">
          ${icon("scroll")}<span class="ins-quest-name">${escapeHtml(q.title)}</span>
          <span class="ins-quest-progress">${q.objectives.filter((o) => o.done).length}/${q.objectives.length}</span>
        </button>`,
    )
    .join("");
  return {
    title: "Objetivo atual",
    body: `
      <p class="modal-body goal-line">${icon("compass")}<span>${escapeHtml(s.currentGoal || "Não há objetivo agora.")}</span></p>
      ${quests.length ? `<p class="ins-tags"><span class="ins-tag">registro de missões</span></p>${questRows}` : ""}`,
    actions: "",
  };
}

export function inspectQuest(s, ins) {
  const q = (s.quests || []).find((x) => x.id === ins.key);
  if (!q) return { title: "Missão", body: `<p class="modal-body">Esse fio da história desapareceu.</p>`, actions: "" };
  const objectives = q.objectives
    .map(
      (o) => `
        <li class="${o.done ? "done" : ""}">
          <span class="check">${o.done ? icon("check") : ""}</span><span>${escapeHtml(o.text)}</span>
        </li>`,
    )
    .join("");
  return {
    title: q.title,
    body: `
      ${q.description ? `<p class="modal-body">${escapeHtml(q.description)}</p>` : ""}
      <ul class="ins-objectives quest">${objectives}</ul>`,
    actions: "",
  };
}

export function inspectBeat(g, ins) {
  const beat = g.beats.find((b) => b.id === ins.beatId);
  return {
    title: "O que acabou de acontecer",
    body: `<p class="modal-body">${escapeHtml((beat && beat.text) || "")}</p>`,
    actions: "",
  };
}
