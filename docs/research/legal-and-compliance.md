# Legalidade, ética e compliance

> Não é parecer jurídico. É o conjunto de regras de engenharia que reduz risco jurídico e
> reputacional. Revisar com profissional quando houver receita recorrente (a empresa já é MEI).

## LGPD — pontos que afetam o design

1. **Dados de empresas** (CNPJ, razão social, CNAE, endereço comercial) **não são dados
   pessoais**. Dados de **pessoas** (nome, e-mail nominal, telefone celular, cargo de
   alguém identificado) **são**, mesmo em contexto profissional.
2. Base legal típica para prospecção B2B: **legítimo interesse** (art. 7º, IX; art. 10),
   exigindo: finalidade legítima e específica, necessidade (mínimo de dados),
   expectativa razoável do titular, transparência e respeito à oposição.
3. **Dados tornados públicos** pelo titular podem ser tratados, mas respeitando a
   finalidade original e os direitos do titular (art. 7º, §§ 3º, 4º e 7º).
4. Direitos do titular: acesso, correção, eliminação, **oposição** → precisamos de opt-out efetivo.

## Regras de design derivadas

| Regra | Implementação |
|---|---|
| Minimização | Coletar **contatos institucionais** (contato@, secretaria@, telefone fixo, formulário). Dado pessoal só quando publicado pela própria organização em papel profissional, marcado `is_personal=true` |
| Sem inferência de contatos | Nunca gerar e-mails por padrão (`nome.sobrenome@`), nunca "descobrir" celulares |
| Rastreabilidade | Toda informação com URL, data e trecho (`Evidence`) — responde "de onde veio o dado?" |
| Opt-out | Tabela `Suppression` (e-mail, telefone, domínio, organização) consultada sempre; pedido de remoção atendido em até 15 dias com exclusão dos dados pessoais |
| Retenção | Dados pessoais de leads sem interação em 12 meses → anonimizar/excluir (job na Fase 4) |
| Transparência na abordagem | Toda mensagem identifica a Scorpion Bits, explica por que estamos contatando e oferece forma simples de não ser mais contatado |
| Histórico de interações | Nomes/cargos de contatos só no banco (nunca em git/CSV versionado); mínimo necessário; enviados apenas a provedores de IA pagos ou locais |
| Sem sensíveis | Nenhum dado sensível (art. 5º, II) é coletado |
| Segurança | Banco local/servidor com acesso restrito; segredos fora do git; backups protegidos |
| Registro | Manter este documento como "registro de tratamento" simplificado; com receita/escala, avaliar RIPD |

## Scraping, robots.txt e termos de uso

- Respeitar `robots.txt` sempre; User-Agent identificado com contato.
- Rate limit conservador (1 req/5 s por domínio padrão); cache para não repetir.
- Não contornar login, captcha, paywall, bloqueio de IP.
- **Não raspar** LinkedIn, Google Search, Google Maps, Instagram/Facebook (termos proíbem).
  Links para perfis que **a própria organização** publica no site podem ser armazenados.
- Preferir **APIs oficiais e dados abertos** (INEP, Receita, IBGE, PNCP, Querido Diário,
  Mapas Culturais) — licenças abertas e uso previsto.
- Respeitar licenças: OSM (ODbL, atribuição), dados gov.br (geralmente CC-BY/aberta).
- Google Places API: termos restringem armazenar conteúdo (exceto `place_id`) → não usar como base.

## Boas práticas de prospecção (anti-spam)

1. Pesquisa → qualificação → personalização → contato **1-a-1** feito por humano.
2. Nunca contatar a mesma organização por canais múltiplos em sequência automática.
3. Registro de todas as interações (Fase 4) para não repetir contato.
4. Máximo de follow-ups por organização (sugestão: 2) e intervalo mínimo (sugestão: 7 dias).
5. WhatsApp: só números **publicados pela organização** como canal de atendimento; nada de
   disparo em lista; conteúdo relevante e identificado.
6. E-mail: no futuro, se houver envio via sistema, usar domínio próprio com SPF/DKIM/DMARC,
   volumes baixos e link de descadastro.

## Checklist por nova fonte

- [ ] Termos de uso permitem acesso automatizado/reuso?
- [ ] robots.txt permite os caminhos usados?
- [ ] Licença dos dados (atribuição necessária?)
- [ ] Contém dados pessoais? Quais e por quê são necessários?
- [ ] Frequência de acesso respeitosa?

## Referências

- LGPD (Lei 13.709/2018): https://www.planalto.gov.br/ccivil_03/_ato2015-2018/2018/lei/l13709.htm
- ANPD — guia orientativo sobre legítimo interesse: https://www.gov.br/anpd
- Síntese de práticas B2B/LGPD: https://speedio.com.br/blog/lgpd-na-prospeccao-b2b-como-usar-dados-de-contato-dentro-da-lei-sem-travar-as-vendas/ ; https://leadcnpj.com.br/blog/lgpd-na-prospeccao-b2b/
- OSMF API usage policy: https://operations.osmfoundation.org/policies/api/
