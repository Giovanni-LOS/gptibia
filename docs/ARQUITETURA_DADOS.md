# Arquitetura de Dados do GPTibia

## Responsabilidade de cada fonte

| Fonte | Uso | Atualização | Estado |
| --- | --- | --- | --- |
| TibiaData v4 | Personagens, mortes, status de mundos e guildas | Consulta em tempo real | Integrado |
| TibiaWiki-SQL | Itens, criaturas, loot, NPCs, spells, imbuements e metadados de quests | Snapshot periódico | Gerado e validado |
| Tibia Knowledge RAG | Busca semântica em quests, criaturas, spells e imbuements | Snapshot + OpenAI Embeddings | Integrado no workflow |

TibiaData e TibiaWiki são serviços comunitários. Dados oficiais devem ser atribuídos à CipSoft apenas quando a fonte for `tibia.com`.

## Atualização do SQLite

Requisito local:

```bash
pipx install tibiawikisql==9.0.0
```

Gerar ou atualizar o snapshot:

```bash
./scripts/update_tibiawiki_db.sh
```

O processo usa arquivos temporários. `data/tibiawiki.db` e `data/rag_knowledge.json` só são publicados depois que o gerador termina, o `PRAGMA quick_check` retorna `ok`, todas as tabelas essenciais possuem dados e o corpus RAG é exportado.

Antes da validação, `scripts/create_tibiawiki_views.py` recria a view `item_details`. Ela não duplica dados e oferece uma interface estável para o agente, mesmo que os atributos continuem normalizados em `item_attribute`.

O banco e o log de parsing são artefatos locais e não são versionados. Atualize antes de uma demonstração importante ou quando a Wiki receber mudanças relevantes.

## Limites conhecidos

* A geração não garante cobertura perfeita. Consulte `data/parsing-errors.log` após cada atualização.
* A tabela `quest` não possui o walkthrough completo da página.
* Consulte criaturas pelo campo único `title`, e não apenas por `name`. Por exemplo, `name = 'Demon'` também corresponde a `Demon (Goblin)`.
* O esquema original separa os dados de itens: peso, classe e preço ficam em `item`; ataque, defesa, armor e requisitos ficam em `item_attribute`. Use a view `item_details` para consultas comuns.
* Chances de loot vêm de estatísticas comunitárias e não devem ser apresentadas como garantia de drop.
* O modelo deve citar que não encontrou dados quando uma consulta retornar vazia; não deve completar a resposta com memória própria.

## Integração recomendada para o n8n 1.98.1

O workflow principal utiliza uma API HTTP stateless chamada por um `Code Tool`. Essa abordagem evita manter uma conexão SSE através do túnel e conserva a mesma integração por `this.helpers.httpRequest` já usada com TibiaData.

Inicie a API local:

```bash
./scripts/start_tibiawiki_http_api.sh
```

O launcher cria dois arquivos locais ignorados pelo Git:

* `.runtime/tibiawiki_api_token`, com permissão `0600`.
* `gptibia_telegram_workflow.local.json`, depois da etapa de configuração.

A API oferece:

* `GET http://127.0.0.1:8080/health`, sem autenticação.
* `POST http://127.0.0.1:8080/v1/quest`, com Bearer token obrigatório (Domain Tool de quests com resolução fuzzy, `quest_danger` e `quest_reward`).
* `POST http://127.0.0.1:8080/v1/creature`, com Bearer token obrigatório (Domain Tool de criaturas com fraquezas elementais, `creature_drop` e quests associadas).
* `POST http://127.0.0.1:8080/v1/item`, com Bearer token obrigatório (Domain Tool de itens com `item_details`, `required_level` e preços em `npc_offer_buy`/`sell`).
* `POST http://127.0.0.1:8080/v1/query`, com Bearer token obrigatório (fallback de leitura SQL livre).
* `GET http://127.0.0.1:8080/v1/knowledge`, com Bearer token obrigatório (corpus RAG de 2.590 documentos).

As chamadas são auditadas em `.runtime/api_access.log` em formato JSON estruturado (`request_id`, `endpoint`, `duration_ms`, `arguments` sanitizados, `entity_resolved`, `match_type`), sem registrar tokens.

O endpoint de consulta livre aceita somente um `SELECT`, abre o banco em `mode=ro`, ativa `query_only`, usa o authorizer do SQLite, limita a resposta a 20 linhas e interrompe consultas que excedam o tempo configurado.

Como o n8n da faculdade está em outra máquina, `127.0.0.1` no workflow apontaria para o servidor da faculdade. Para um teste, publique a API:

```bash
./scripts/start_tibiawiki_http_tunnel.sh
```

Use a URL HTTPS exibida para gerar o workflow importável:

```bash
./scripts/configure_n8n_http_workflow.py \
  --api-url https://SEU-TUNEL.trycloudflare.com
```

Importe `gptibia_telegram_workflow.local.json`. O template versionado mantém placeholders e não contém o token. Quick Tunnels são efêmeros e não possuem garantia de disponibilidade; para uso contínuo, configure um túnel nomeado ou hospede a API em um serviço HTTPS controlado.

