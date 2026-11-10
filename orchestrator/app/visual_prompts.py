"""Short English conditioning for image models with a small text encoder."""
import json

from . import llm


def compact_english_prompt(source: str, word_budget: int, *, style: str = "", character: bool = False) -> str:
    instructions = (
        "You design a concrete image from roleplaying source material. "
        "The STYLE field is authoritative: ignore any conflicting older artistic style "
        "mentioned in SUBJECT. Do not translate the "
        "whole source paragraph. Output ONLY a JSON object with four English string fields: "
        '"style" (artistic medium, at most six words), "subject" (visible physical details), '
        '"clothing" (concrete outfit, empty for scenes), "lighting" (at most four words). '
        "The subject and clothing each use at most ten words for a character. "
        f"For a scene, use at most {max(10, word_budget - 10)} words for its visible subject. "
        "Preserve the supplied science-fiction, "
        "fantasy, painted or illustrated style; do not replace it with photography. "
        "Discard plot, proper names, percentages, abstract personality and literary metaphors. "
        "Do not describe written words, diagrams, anatomy studies or reference-sheet panels. "
        "Describe a single coherent illustration. Do not put environments in a character's "
        "style or physical description. Do not include names or personality in the subject."
    )
    if character:
        instructions += (
            " The subject is ONE person. Preserve explicit physical traits and clothing. "
            "When clothing is unspecified, give them a fully clothed outfit appropriate to "
            "their role and setting. A synchronization score is not a physical feature. "
            "Keep clothing and human identity explicit; do not turn people into mannequins, "
            "robots or exposed anatomy unless the source explicitly says they are nonhuman. "
            "Do not add a pose, shot type or background: the renderer adds those per view."
        )
    messages = [{"role": "system", "content": instructions}]
    if character:
        messages.extend([
            {"role": "user", "content": "STYLE: Pintura de fantasia científica. SUBJECT: Homem, herdeiro de uma família militar, 0% de sincronização, inteligente e observador. Aparência não informada."},
            {"role": "assistant", "content": '{"style":"Epic sci-fi fantasy painting","subject":"young human man, alert eyes, short dark hair","clothing":"dark military pilot jacket, steel shoulder guards, crystal accents","lighting":"dramatic blue rim lighting"}'},
            {"role": "user", "content": "STYLE: Ilustração medieval pintada. SUBJECT: Uma médica idosa, gentil e sábia, com cabelos brancos e olhos verdes."},
            {"role": "assistant", "content": '{"style":"Painterly medieval fantasy illustration","subject":"elderly human woman, white hair, green eyes","clothing":"long dark healer robe, leather medicine pouch","lighting":"warm candlelight"}'},
        ])
    messages.append({"role": "user", "content": f"STYLE: {style}\nSUBJECT: {source}"})
    reply = llm.chat(messages, output_language="en", max_tokens=200)
    raw_prompt = (reply.content or "").strip()
    if not raw_prompt or reply.finish_reason == "length":
        raise ValueError("image prompt translation did not finish")
    if raw_prompt.startswith("```"):
        raw_prompt = raw_prompt.split("\n", 1)[1].rsplit("```", 1)[0]
    visual_fields = json.loads(raw_prompt)
    field_limits = {"style": 6, "subject": 10 if character else max(10, word_budget - 10),
                    "clothing": 10, "lighting": 4}
    prepared_fields = {
        field_name: " ".join(str(visual_fields.get(field_name) or "").split()[:word_limit]).strip(" ,.")
        for field_name, word_limit in field_limits.items()
    }
    if not prepared_fields["style"] or not prepared_fields["subject"]:
        raise ValueError("image prompt is missing its subject or artistic style")
    subject = prepared_fields["subject"]
    if character:
        if not prepared_fields["clothing"]:
            raise ValueError("character image prompt is missing its outfit")
        subject = f"fully clothed {subject}, wearing {prepared_fields['clothing']}"
    return ", ".join(part for part in (prepared_fields["style"], subject, prepared_fields["lighting"]) if part)
