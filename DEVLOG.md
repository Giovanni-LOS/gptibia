# 📓 Diário de Bordo & Documentação de Desenvolvimento — GPTibia

> **Projeto:** GPTibia — Agente Inteligente de Suporte e Estratégia para Tibia  
> **Disciplina:** Desenvolvimento de Agentes de Inteligência Artificial (DAIA)  
> **Repositório Oficial:** [https://github.com/Giovanni-LOS/gptibia](https://github.com/Giovanni-LOS/gptibia)  
> **Desenvolvedor:** Giovanni-LOS  

---

## 📌 Sumário Executivo do Projeto
O **GPTibia** é um agente autônomo baseado em IA, orquestrado no **n8n**, que atua como oráculo e assistente tático de suporte para jogadores do MMORPG Tibia no **Telegram**. O sistema integra modelos de linguagem de última geração (OpenAI/Gemini), memória conversacional por usuário, recuperação de informações em documentos (RAG), banco estruturado da Wiki e chamadas em tempo real à API oficial do jogo.

---

# 🕒 Registro Cronológico de Desenvolvimento (Changelog / DevLog)

---

### 📅 24 de Agosto de 2026 — Setup de Hardware & Flash da ROM Stock no Linux

* **Desafio:** Celular Redmi Note 9 Pro Global (`joyeuse`) estava rodando LineageOS e necessitava retornar à ROM oficial MIUI 14 Global Stable para restabelecer estabilidade de firmware e suporte de hardware.
* **Decisão de Arquitetura:** Executar o flashing nativamente pelo Linux (Omarchy / Arch Linux) com `android-tools` e `fastboot`, evitando riscos de desconexão USB de máquinas virtuais.
* **Ações e Correções:**
  1. Localização e descompactação da ROM oficial `joyeuse_global_images_V14.0.3.0.SJZMIXM_20230307.0000.00_12.0_global.tgz`.
  2. **Bug de CRC da Xiaomi no Linux:** Durante a execução inicial do `flash_all.sh`, ocorreu o erro `Writing 'dtbo' FAILED (remote: 'Check CRC failed')`. O problema foi solucionado comentando a gravação de `crclist.txt` e `sparsecrclist.txt` no script de flash e reiniciando a sessão do Fastboot.
  3. **Preservação do Bootloader:** Utilizou-se o script `flash_all.sh` (evitando `flash_all_lock.sh`), mantendo o **bootloader 100% desbloqueado** para liberdade total de customizações futuras.
  4. Autenticação na tela de segurança (*This device is locked*) com a Conta Mi original vinculada.

---

### 📅 25 de Agosto de 2026 — Otimização do Sistema, GCam & Fundação do GPTibia

#### 1. Debloat Completo (Sem necessidade de Root)
* Execução via ADB com comandos `pm uninstall -k --user 0` para remoção limpa de bloatware sem quebrar certificações bancárias (Play Integrity).
* **Removidos:** 10 jogos patrocinados (Candy Crush, WOW, etc.), redes sociais comerciais (TikTok, Kwai, CapCut, Facebook, Amazon, AliExpress), telemetria e anúncios da Xiaomi (`joyose`, `discover/GetApps`, `guardprovider`, carrossel de tela de bloqueio *Glance*) e apps secundários do Google.
* **Mantidos:** Ferramentas essenciais do sistema, Google Drive, galeria nativa e app de controle infravermelho (Mi Remote).

#### 2. Calibração Fotográfica (GCam BSG 8.1)
* Download e instalação da Google Camera **BSG 8.1 (MGC 8.1.101 GV2b snap)** com acesso às lentes auxiliares (64MP Principal, Ultrawide e Macro).
* Inserção do perfil de cores e HDR+ calibrado: `PowerShot-BSG-RedmiNote9Pro.xml`.

#### 3. Concepção do Projeto Acadêmico "GPTibia"
* Definição do escopo do agente inteligente para a disciplina DAIA, integrando n8n, OpenAI, Telegram e dados de Tibia.
* Criação do repositório público no GitHub: `Giovanni-LOS/gptibia`.

#### 4. Entregas das 3 Atividades da Disciplina:
* 🟢 **Atividade 1 (11/08):** Elaboração do documento [`comportamento_agente.md`](https://github.com/Giovanni-LOS/gptibia/blob/main/comportamento_agente.md) contendo persona, regras de domínio estrito de Tibia e o *System Message* do agente.
* 🟢 **Atividade 2 (18/08):** Elaboração do documento [`testes_comunicacao.md`](https://github.com/Giovanni-LOS/gptibia/blob/main/testes_comunicacao.md) contendo matriz de comunicação esperada, 7 casos de teste (`CT01` a `CT07`), execução no n8n com diagnóstico de falhas do prompt inicial (v1) e validação do prompt ajustado (v2).
* 🟢 **Atividade 3 (25/08):** Criação da base documental estruturada [`base_conhecimento_gptibia.json`](https://github.com/Giovanni-LOS/gptibia/blob/main/base_conhecimento_gptibia.json) contendo 20 fontes/manuais oficiais sobre o jogo com metadados e resumos para o RAG.

---

### 📅 26 de Agosto de 2026 — Integração do Telegram Bot & Resolução de Segredos

#### 1. Criação do Bot no Telegram
* Criação do bot oficial no `@BotFather` sob o nome **GPTibia** e emissão do Token da API HTTP.

#### 2. Resolução de Alerta de Segurança do GitHub (Secret Scanning)
* Ao clonar a documentação do n8n (`n8n-docs`), um arquivo de exemplo com credencial fictícia de MongoDB disparou o Push Protection do GitHub.
* **Solução:** Reversão do commit problemático, adição de `docs/n8n-docs/` ao `.gitignore` (mantendo a documentação salva localmente no PC para consulta técnica) e push limpo no branch `main`.

#### 3. Ajuste de Compatibilidade do Modelo OpenAI no n8n
* Ao conectar o nó `AI Agent` ao nó `OpenAI Chat Model` com o modelo `chat-latest`, o n8n retornou: `Unsupported value: 'temperature' does not support 0.3 with this model. Only the default (1) value is supported.`
* **Solução:** Remoção do parâmetro customizado de temperatura no nó da OpenAI, permitindo a operação com a temperatura padrão (`1.0`).
* **Validação:** Ativação do fluxo [`gptibia_telegram_workflow.json`](https://github.com/Giovanni-LOS/gptibia/blob/main/gptibia_telegram_workflow.json) no n8n. O bot passou a responder com sucesso em tempo real no Telegram.

---

### 📅 01 de Setembro de 2026 — Validação em Produção da TibiaData API & Resolução de Sandbox

#### 1. Diagnóstico do Erro de Sandbox no n8n
* **Sintoma:** Ao testar no Telegram com a mensagem *"Conhece o personagem Disco Draco?"*, o bot respondeu: `a ferramenta de personagens está retornando um erro técnico ("fetch is not defined")`.
* **Causa Raiz:** O n8n executa nós de código em uma sandbox isolada (VM2) que não expõe o `fetch` global nativo do Node.js/navegador. Além disso, a API retornou `"guild": {}` para o personagem (objeto vazio, que em JS é truthy), causando quebra ao ler `.name`.
* **Solução Técnica Definitiva:**
  1. Migração das chamadas de rede no `Custom Code Tool` para o helper oficial do n8n: `this.helpers.httpRequest({ method: 'GET', url: '...', json: true })`.
  2. Tratamento defensivo de inputs (remoção automática de aspas enviadas pela LLM).
  3. Tratamento de guildas vazias e extração correta de mortes e status.

#### 2. Validação Real em Produção (Telegram)
* A consulta ao vivo para o personagem **Disco Draco** no Telegram retornou com sucesso:
  * **Level:** 170
  * **Vocação:** Elite Knight
  * **Mundo:** Ourobra (Status: Offline)
  * **Residência:** Ankrahmun
  * **Guilda:** Nenhuma
  * **Mortes:** Morto no level 171 por *pirate marauder*
* O agente demonstrou autonomia completa de *Tool Calling*, decidindo quando buscar dados ao vivo e formatando a resposta de forma clara e tática.

#### 3. Substituição da Base Hipotética por Dados Reais da TibiaWiki
* **Auditoria da base anterior:** Os 20 registros de `base_conhecimento_gptibia.json` eram apenas um catálogo; vários PDFs apontados não existiam. O arquivo deixou de ser considerado uma fonte válida para ingestão no RAG e foi preservado somente como histórico da atividade.
* **Decisão de arquitetura:** Separação das fontes por tipo de consulta:
  1. TibiaData para personagens e mundos em tempo real.
  2. TibiaWiki-SQL para fatos estruturados, filtros, atributos, loot e relações.
  3. RAG futuro somente para páginas reais de quests, lore e mecânicas narrativas.
* **Automação criada:** `scripts/update_tibiawiki_db.sh` gera um snapshot sem imagens e sem artigos obsoletos, registra erros de parsing, valida o arquivo e só então substitui a versão anterior.
* **Validação criada:** `scripts/validate_tibiawiki_db.py` abre o SQLite em modo somente leitura, executa `PRAGMA quick_check` e exige as tabelas essenciais não vazias.

#### 4. Primeiro Snapshot Real do TibiaWiki-SQL
* **Versão do gerador:** `tibiawikisql 9.0.0`.
* **Resultado validado:** banco `data/tibiawiki.db` com aproximadamente 14 MB e integridade SQLite aprovada.
* **Cobertura principal:** 2.096 criaturas, 19.302 relações de loot, 9.539 itens, 1.211 NPCs, 366 quests, 195 spells e 72 imbuements.
* **Limitações registradas:** 59 artigos tiveram erros de parsing; também houve ofertas de NPCs e nomes de itens não mapeados. O arquivo `data/parsing-errors.log` mantém o diagnóstico local.
* **Limite funcional das quests:** A tabela `quest` contém metadados, requisitos, perigos e recompensas, mas não contém walkthrough completo. Guias passo a passo continuarão dependendo do RAG com fontes reais.

#### 5. Preparação do MCP SQLite
* **Servidor selecionado:** `db-mcp 5.0.1`, fixado em `mcp/package.json` e também disponível pela imagem versionada `writenotenow/db-mcp:v5.0.1`.
* **Runtime local:** Node atualizado para `26.8.1`; 145 pacotes instalados com auditoria npm indicando zero vulnerabilidades conhecidas.
* **Configuração:** O launcher local usa o backend WASM, solicita o filtro `read_query,list_tables` e mantém o snapshot original inalterado. O Compose alternativo monta o banco como somente leitura, remove capabilities do contêiner e impede ganho de privilégios.
* **Endpoints preparados:** Streamable HTTP em `/mcp`, compatibilidade SSE em `/sse` e health check em `/health`, todos limitados à interface local na porta 3000.
* **Validação do protocolo:** Health check aprovado, handshake MCP `2025-03-26` concluído e consulta parametrizada do Demon retornando uma única entidade correta. Uma tentativa de `DELETE` pela tool de leitura foi rejeitada com `VALIDATION_ERROR`.
* **Proteção no n8n:** Como o servidor também publica tools internas, o workflow seleciona explicitamente apenas `sqlite_read_query` e `sqlite_list_tables`; `sqlite_execute_code` não é entregue ao AI Agent.
* **Workflow atualizado:** `gptibia_telegram_workflow.json` recebeu o `MCP Client Tool` 1.4 em Streamable HTTP e regras de system prompt para consultar por `title`, limitar resultados e não inventar walkthroughs ausentes.

#### 6. Verificação Final desta Etapa
* **Scripts e artefatos:** Sintaxe Bash aprovada, arquivos JSON válidos, configuração do Docker Compose válida e `git diff --check` sem erros de whitespace.
* **Snapshot preservado:** `data/tibiawiki.db` permaneceu com 13.914.112 bytes, permissão `0644` e SHA-256 `6641ceab080a28d6f8b4fc6d7f7fefca743daa9cf56c1f9e74f20f3afd66c0f8` após os testes.
* **Servidor em execução:** O health check local respondeu como saudável em `http://127.0.0.1:3000/health`.
* **Documentação alinhada:** O exemplo de consulta do Demon no `README.md` foi atualizado de 110% para os 112% de Ice e Holy retornados pelo snapshot atual.
* **Limite do teste:** A estrutura do workflow e sua conexão `ai_tool` foram validadas no arquivo JSON. O teste ponta a ponta ainda depende de importar o fluxo na instância do n8n e enviar consultas reais pelo Telegram.

#### 7. Compatibilidade com o n8n 1.98.1 e Fallback HTTP
* **Auditoria da versão exata:** A tag oficial `n8n@1.98.1` foi inspecionada. O `MCP Client Tool` versão 1 usa exclusivamente `SSEClientTransport`; Streamable HTTP ainda não está disponível nessa versão.
* **Diagnóstico corrigido:** O choque de transportes existe, mas não explica sozinho o `unexpected EOF`. O workflow também usava tipo e parâmetros incorretos, `127.0.0.1` não alcança esta máquina a partir do n8n remoto e o canal SSE foi bloqueado pelo Quick Tunnel durante os testes.
* **Limite encontrado no pacote:** O `db-mcp 5.0.1` anuncia `--transport sse`, porém encerrou com `Unsupported transport: sse`. A configuração simples por `MCP_AUTH_TOKEN` também não satisfez a validação do transporte HTTP dessa versão.
* **Solução principal implementada:** `scripts/tibiawiki_http_api.py` expõe `POST /v1/query` por HTTP stateless, exige Bearer token, aceita apenas um `SELECT`, usa SQLite read-only com authorizer, limita 20 linhas e aplica timeout de execução.
* **Operação segura:** `scripts/start_tibiawiki_http_api.sh` cria o token com permissão `0600`; `scripts/start_tibiawiki_http_tunnel.sh` publica a porta local; `scripts/configure_n8n_http_workflow.py` injeta URL e token somente em `gptibia_telegram_workflow.local.json`, ignorado pelo Git.
* **Workflow principal:** O MCP foi substituído pelo Code Tool `tibiawiki_sql_query`, que usa `this.helpers.httpRequest`, compatível com o padrão já validado nas tools TibiaData.
* **Validação HTTP:** Health check aprovado; consulta do Demon aprovada localmente e por HTTPS; requisição sem token retornou `401`; `DELETE` retornou `400`; quatro testes unitários passaram.
* **Validação do Code Tool:** O JavaScript extraído de `gptibia_telegram_workflow.local.json` foi executado com um mock de `this.helpers.httpRequest` e consultou o Demon pela URL pública com sucesso.
* **Verificação de segredos:** Tokens e workflow configurado ficaram com permissão `0600`; nenhum token foi encontrado nos arquivos versionáveis. A auditoria npm permaneceu com zero vulnerabilidades conhecidas.
* **Alternativa MCP preservada:** `mcp/tibiawiki_sse_server.mjs` usa o SDK MCP, `node:sqlite` read-only, Bearer token e heartbeat. O arquivo `gptibia_telegram_workflow_mcp_sse.json` usa o tipo oficial `mcpClientTool` e os parâmetros corretos `include`/`includeTools`.
* **Resultado do SSE:** Handshake, listagem das duas tools, consulta e bloqueio de escrita passaram localmente. No Cloudflare Quick Tunnel, `/health` e `401` funcionaram, mas o stream autenticado não entregou bytes mesmo com heartbeat e flush; essa opção permanece apenas para redes ou proxies que suportem SSE persistente.

#### 8. Correção de Consultas Incompletas de Itens
* **Falha observada:** Para “Qual o ataque, defesa e peso da Magic Sword?”, o agente retornou apenas 42 oz e afirmou que ataque e defesa não estavam disponíveis.
* **Causa raiz:** Não era falha da API HTTP. O esquema do TibiaWiki-SQL guarda `weight` em `item`, mas mantém `attack`, `defense` e `defense_modifier` em linhas da tabela `item_attribute`. O agente consultou apenas a primeira tabela e encerrou a busca cedo.
* **Inconsistência adicional:** O system prompt do workflow HTTP ainda citava os nomes antigos `sqlite_read_query` e `sqlite_list_tables`, apesar de a tool ativa se chamar `tibiawiki_sql_query`.
* **Camada semântica:** `scripts/create_tibiawiki_views.py` passou a criar `item_details`, uma view que combina os campos básicos do item com ataque, defesa, armor, requisitos, imbuement slots e resistências. O atualizador recria a view antes de validar e publicar cada snapshot.
* **Prompt refinado:** Para itens, o agente deve consultar `item_details` primeiro, usar `item_attribute` como fallback e somente depois declarar ausência. Pedidos com vários atributos devem ser respondidos de forma conjunta e direta.
* **Regressão adicionada:** O caso `CT08` exige a resposta “ataque 48, defesa 35 (+3) e peso 42 oz” para Magic Sword.
* **Validação:** A view contém 9.539 itens; cinco testes automatizados passaram; a consulta local e a consulta HTTPS retornaram os cinco campos esperados para Magic Sword.

---

## 🛠️ Arquitetura Atual do Sistema

```
[ Usuário no Telegram ]
          │
          ▼
[ Telegram Trigger Node ]
          │
          ▼
[ AI Agent Node (GPTibia) ] ◄───► [ Chat Memory (Per User Chat ID) ]
     │                │
     ▼                ▼
[ OpenAI Model ]   [ Tools (Ferramentas Ativas) ]
 (chat-latest)        ├── 1. TibiaData Character Lookup (Live Status, Deaths, Guild)
                      ├── 2. TibiaData World Status (Players Online, PvP, Location)
                      ├── 3. Vector Store RAG (Fontes Reais de Quests/Bosses) [A Implementar]
                      └── 4. TibiaWiki-SQL via HTTP Tool (API e túnel validados)
          │
          ▼
[ Telegram Send Message Node ]
          │
          ▼
[ Resposta Entregue no Celular do Jogador ]
```

---

## 📋 Próximas Metas no Roadmap
1. [x] Canal de entrada e saída no Telegram com memória contextual por usuário.
2. [x] Conectar nó de Tool para a `TibiaData API v4` (Live Character & World Data) com `this.helpers.httpRequest`.
3. [ ] Reconstruir o RAG somente com documentos ou páginas reais e verificáveis.
4. [x] Gerar e validar o banco estruturado da Wiki (`tibiawiki-sql`).
5. [x] Expor o SQLite por API HTTP autenticada e manter MCP SSE como alternativa.
6. [ ] Importar `gptibia_telegram_workflow.local.json` no n8n e validar pelo Telegram.
7. [ ] Configurar execução autônoma 24/7 do n8n dentro do Termux no Redmi Note 9 Pro.
