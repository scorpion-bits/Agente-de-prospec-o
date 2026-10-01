"""Vocabulário de `Organization.similarity_tags` ("parecida com o SESC", E17b, ADR-024).

Tag fora desta lista é rejeitada pelo conector: o filtro do admin e o perfil `lead.sesc`
(docs/architecture/scoring.md) dependem de nomes estáveis.
Para adotar uma tag nova, acrescente-a aqui.
"""

SIMILARITY_TAGS = {
    "sistema_s": "Sistema S (SENAC, SESI, SENAI…)",
    "cultural_publico": "Cultura / equipamento cultural público",
    "educacao_nao_formal": "Educação não formal (oficinas, cursos livres)",
    "educacao_tecnica": "Ensino técnico e tecnológico",
    "ensino_superior": "Ensino superior / extensão universitária",
    "poder_publico_municipal": "Prefeitura (secretarias)",
    "ciencia_cultura": "Centro de ciência / divulgação científica",
    "baixa_prioridade": "Sem contratação externa conhecida",
}


def clean_tags(raw: str, *, separator: str = "|") -> list[str]:
    """Tags válidas, sem repetição e na ordem dada; tag desconhecida levanta `ValueError`."""
    tags: list[str] = []
    for part in raw.split(separator):
        tag = part.strip().casefold()
        if not tag or tag in tags:
            continue
        if tag not in SIMILARITY_TAGS:
            raise ValueError(
                f"tag de similaridade {tag!r} desconhecida (use: {', '.join(SIMILARITY_TAGS)})."
            )
        tags.append(tag)
    return tags
