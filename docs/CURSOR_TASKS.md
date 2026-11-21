# Backlog Cursor — Ryoku AI para Omarchy

## Objetivo

Construir uma interface de **conversa geral**, leve e local, aproveitando o ChatGPT autorizado, sem usar o Codex como interface de chat. O Cursor será responsável por produzir e testar o código.

## Sprint 0 — base do repositório
- [x] CLI Python sem dependências em runtime
- [x] Diagnóstico local que não lê arquivos pessoais nem executa comandos externos
- [x] Testes unitários e GitHub Actions
- [x] Documentação de SIWC e política de privacidade
- [ ] Testar CLI no notebook Omarchy (PASS_REAL)

## Sprint 1 — autenticação oficial
- [x] Conferir a documentação SIWC/DevKit atual e a licença de redistribuição
- [x] Escolher empacotamento sustentável para SDK e backend seguro no Linux (`vendor/siwc-local` + `siwc_bridge` + keytar)
- [x] Implementar `ryoku login`, `ryoku logout`, status da conta e seleção de perfil
- [x] Persistir host ID estável sem hardware ID; armazenamento em keyring/KWallet (sem fallback inseguro)
- [x] Verificar identity, `session.sharing`, modelos disponíveis, expirados/renovação/consentimento
- [x] Testes unitários com mocks; login real só pelo consentimento do usuário
- [ ] PASS_REAL do login no notebook (bloqueia merge da issue #2 / PR #4)

## Sprint 2 — conversa no terminal + histórico
- [x] Implementar `ryoku chat`, streaming, saída limpa com Ctrl+C
- [x] Histórico local persistente (SQLite), compartilhado com o painel; sem exclusão automática
- [x] Contexto real reenviado (`input` array); orçamento e aviso de truncamento
- [x] `ryoku history list/show/rename/delete/clear` com confirmação
- [x] Gerenciar limites de uso e erros sem criar cobrança inesperada (erros do SDK; sem API key)
- [x] Sem chamar ferramentas do sistema sem permissão
- [ ] PASS_REAL histórico + painel no notebook (issue #5)

## Sprint 3 — integração com Omarchy
- [x] Plugin Quickshell opcional sem iniciar outro Quickshell (`plugins/io.github.paulon34.ryoku-ai`)
- [x] Botão 緑, painel com conversas, streaming, nova/apagar com confirmação
- [x] Installer/rollback reversíveis (não toca bandeja/Agenda/Resonance)
- [ ] Diagnóstico de serviços somente leitura com allowlist; aprovação antes de futuras modificações
- [ ] Revisão pré-publicação e PASS_REAL no notebook

Critérios: nunca afirmar "login funcional" antes do teste real; nunca armazenar tokens no Git; Cursor e Codex são separados do chat; não modificar repositórios NixOS privados.
