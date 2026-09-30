# Como trabalhar com o Claude Code em ciclos

## Ciclo padrão (uma etapa por sessão)

```text
/clear
 ↓
Claude lê CLAUDE.md (automático) → docs/plan/STATUS.md → seção da etapa no arquivo de fase
 ↓
Claude lê SÓ os documentos listados em "Ler antes" da etapa
 ↓
Claude confirma em 3–5 linhas o que vai fazer (e pergunta se algo estiver ambíguo)
 ↓
Implementa → testa (make check) → revisa o próprio diff
 ↓
Atualiza STATUS.md, ADRs (se houver decisão), docs de arquitetura (se mudou), sessão em history/
 ↓
Commit "EXX: <resumo>" (e push, se combinado)
 ↓
Humano verifica → /clear
```

## Prompt sugerido para iniciar uma sessão

> Leia o CLAUDE.md e o docs/plan/STATUS.md. Execute a próxima etapa do plano seguindo o
> ritual. Ao final, atualize a documentação e me mostre o que verificar.

Para uma etapa específica:

> Leia o CLAUDE.md e o STATUS.md e execute a etapa E07.

## Regras para o Claude durante uma etapa

1. **Uma etapa por sessão.** Se terminar cedo, não comece a próxima sem pedido.
2. Se a etapa se mostrar grande demais (> ~1 sessão), **pare**, divida em EXXa/EXXb no
   arquivo de fase, atualize STATUS e execute só a primeira parte.
3. Se encontrar uma decisão não prevista e questionável → ADR (curto) antes de seguir.
4. Se precisar mudar a arquitetura → atualizar o doc de arquitetura na mesma sessão.
5. Não ler a documentação inteira "por garantia" — seguir o "Ler antes" da etapa.
6. Nada de rede em testes; conectores usam fixtures gravadas.
7. Chaves de API nunca em código/commit; usar `.env`.
8. Se um problema ficar aberto, registrar em STATUS → "Problemas abertos".

## O que o humano verifica ao fim de cada etapa

- O "Critério de conclusão" da etapa está atendido? (listado no arquivo de fase)
- `make check` passa?
- STATUS.md foi atualizado e aponta a próxima etapa correta?
- Para conectores: amostra de 10 itens reais revisada faz sentido?

## Registro de sessão (`docs/history/sessions/AAAA-MM-DD-EXX.md`)

Curto (≤ 30 linhas): o que foi feito, decisões, problemas, métricas relevantes,
próximos passos. Serve para auditoria e para arquivar contexto que sai do STATUS.
