"""Conservative context-window accounting shared by prompt builders and LLM calls."""
import json
from .config import settings

# Approximation deliberately errs high for Portuguese prose plus JSON tool schemas.
CHARS_PER_TOKEN = 3
LANGUAGE_TOKENS = 170
OUTPUT_RESERVE = 1024


class ContextLimitError(ValueError):
    """The request cannot safely fit without losing unsummarized history."""


def estimate_tokens(messages: list[dict], tools: list[dict] | None = None) -> int:
    characters = sum(len(str(message.get("content") or "")) + 12 for message in messages)
    tool_characters = len(json.dumps(tools, ensure_ascii=False, separators=(",", ":"))) if tools else 0
    return (characters + tool_characters + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN + LANGUAGE_TOKENS


def available_output(messages: list[dict], tools: list[dict] | None, requested: int) -> int:
    """Never ask the backend to generate beyond the configured model window."""
    remaining = max(0, settings.LLM_CONTEXT_SIZE - estimate_tokens(messages, tools) - OUTPUT_RESERVE)
    if requested > 0:
        return min(requested, remaining)
    return remaining


def keep_recent(history_entries: list, render_history_entry, budget_tokens: int) -> list:
    """Return newest complete entries that fit; never cut an entry silently."""
    kept, used = [], 0
    for history_entry in reversed(history_entries):
        cost = max(1, (len(render_history_entry(history_entry)) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN)
        if kept and used + cost > budget_tokens:
            break
        if cost > budget_tokens:
            break
        kept.append(history_entry)
        used += cost
    return list(reversed(kept))


def summarize(previous: str, passages: list[str], build_messages, cancel=None, max_tokens=None) -> str:
    """Fold all passages in bounded requests. Never accept partial/truncated memory."""
    from . import llm
    from .engine.parsing import scrub_model_text

    pending = "\n".join(passages)
    summary = previous
    while pending:
        base_cost = estimate_tokens(build_messages(summary, ""))
        capacity = min(settings.CONTEXT_FOLD_BATCH_TOKENS,
                       int(settings.LLM_CONTEXT_SIZE * settings.CONTEXT_COMPACT_AT) - base_cost)
        if capacity < 128:
            raise ContextLimitError("O resumo e as regras excedem a janela do modelo. Aumente LLM_CONTEXT_SIZE e a janela no servidor.")
        chunk_size = min(len(pending), capacity * CHARS_PER_TOKEN)
        if chunk_size < len(pending):
            boundary = max(pending.rfind("\n", 0, chunk_size), pending.rfind(" ", 0, chunk_size))
            if boundary > chunk_size // 2:
                chunk_size = boundary + 1
        # A long individual beat can span batches; its cursor only advances after ALL succeed.
        passage, pending = pending[:chunk_size], pending[chunk_size:]
        reply = llm.chat(build_messages(summary, passage),
                         max_tokens=settings.SUMMARY_MAX_TOKENS if max_tokens is None else max_tokens,
                         cancel=cancel, thinking=False)
        compacted = scrub_model_text(reply.content or "")
        if not compacted or reply.finish_reason == "length":
            raise ContextLimitError("Não foi possível concluir a compactação. O histórico foi preservado; tente novamente.")
        if estimate_tokens(build_messages(compacted, "")) >= int(settings.LLM_CONTEXT_SIZE * settings.CONTEXT_COMPACT_AT):
            raise ContextLimitError("O resumo gerado ficou grande demais. O histórico foi preservado; tente novamente.")
        summary = compacted
    return summary


def prepare_beats(conn, game_id: str, history: list, budget_tokens: int, character=None) -> list:
    """Replace only fully summarized turns; keep the complete current turn verbatim."""
    from . import repo, prompts
    from .engine import live

    kept = keep_recent(history, prompts._render_beat, budget_tokens)
    if not history:
        return kept
    if not kept:
        kept = [history[-1]]
    # Never omit part of the oldest retained turn (cursors are expressed in turns).
    first_turn = kept[0]["turn_index"] if kept else history[-1]["turn_index"] + 1
    if character is None:
        owner = repo.get_game(conn, game_id)
        previous = owner["story_summary"] or ""
    else:
        owner = repo.get_character(conn, character["id"])
        previous = owner["memory_summary"] or ""
    done = owner["summarized_through"] or 0
    target = first_turn - 1
    if target > done:
        rows = (repo.beats_between(conn, game_id, done, target) if character is None else
                repo.witnessed_beats_between(conn, game_id, character["id"], done, target))
        if rows:
            builder = (prompts.build_summary_messages if character is None else
                       lambda summary, transcript: prompts.build_character_summary_messages(character["name"], summary, transcript))
            summary = summarize(previous, [prompts._render_beat(row) for row in rows], builder,
                                cancel=live.stop_event(game_id),
                                max_tokens=settings.SUMMARY_MAX_TOKENS if character is None else settings.CHAR_SUMMARY_MAX_TOKENS)
            current = (repo.get_game(conn, game_id) if character is None else
                       repo.get_character(conn, character["id"]))
            summary_field = "story_summary" if character is None else "memory_summary"
            if not current or (current["summarized_through"] or 0) != done or (current[summary_field] or "") != previous:
                raise ContextLimitError("A memória mudou durante a compactação. Tente novamente.")
            if character is None:
                repo.set_story_summary(conn, game_id, summary, target)
            else:
                repo.set_character_summary(conn, character["id"], summary, target)
    # LIMIT may have split the first turn. Fetch that turn in full so nothing falls in a gap.
    if kept:
        first_rows = (repo.beats_between(conn, game_id, first_turn - 1, first_turn) if character is None else
                      repo.witnessed_beats_between(conn, game_id, character["id"], first_turn - 1, first_turn))
        kept = list(first_rows) + [row for row in kept if row["turn_index"] > first_turn]
    return kept
