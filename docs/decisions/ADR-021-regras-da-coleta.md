# ADR-021 — Regras da infra de coleta (fetcher, runner e documentos brutos)

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E04

## Contexto
`connectors.md` define o contrato e as regras de coleta responsável, mas deixou em aberto como tratar
robots.txt indisponível, bloqueios, simulação (`--dry-run`), retenção e a evidência de CSV curado.

## Decisão
1. **robots.txt:** 404/410 = sem restrições (RFC 9309); 401/403, 5xx ou fora do ar = **fallback
   conservador**, nada é baixado daquele site. Cache de 24 h por origem; vale também a cada redirecionamento.
2. **Bloqueio não se contorna:** robots que proíbe ou 401/403 levantam erro; o runner **desabilita a
   fonte** e registra em `CollectionRun.error_log` para revisão humana (`robots_ok` volta só por
   decisão humana). Em `--dry-run` a fonte não é alterada.
3. **Portões antes de coletar:** fonte com rede exige `robots_ok`; `collect --all` só roda `enabled`;
   `collect <slug>` numa fonte desabilitada só vale com `--dry-run` (para avaliar antes de ligar).
4. **`--dry-run` roda o conector de verdade** (rede incluída) mas desfaz tudo na transação, exceto o
   próprio `CollectionRun` (`dry_run=True`): dá para ver "o que entraria" e a execução fica auditada.
5. **Isolamento:** cada item roda em um savepoint (item ruim não derruba a fonte); erro do conector
   termina só a fonte (`partial` se já havia itens, `error` se não); o comando sai com erro só se alguma
   fonte falhou por inteiro.
6. **`RawDocument` único por URL**, só texto (gzip), com hash, ETag e `expires_at`. Re-coleta atualiza a
   linha; o histórico de mudanças está nas `Evidence`. A retenção (`purge_raw_documents`) apaga **o
   texto** e mantém URL/hash, para as evidências nunca ficarem órfãs. Binários são recusados (ADR-010).
7. **Evidência do `seed_csv`:** com `source_url` → `observed`; sem → `manual`/`human`. Nunca
   "observado" sem fonte (ADR-004).
8. **Logs públicos (ADR-014):** `collect` imprime só contagens e nomes de fonte; as mensagens de erro
   (tipo + mensagem curta, sem o conteúdo do item) ficam só no banco.
9. **Memória comercial no upsert:** organização via `get_or_create_organization` (já reconhece as
   contatadas); oportunidade liga ao organizador **só se ele já existe**, nunca cria organização.

## Alternativas consideradas
| Alternativa | Por que não |
|---|---|
| robots.txt fora do ar = liberado | Pode estar fora do ar justamente porque o site nos bloqueou |
| `--dry-run` sem rede | Esconderia os problemas que o dry-run existe para mostrar |
| Um `RawDocument` por download | O banco Free tem 500 MB; o histórico útil já está nas evidências |

## Consequências
+ Uma fonte nova = uma classe (ou só uma linha `Source` para `seed_csv`) + fixture + teste.
− O `httpx` registra as URLs em INFO nos logs: aceitável (fontes públicas), mas não coletar URLs com
  dado pessoal em `query string`.
− `max_pages` por fonte (padrão 20) e 1 req/5 s tornam coletas grandes lentas de propósito.
