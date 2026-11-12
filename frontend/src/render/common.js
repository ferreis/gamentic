// Shared rendering primitives: text safety, the help copy, the holo chrome.


export const HELP = {
  menu: "O painel principal. Jogar abre seus mundos salvos, Novo cria uma aventura e Configurações ajusta o som e o servidor.",
  hud: "Seus indicadores. A barra de coração é sua vida; se ela acabar, a história se volta contra você. Pontos são a pontuação por ações inteligentes e corajosas. Memória mostra quanto da história o narrador ainda consegue manter em mente.",
  quests: "Seus objetivos atuais. Cada missão tem uma lista de objetivos. O narrador os marca à medida que você avança e pode adicionar novos conforme a história se desenrola.",
  party: "Personagens presentes com você. Cada cartão mostra a disposição, a vida e o que carregam. Toque em um personagem para abrir o perfil completo, traços revelados, momentos compartilhados, memórias e o canal privado.",
  scene: "Onde você está agora. O clima muda com a história, e o relógio é do mundo do jogo. Ao lado estão os objetos revelados, o que você pode tentar e as saídas.",
  inventory: "O que você está carregando. Espaços vazios mostram quanto ainda cabe. Use Dar para entregar algo a um personagem.",
  story: "A história. Texto corrido é a narração; cartões coloridos com nome são personagens falando com você. Pequenos indicadores mostram acontecimentos como dano, itens e pontos.",
  action: "Escreva o que você faz ou diz e pressione Enter. O jogo entende falas, ações, ataques, presentes e sussurros. Olhar examina a cena ou algo de perto. Continuar avança a história, e o desejo é uma esperança para o narrador, não uma ação.",
  creator: "Descreva o mundo que você quer em linguagem comum e converse com o criador de mundos. Defina as regras e salve o cenário. Na biblioteca, use-o para iniciar quantas aventuras quiser.",
  settings: "Opções de som e, durante o jogo, regras da aventura: dificuldade, voz do narrador e exportação para compartilhar ou salvar. O servidor se conecta automaticamente.",
  library: "Seus cenários e aventuras. Um cenário guarda as regras do mundo; cada aventura tem seu próprio progresso. Elas ficam armazenadas no servidor.",
};

export function help(key) {
  return `<button type="button" class="help-dot" data-help="${key}" aria-label="O que é isto?" title="O que é isto?">?</button>`;
}

// Speech text sometimes arrives wrapped in literal quote marks; the bubble IS
// the quotation, so showing them doubles up. Strip one wrapping pair only.
export function stripWrappingQuotes(value) {
  const t = String(value ?? "").trim();
  const pairs = [
    ['"', '"'],
    ["“", "”"], // curly double
    ["‘", "’"], // curly single
  ];
  for (const [a, b] of pairs) {
    if (t.length > 1 && t.startsWith(a) && t.endsWith(b)) {
      return t.slice(a.length, t.length - b.length).trim();
    }
  }
  return t;
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

// ---------------------------------------------------------------------------
// Main menu / title (the holographic landing deck)
// ---------------------------------------------------------------------------
//
// Phase 1 of the UI redesign: an ice-cyan sci-fi HUD landing screen. Three
// chamfered "nodes" (New / Play / Settings) with rotating dial rings, corner
// brackets and bloom. Pure CSS motion; no canvas, no framework. The nodes route
// straight into the existing views (Play -> library, New -> creator, etc.).

// Shared holographic background FX. Scanlines only (the nebula spheres, bloom
// halo and perspective grid were removed at the owner's request - too busy).
export function holoFx() {
  return `<div class="menu-fx" aria-hidden="true">
            <span class="fx-scan"></span>
          </div>`;
}

export function holoFrame() {
  // Four crisp corner brackets that hug a chamfered frame.
  return `<span class="holo-frame" aria-hidden="true">
            <i class="corner tl"></i><i class="corner tr"></i>
            <i class="corner bl"></i><i class="corner br"></i>
          </span>`;
}

// The diagonal corner accents on a holo card / modal / panel: top-right and
// bottom-left. Pure decoration, so they hide from screen readers (the sibling
// holoFrame above does the same with its four brackets).
export function cardCorners() {
  return `<span class="card-corner tr" aria-hidden="true"></span><span class="card-corner bl" aria-hidden="true"></span>`;
}

export function initials(name) {
  // articles never carry identity: "a heavy iron key" reads "HI", not "AH"
  // (live find: an image-less pack item showed the letters "AH" in its slot)
  const parts = String(name || "?").split(/\s+/).filter((p) => p);
  const meaningful = parts.filter((p) => !/^(a|an|the)$/i.test(p));
  return (meaningful.length ? meaningful : parts)
    .slice(0, 2)
    .map((part) => part[0] || "")
    .join("")
    .toUpperCase();
}

const APRESENTACAO_ENUM = { male: "Masculino", female: "Feminino", nonbinary: "Não binário", done: "Concluída", failed: "Fracassada", active: "Ativa", won: "Vitória", lost: "Derrota", calm: "Calmo", tense: "Tenso", dangerous: "Perigoso", unknown: "Desconhecido", friendly: "Amigável", neutral: "Neutro", hostile: "Hostil", off: "Desativado", sometimes: "Às vezes", often: "Frequentemente", easy: "Fácil", normal: "Normal", hard: "Difícil" };

export function titleCase(value) {
  const original = String(value || "");
  const normalized = original.toLowerCase().replace(/[-_]+/g, " ");
  if (APRESENTACAO_ENUM[normalized]) return APRESENTACAO_ENUM[normalized];
  return original
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

// The unread-whisper alert: a small count badge for a character with private
// beats the player has not yet read. Zero renders nothing. `cls` lets the cast
// card (a floating dot) and the Whisper tab (an inline pill) style it apart
// while reading the SAME count. A real number for screen readers; 9+ caps the
// glyph width.
export function unreadBadge(count, cls = "") {
  const n = Number(count) || 0;
  if (n < 1) return "";
  const label = n === 1 ? "1 sussurro não lido" : `${n} sussurros não lidos`;
  return `<span class="pm-unread${cls ? ` ${cls}` : ""}" role="status" aria-label="${escapeHtml(label)}" title="${escapeHtml(label)}">${n > 9 ? "9+" : n}</span>`;
}
