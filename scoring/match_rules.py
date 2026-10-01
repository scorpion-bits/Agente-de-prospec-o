"""Regras v1 do matching (E20, ADR-027): **dados**, não código.

Cada regra liga uma condição sobre a organização a serviços do catálogo. Para mudar o que é
sugerido, edite esta lista (ou o catálogo/portfólio no admin): o motor em `scoring/matching.py`
não muda. Slugs de serviço que não existem (ou inativos) são ignorados.

Campos de uma regra:
- `id`: nome estável (vai no motivo e no método de evidência).
- `when`: lista de condições alternativas (basta uma valer); dentro de cada uma, todas as
  chaves precisam valer. Chaves: `kinds`, `tags_any`, `network_any`, `stages_any` (trechos do
  nome da etapa de ensino, sem acento), `stages_exact`, `name_any` (trechos do nome ou segmento),
  `keywords_any` (trechos no nome, segmento ou trechos de evidência), `website_status`.
- `services`: slugs do catálogo.
- `strength`: 0–1; sem item de portfólio que prove, vira 70% disso (Fit menor).
- `reason`: texto legível (é uma **hipótese**: `inferred`).
- `proof`: como achar a prova no portfólio: `tags_any` (capacidades) e/ou `kinds`.
"""

RULES: list[dict] = [
    {
        "id": "sesc_courses",
        "when": [
            {"kinds": ["sesc"]},
            {"tags_any": ["educacao_nao_formal", "cultural_publico", "sistema_s"]},
        ],
        "services": ["course_gamedev", "workshop_gamedev", "game_jam_org"],
        "strength": 0.9,
        "reason": (
            "SESC ou organização parecida: oferece cursos e oficinas livres ao público, "
            "o formato do Game Lab já realizado no SESC Araraquara."
        ),
        "proof": {"tags_any": ["ensino_presencial"], "kinds": ["course"]},
    },
    {
        "id": "school_upper_grades",
        "when": [
            {
                "kinds": ["school"],
                "stages_any": ["anos finais", "ensino medio"],
            },
            {"kinds": ["school"], "stages_exact": ["ensino fundamental"]},
        ],
        "services": ["extracurricular_school", "course_gamedev"],
        "strength": 0.8,
        "reason": (
            "Escola privada com ensino fundamental II ou médio: público da idade certa "
            "para atividade extracurricular e curso de jogos."
        ),
        "proof": {"tags_any": ["ensino_presencial"], "kinds": ["course"]},
    },
    {
        "id": "technical_school",
        "when": [
            {"tags_any": ["educacao_tecnica"]},
            {"stages_any": ["profissional", "tecnic"]},
            {"kinds": ["school"], "name_any": ["tecnic", "informatica"]},
        ],
        "services": ["course_gamedev", "workshop_gamedev"],
        "strength": 0.75,
        "reason": "Ensino técnico ou de informática: curso e oficina de jogos combinam.",
        "proof": {"tags_any": ["ensino_presencial"], "kinds": ["course"]},
    },
    {
        "id": "school_generic",
        "when": [{"kinds": ["school"]}],
        "services": ["workshop_gamedev"],
        "strength": 0.4,
        "reason": (
            "Escola privada: oficina pontual de jogos como porta de entrada (hipótese fraca)."
        ),
        "proof": {"tags_any": ["ensino_presencial"], "kinds": ["course"]},
    },
    {
        "id": "mentions_games",
        "when": [
            {
                "keywords_any": [
                    "gamificacao",
                    "gamificar",
                    "jogos educativos",
                    "jogo educativo",
                    "game based learning",
                ]
            }
        ],
        "services": ["educational_game", "gamification"],
        "strength": 0.6,
        "reason": "O que a organização publica cita gamificação ou jogos educativos.",
        "proof": {"tags_any": ["jogos"], "kinds": ["game"]},
    },
    {
        "id": "no_website",
        "when": [{"website_status": "not_found"}],
        "services": ["institutional_site"],
        "strength": 0.35,
        "reason": "Nenhum site oficial foi encontrado na busca (hipótese fraca).",
        "proof": {"tags_any": ["web"], "kinds": ["website"]},
    },
]
