# Sign in with ChatGPT — arquitetura e segurança

**Status na V0.1: não implementado.** O CLI não faz autenticação nem solicita IA.

Referências oficiais:
- https://developers.openai.com/siwc/quickstart
- https://developers.openai.com/siwc/token-sharing-open-source
- https://developers.openai.com/cookbook/articles/sign-in-with-chatgpt
- https://github.com/openai/sign-in-with-chatgpt-devkit
- https://help.openai.com/en/articles/6950777-what-is-chatgpt-plus

## Regras de implementação

1. **Não confundir Plus com API paga.** A API tradicional é faturada à parte. O SIWC para OSS local depende de consentimento, escopos, elegibilidade e limites próprios.
2. O login precisa usar SDK/código oficial auditado: **navegador do sistema, loopback 127.0.0.1, PKCE, state, nonce, ID token verificado e escopos autorizados**. Não criar login improvisado nem reutilizar credenciais de Codex/Cursor/ChatGPT.
3. Gerar um `ext_agent_host_id` opaco, aleatório, persistente por instalação. Nunca usar hostname, e-mail ou serial do notebook como identificador.
4. Credenciais protegidas por **Secret Service/GNOME Keyring ou KWallet** e permissões de arquivos rigorosas. Falhar fechado se o armazenamento protegido não existir. Não permitir fallback texto puro nem backend Linux `basic_text`.
5. Verificar `session.sharing` antes das solicitações de IA: login de identidade **não** significa permissão para usar o plano.
6. Modelos descobertos após login pelo SDK; não presumir acesso a modelos específicos. Expor erros de limite, consentimento e nova autenticação sem vazar credenciais.
7. Conversas não possuem memória e histórico do ChatGPT por padrão. O histórico local é **opt-in**; não salvá-lo automaticamente no código de diagnóstico.
8. Leitura de dados do sistema só por funções específicas aprovadas, com redaction; nada de shell irrestrito nem `sudo`.
9. No plugin Omarchy, reutilizar o processo Quickshell oficial, não criar uma segunda shell ou processar segredos em QML.

## Dependências e licença

O exemplo atual da OpenAI utiliza `@siwc/local` do repositório [Sign in with ChatGPT DevKit](https://github.com/openai/sign-in-with-chatgpt-devkit). Na versão inspecionada, esse pacote é um **workspace privado**; portanto NÃO recomendar `npm install @siwc/local` direto do registro público sem verificar a disponibilidade. O Cursor deve avaliar a licença, pinagem do código, distribuição e adaptação segura do armazenamento de credenciais do Linux.

**Critério PASS_REAL:** autenticação no navegador, escopos concedidos, listagem de modelos, resposta real, logout e renovação de sessão testados no notebook, sem exposição de tokens.

Não publicar logs de OAuth, tokens, cookies, dumps de sessão nem perfis locais.
