const API_URL = '__TIBIAWIKI_API_URL__';
const API_TOKEN = '__TIBIAWIKI_API_TOKEN__';

if (API_URL.includes('__TIBIAWIKI_') || API_TOKEN.includes('__TIBIAWIKI_')) {
  return 'A TibiaWiki HTTP Tool ainda nao foi configurada. Gere o workflow local com scripts/configure_n8n_http_workflow.py.';
}

let sql = '';
if (typeof query === 'string') {
  sql = query.trim();
} else if (typeof query === 'object' && query !== null) {
  sql = String(query.query || query.sql || query.input || '').trim();
}

if (!sql) {
  return 'Consulta SQL vazia. Envie um unico SELECT com LIMIT de no maximo 20 linhas.';
}

try {
  const result = await this.helpers.httpRequest({
    method: 'POST',
    url: API_URL,
    headers: {
      Authorization: `Bearer ${API_TOKEN}`,
      'Content-Type': 'application/json'
    },
    body: { query: sql },
    json: true,
    timeout: 15000
  });

  return JSON.stringify(result);
} catch (error) {
  return `Erro ao consultar a TibiaWiki: ${error.message}`;
}
