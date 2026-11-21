# Anexos no Ryoku AI — proposta técnica para próximas sprints

**Status:** design/roadmap, NÃO implementado. O envio atual em `Panel.qml` e `siwc_bridge/src/bridge.mjs` aceita **somente texto**. Não mostrar como recurso pronto na UI nem afirmar ter analisado uma imagem sem tê-la enviado ao modelo.

## Experiência desejada

- Botão `+` ao lado da caixa de mensagem: escolher imagem, print ou documento local.
- Colar print via Ctrl+V e mostrar pré-visualização com nome/tipo/tamanho e opção de remover antes de enviar.
- Perguntas de exemplo: "Analise esse erro do Omarchy e me diga como corrigir", "Resuma o PDF", "Explique este log".
- O histórico local registra os anexos associados à conversa e deixa claro quando o conteúdo foi truncado ou não pôde ser lido.
- Não executar comandos ou alterações no sistema automaticamente a partir de texto em documentos/prints.

## Etapa A: arquivos de texto/documentos

1. Criar seleção de arquivos via diálogo Qt/portal no Quickshell; nenhum caminho de usuário é enviado para shell interpeter/argv. CLI local recebe um protocolo com dados por stdin.
2. Validar MIME real, tamanho máximo configurável, contagem de arquivos, acesso permitido pelo usuário, symlinks e erros de permissão. Nunca varrer diretórios inteiros.
3. Extrair localmente TXT/MD/LOG/JSON/CSV/código com limites, UTF-8 e avisos de truncamento. PDF com biblioteca de extração instalada e tratamento de páginas sem texto; não fingir extração de páginas escaneadas.
4. Construir contexto com texto extraído e rótulos de origem/página. Tratar conteúdo de anexos como dados não confiáveis e não como instruções do app. Persistência local controlada por usuário.
5. Testes de arquivo vazio, malicioso, enorme, unicode, múltiplos arquivos, exclusão e troca de perfil.

## Etapa B: screenshots/imagens e visão de verdade

1. Arquivos PNG/JPEG/WebP e screenshot obtido via seleção ou ferramenta existente, com confirmação explícita de envio.
2. Verificar em versão efetivamente instalada do `@siwc/local` se `streamResponse` aceita conteúdo estruturado no formato multimodal da Responses API e se o modelo/consentimento do usuário permitem visão. O bridge atual valida apenas strings; precisa de protocolo seguro e testes antes de liberar.
3. Quando houver suporte, codificar imagem em formato aceito e enviar conteúdo binário real ao modelo (não apenas caminho, nome ou texto inventado). Streaming, limites, tamanho e erros devem ser explícitos.
4. Se a modalidade não for suportada, mostrar "análise de imagens indisponível neste modelo/conta" em vez de simular visão ou trocar de provedor sem autorização.
5. Teste PASS_REAL com print contendo um erro visual que **não apareça no prompt textual** e checar se o diagnóstico menciona detalhes da imagem.

## Privacidade e compatibilidade

- Tokens apenas no bridge seguro; não armazenar em QML, stdout, logs ou GitHub.
- Anexos persistem localmente apenas conforme política definida e com exclusão vinculada à conversa; nenhum upload escondido.
- NÃO usar a Files Upload API só por existir no ChatGPT web: o login SIWC do projeto é integração diferente e os recursos disponíveis devem ser verificados.
- Avaliar separadamente licenças de extratores e do DevKit para distribuição open source.
- Preservar bandeja, Google Agenda, Resonance, histórico SQLite e rollback do plugin.

## Critérios para marcar implementado

- [ ] Texto/documento: extração real e resumo com referência do conteúdo do arquivo
- [ ] Imagem: conteúdo real enviado ao modelo com capacidade de visão comprovada
- [ ] Ctrl+V, seletor, prévia, remover anexo, erro claro por formato/limite
- [ ] Histórico e isolamento por perfil; logout/rollback sem perda involuntária
- [ ] CI verde; PASS_REAL no notebook (multi-monitor/escala) sem regressões
