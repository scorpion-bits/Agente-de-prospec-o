# ADR-027 — Matching serviço ↔ organização ↔ portfólio por regras em dados

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E20

## Contexto
O sistema precisa sugerir «a organização X compraria o serviço Y, porque…, prova: trabalho Z». O catálogo é pequeno e
as correlações são explícitas (`docs/agents/README.md`, ficha 4): regras bastam, sem IA (princípio 1).

## Decisão
1. **Regras são dados** (`scoring/match_rules.py`: condição → serviços → força → razão → prova); o motor
   (`scoring/matching.py`) é genérico. Condições: tipo, tags de similaridade, rede, etapas de ensino (INEP), trechos do
   nome/segmento, palavras em trechos de evidência, situação do site. Serviço inexistente ou inativo é ignorado.
2. **Razões:** a hipótese é `inferred`; os fatos que a sustentam são `observed` e citam a `Evidence` quando existe
   (etapas de ensino, trecho com «gamificação»). Tipo/tags/situação do site vêm do próprio cadastro (`evidence_id` nulo).
3. **Prova de portfólio:** só itens `public=True` e com situação diferente de «a confirmar» (não se cita o que não é
   público nem o que não se sabe se fizemos, ex.: o site da empresa). Escolhida por capacidade/tipo da regra, não por
   serviço fixo: novo item no admin já vira prova. Sem prova, a força cai para **70 %** (Fit menor, ADR-012).
4. **Limite:** no máximo **3 matches por organização**, os mais fortes (regras genéricas demais diluiriam a lista).
   Duas regras para o mesmo serviço: vale a mais forte.
5. **Reexecutável:** `match_services` atualiza os `Match` de método `rules_v1` e **remove** os que deixaram de valer;
   `--dry-run` não grava. Saída só com contagens (ADR-014).
6. **Sem filtro geográfico, de relacionamento ou de opt-out aqui:** isso é pontuação (E21: gates de memória, geo).
7. **IA opcional (justificativa do top-20) não implementada:** nada a justificar sem uso real ainda.

## Consequências
+ Custo zero, explicável, testável; mudar regra é editar dados.
− Escola sem etapas informadas só recebe o match fraco (oficina); palavras-chave só enxergam o que já virou evidência.
− Valores de força são hipóteses a calibrar com respostas reais.
