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
- [ ] Conferir a documentação SIWC/DevKit atual e a licença de redistribuição
- [ ] Escolher empacotamento sustentável para SDK e backend seguro no Linux
- [ ] Implementar `ryoku login`, `ryoku logout`, status da conta e seleção de perfil
- [ ] Persistir host ID estável sem hardware ID; armazenamento em keyring/KWallet (sem fallback inseguro)
- [ ] Verificar identity, `session.sharing`, modelos disponíveis, expirados/renovação/consentimento
- [ ] Testes unitários com mocks; login real só pelo consentimento do usuário

## Sprint 2 — conversa no terminal
- [ ] Implementar `ryoku chat`, streaming, saída limpa com Ctrl+C
- [ ] Histórico local **opcional**, sem expor prompt/senha em logs
- [ ] Gerenciar limites de uso e erros sem criar cobrança inesperada
- [ ] Sem chamar ferramentas do sistema sem permissão

## Sprint 3 — integração com Omarchy
- [ ] Plugin Quickshell opcional sem iniciar outro Quickshell
- [ ] Botão 緑, popup com conversas, comando `ryoku chat` e atalho configurável
- [ ] Diagnóstico de serviços somente leitura com allowlist; aprovação antes de futuras modificações
- [ ] Rollback/backup, multimonitor e bateria
- [ ] Revisão pré-publicação e PASS_REAL no notebook

Critérios: nunca afirmar "login funcional" antes do teste real; nunca armazenar tokens no Git; Cursor e Codex são separados do chat; não modificar repositórios NixOS privados.
