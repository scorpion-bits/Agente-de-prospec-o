"""Apresentação do `Score` no admin: rótulo com texto + cor e o breakdown linha a linha (E13).

A cor nunca é o único sinal (ADR-004): o rótulo vem sempre escrito.
"""

from django.contrib.contenttypes.models import ContentType
from django.db.models import OuterRef, Subquery
from django.utils import timezone
from django.utils.html import format_html, format_html_join

from scoring.models import Score

COLORS = {
    Score.Label.PRIORITIZE: "#1a7f37",
    Score.Label.EVALUATE: "#9a6700",
    Score.Label.LOW: "#57606a",
    Score.Label.IGNORE: "#8c959f",
    Score.Label.GATED: "#cf222e",
    Score.Label.ONGOING: "#0969da",
}


def annotate_scores(queryset, model):
    """Anota `_score_total` e `_score_label` (para ordenar a lista de `model` pela nota)."""
    content_type = ContentType.objects.get_for_model(model)
    scores = Score.objects.filter(content_type=content_type, object_id=OuterRef("pk"))
    return queryset.annotate(
        _score_total=Subquery(scores.values("total")[:1]),
        _score_label=Subquery(scores.values("label")[:1]),
    )


def label_badge(label: str | None, total: int | None):
    if not label:
        return "—"
    name = dict(Score.Label.choices)[label]
    shown = name if total is None else f"{total} · {name}"
    return format_html('<b style="color:{}">{}</b>', COLORS[label], shown)


def breakdown_html(score: Score | None):
    """O «por que N/100»: uma linha por fator, com peso, pontos e explicação."""
    if score is None:
        return "Ainda não pontuada (rode `make rescore`)."
    head = format_html(
        "<p><b>{}</b> · perfil <code>{}</code> · versão {} · calculada em {}</p>",
        label_badge(score.label, score.total),
        score.profile,
        score.scoring_version,
        timezone.localtime(score.computed_at).strftime("%d/%m/%Y %H:%M"),
    )
    if score.gated:
        return head + format_html("<p><b>Bloqueada:</b> {}</p>", score.gate_reason)
    rows = format_html_join(
        "",
        "<tr><td><b>{}</b> {}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>",
        (
            (
                row["factor"],
                row["label"],
                f"{row['raw']:.2f}".replace(".", ","),
                f"{row['weight']:.2f}".replace(".", ","),
                f"{row['points']:.1f}".replace(".", ","),
                format_html("{}{}", row["explanation"], _support(row)),
            )
            for row in score.breakdown
        ),
    )
    summary = format_html(
        "<p>Soma ponderada {} · confiança K = {} → <b>{}/100</b></p>",
        f"{score.raw_sum:.3f}".replace(".", ","),
        f"{score.confidence:.3f}".replace(".", ","),
        score.total,
    )
    alerts = format_html_join("", "<li>⚠ {}</li>", ((a,) for a in score.alerts))
    table = format_html(
        "<table><thead><tr><th>Fator</th><th>Nota</th><th>Peso</th><th>Pontos</th>"
        "<th>Por quê</th></tr></thead><tbody>{}</tbody></table>",
        rows,
    )
    return head + table + summary + (format_html("<ul>{}</ul>", alerts) if score.alerts else "")


def _support(row: dict):
    ids = row.get("evidence_ids") or []
    if not ids:
        return " [sem evidência]"
    kind = "observado" if row.get("support") == 1 else "inferido"
    refs = ", ".join(f"#{i}" for i in ids)
    return f" [{kind}; evidência {refs}]"
