# ADR-026 — Contatos públicos institucionais: extração por regra, só do domínio da organização

- **Status:** aceito
- **Data:** 2026-10-01
- **Etapa:** E19

## Contexto
Com o site oficial da organização (E18 ou semente), falta saber **como contatá-la**. A LGPD
(`docs/research/legal-and-compliance.md`) pede minimização: contatos institucionais, nada inferido, nada de pessoas
no LinkedIn. O ambiente do Claude não alcança sites reais: **nada foi testado em páginas de verdade**, só em HTML gravado.

## Decisão
1. **Sem IA** (`extraction/contacts.py`, pura): `mailto:`, `tel:`, `wa.me`/`api.whatsapp.com`, e-mail e telefone no
   texto visível, JSON-LD (`email`, `telephone`, `sameAs`), links de redes e formulário de contato.
2. **Páginas:** a inicial + até 4 do **mesmo domínio**, escolhidas pelo caminho/texto do link (contato e fale conosco
   primeiro; depois atendimento/matrícula; depois sobre/institucional), no máx. 5 por site, via `PoliteFetcher`
   (robots, rate limit, cache 304). Falha numa página só a descarta; site inacessível fica marcado como verificado.
3. **E-mail:** só do domínio do site (ou subdomínio/pai) com confiança 0,9; webmail publicado no site entra com 0,6;
   domínio alheio (agência, hospedagem) é ignorado. Endereços de modelo/imagem são ignorados. Nada é gerado ou
   «adivinhado»; e-mail ofuscado é perda aceita.
4. **Institucional × pessoal:** caixa de função (`contato`, `secretaria`, `coordenacao`…) é institucional;
   `nome.sobrenome` é gravado com `is_personal=True` (publicado pela própria organização); palavra única desconhecida
   fica institucional. É heurística: o humano revisa no admin.
5. **Telefone:** E.164 (`+55…`), DDD 11–99, fixo 2–5xxx, celular 9xxxx; no texto exige DDD entre parênteses, `+55` ou
   separador (não confunde CEP/CNPJ). `0800` não é extraído.
6. **Redes:** só perfil/página da organização (Instagram, Facebook, YouTube, LinkedIn `company`/`school`); nunca
   `linkedin.com/in/`. Se o site aponta **mais de um** perfil da mesma rede, nenhum é gravado (pode ser a agência).
7. **Evidência e opt-out:** cada contato tem `Evidence` **observada** (`regex:contacts`, URL da página, trecho
   literal verificado contra o texto). Organização em `Suppression` (ou `do_not_contact`) nem é visitada; e-mail,
   telefone e domínio suprimidos não viram contato. Uso/exibição continua por `ContactPoint.objects.usable()`.
8. **Idempotência:** contato existente (mesmo `organização+tipo+valor`) não é alterado (preserva edição e
   `bounced`/`invalid`); só renova a evidência. **Achar ≠ verificar:** `last_verified_at` fica vazio na extração; sem verificação por SMTP nem serviços de terceiros (ADR-005). `Organization.contacts_checked_at` (migration
   `core.0005`) evita reler o mesmo site toda execução; `--refresh` relê.
9. **Logs públicos:** o comando imprime só contagens e a cobertura (% de organizações com site e ≥ 1 contato
   institucional utilizável). Nenhum valor de contato sai nos logs (ADR-014).

## Consequências
+ Custo zero; reexecutável; nada sem fonte; opt-out respeitado antes e depois.
− Heurística pessoal × institucional pode errar nos dois sentidos.
− Sites só em JavaScript, e-mails ofuscados e Cloudflare «email protection» não são lidos.
− Nenhum site real foi testado; a amostra de 20 conferida à mão é pendência do humano (P14).