## Tibia Knowledge e OpenAI Embeddings

`scripts/export_rag_knowledge.py` converte os registros reais do snapshot em documentos textuais com `id`, `text` e metadados de proveniência. O corpus atual contém:

| Entidade | Documentos | Uso principal |
| --- | ---: | --- |
| Criaturas | 1.957 | Busca por perfil, local, elementos e habilidades |
| Quests | 366 | Contexto, requisitos, perigos e recompensas |
| Spells | 195 | Descoberta por efeito, vocação e palavras mágicas |
| Imbuements | 72 | Descoberta por efeito, slot e materiais |

O workflow implementa os dois caminhos usados na Aula 3:

1. **Ingestão:** `Atualizar Tibia Knowledge` baixa o corpus, cria chunks de 1.200 caracteres com sobreposição de 180, gera OpenAI Embeddings e insere no Vector Store.
2. **Recuperação:** `Tibia Knowledge - RAG` usa a mesma chave de memória e outro nó OpenAI Embeddings, sendo entregue ao AI Agent como tool semântica com `topK = 6`.

Depois de importar o workflow, execute manualmente **Atualizar Tibia Knowledge** antes de testar o bot. Os dois nós de embeddings devem usar a mesma credencial OpenAI.

O `Simple Vector Store` é adequado para a demonstração acadêmica, mas mantém os vetores na memória do processo. Os dados precisam ser ingeridos novamente após reiniciar o n8n e não devem conter informação sensível. Para operação persistente, a evolução recomendada é trocar apenas a implementação do store por PGVector, Qdrant ou outro backend compatível, preservando o exportador e a separação híbrida.

O corpus não cria informação que o SQLite não possui. Em especial, os documentos de quests contêm contexto, requisitos, perigos e recompensas, mas não um walkthrough completo. A ingestão de páginas narrativas reais continua sendo uma extensão futura.

## Compatibilidade MCP SSE

O código-fonte oficial da tag `n8n@1.98.1` confirma que o `MCP Client Tool` versão 1 instancia apenas `SSEClientTransport`. Essa versão não suporta Streamable HTTP.

O diagnóstico não termina aí:

* O `db-mcp 5.0.1` aceita `/mcp` e anuncia uma opção `sse`, mas `--transport sse` falhou nos testes com `Unsupported transport: sse`.
* O workflow anterior usava o tipo inexistente `@n8n/n8n-nodes-langchain.toolmcp`; o tipo correto é `@n8n/n8n-nodes-langchain.mcpClientTool`.
* Os parâmetros corretos da versão 1 são `include` e `includeTools`, não `toolsToInclude` e `includedTools`.
* Um endpoint em `127.0.0.1` nunca seria alcançado pelo n8n remoto.

Para preservar uma alternativa, foi criado um servidor legado com o SDK MCP, `node:sqlite` somente leitura, Bearer token e heartbeat a cada 15 segundos:

Requisitos e instalação local:

```bash
node --version  # v26 ou superior
npm install --prefix mcp
```

Iniciar em primeiro plano:

```bash
./scripts/start_tibiawiki_mcp.sh
```

Para parar, pressione `Ctrl+C` no terminal do servidor.

Endpoints locais:

* SSE legado autenticado: `http://127.0.0.1:3000/sse`
* Health check: `http://127.0.0.1:3000/health`

O arquivo `gptibia_telegram_workflow_mcp_sse.json` contém o nó correto para o n8n `1.98.1`. Antes de importar, substitua a URL de exemplo e crie no n8n uma credencial **HTTP Bearer Auth** usando `.runtime/tibiawiki_mcp_token`.

Essa variante concluiu handshake, listagem de tools e consulta local. Pelo Cloudflare Quick Tunnel usado nos testes, entretanto, `/health` e respostas curtas atravessaram, mas o stream SSE não entregou bytes. Por isso ela não é o caminho recomendado para o n8n remoto da faculdade.

## Validação executada

* A API HTTP retornou uma única linha para `title = 'Demon'`, com 8.200 HP, 6.000 XP, 112% Ice, 0% Fire e 112% Holy.
* A API respondeu `401` sem token e `400` para uma tentativa de `DELETE`.
* A mesma consulta HTTP passou por uma URL `trycloudflare.com` autenticada.
* O MCP SSE local publicou somente `sqlite_read_query` e `sqlite_list_tables`, recusou acesso sem Bearer token e rejeitou `DELETE`.
* O workflow principal contém o Code Tool conectado ao AI Agent. Ainda falta importar a cópia local na instância do n8n e validar a chamada pelo Telegram.

## Regras para o agente

1. Usar TibiaData para informações que mudam em tempo real.
2. Usar a tool HTTP SQLite para números, filtros e relações estruturadas.
3. Usar o Tibia Knowledge para busca semântica, contexto e explicações; nunca como substituto de filtros ou cálculos SQL.
4. Combinar SQL e RAG quando a pergunta misturar fatos exatos com estratégia ou contexto.
5. Nunca tratar o resultado de uma tool como infalível; respostas vazias e erros de parsing devem ser informados.
6. Não executar comandos de escrita, DDL ou múltiplas instruções SQL.
