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
                      ├── 3. Vector Store RAG (20 Documentos de Quests/Bosses) [A Implementar]
                      └── 4. TibiaWiki-SQL (Itens e Bestiário) [A Implementar]
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
3. [ ] Integrar base de conhecimento vetorial (RAG) com os 20 documentos do `base_conhecimento_gptibia.json`.
4. [ ] Integrar banco de dados estruturado da Wiki (`tibiawiki-sql`).
5. [ ] Configurar execução autônoma 24/7 do n8n dentro do Termux no Redmi Note 9 Pro.

