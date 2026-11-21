# Sign in with ChatGPT — arquitetura e segurança

**Status na V0.2 (Sprint 1):** integração via bridge oficial `@siwc/local` implementada no código. **PASS_REAL do login no notebook ainda pendente** — não declarar “login funcional” até validação manual.

Referências oficiais:
- https://developers.openai.com/siwc/quickstart
- https://developers.openai.com/siwc/token-sharing-open-source
- https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt
- https://github.com/openai/sign-in-with-chatgpt-devkit
- https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus

## Decisão de empacotamento

| Item | Decisão |
| --- | --- |
| SDK | `@siwc/local` do DevKit oficial (Node.js ≥ 22), pinado em `vendor/siwc-local` (`PIN.txt`) |
| Registro npm | Pacote `private: true` no upstream; **não** instalamos `@siwc/local` do registry público |
| Licença do SDK | Sign-in with ChatGPT DevKit **Noncommercial License v1.0** (separada do MIT do Ryoku) |
| Runtime | CLI Python chama `siwc_bridge/src/bridge.mjs` (NDJSON). Sem reinventar OAuth |
| Criptografia Linux | `keytar` → Secret Service / KWallet; AES-256-GCM no arquivo. **Sem** `basic_text`, plaintext ou fallback inseguro |
| Host ID | Gerado/persistido pelo SDK (`sendHostId: true`); opaco; não usamos hostname/e-mail/serial |
| Fora de escopo | Tokens Codex/Cursor, cookies do navegador, chave de API cobrada à parte |

Se o bridge Node ou o chaveiro estiverem ausentes, `ryoku login` / `chat` falham fechados com mensagem clara. O `ryoku doctor` continua sem dependências de rede.

### Avaliação de licença

O código original do Ryoku permanece **MIT**. O diretório `vendor/siwc-local` e o uso do DevKit ficam sob a licença Noncommercial da OpenAI: uso pessoal/aprendizado/desenvolvimento sem aplicação comercial prevista. Uso comercial do Contribution da OpenAI exige acordo escrito com a OpenAI. Redistribua o NOTICE/LICENSE do DevKit junto com qualquer cópia do vendor.

### O que não fazer

Não usar `chatgpt-plan-auth` (terceiros) como substituto do SDK oficial. Não implementar OAuth “na mão” copiando endpoints. Se o pin do DevKit ficar incompatível ou a OpenAI retirar o fluxo OSS, documente o bloqueio e pare — não invente autenticação.

## Regras de implementação

1. **Não confundir Plus com API paga.** A API tradicional é faturada à parte. O SIWC para OSS local depende de consentimento, escopos, elegibilidade e limites próprios.
2. O login usa SDK oficial: **navegador do sistema, loopback 127.0.0.1, PKCE, state, nonce, ID token verificado e escopos autorizados**.
3. `ext_agent_host_id` opaco e persistente por instalação (SDK).
4. Credenciais protegidas por **Secret Service/GNOME Keyring ou KWallet**. Falhar fechado se indisponível.
5. Verificar `session.sharing` antes das solicitações de IA.
6. Modelos descobertos após login (`ryoku models`); não presumir slugs.
7. Histórico local é **opt-in**; o chat atual não grava conversas automaticamente.
8. Sem shell irrestrito nem `sudo` automático.
9. Plugin Omarchy (Sprint 3): reutilizar Quickshell oficial.

## Comandos

```bash
# Dependências do bridge (uma vez)
cd siwc_bridge && npm install && cd ..

ryoku login                 # navegador + consentimento
ryoku login --reconsent     # pedir de novo uso do plano
ryoku status                # identity vs session.sharing
ryoku models
ryoku chat                  # REPL; Ctrl+C encerra
ryoku chat -p "olá"
ryoku logout
```

## Critério PASS_REAL

Autenticação no navegador, escopos concedidos, listagem de modelos, resposta real, logout e renovação de sessão testados **no notebook Omarchy**, sem exposição de tokens.

Checklist manual (não automatizar com conta real no CI):
- [ ] `ryoku login` abre o navegador e conclui
- [ ] `ryoku status` mostra `session.sharing: sim` com Plus/Pro elegível
- [ ] `ryoku models` lista slugs
- [ ] `ryoku chat -p "…"` devolve texto
- [ ] `ryoku logout` remove credenciais locais
- [ ] Sem tokens em stdout/stderr/logs/git

Não publicar logs de OAuth, tokens, cookies, dumps de sessão nem perfis locais.
