#!/usr/bin/env bash
# Constrói localmente o repositório fictício "loja-incidentes" (conteúdo + histórico git).
# Uso: criar_repo.sh <diretorio-destino>   (não existe ou está vazio)
# Não cria repo no GitHub, não faz push. Determinístico (datas fixas).
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "uso: $0 <diretorio-destino>" >&2
  exit 1
fi
DEST="$1"
if [ -e "$DEST" ] && { [ ! -d "$DEST" ] || [ -n "$(ls -A "$DEST")" ]; }; then
  echo "erro: '$DEST' já existe e não está vazio" >&2
  exit 1
fi
mkdir -p "$DEST"
cd "$DEST"

git init -q -b main
git config user.name "Equipe Loja"
git config user.email "loja@example.com"
git config commit.gpgsign false
git config tag.gpgsign false

# commitar "<data ISO>" "<mensagem>" [autor "Nome <email>"]
commitar() {
  local data="$1" msg="$2"
  export GIT_AUTHOR_DATE="$data" GIT_COMMITTER_DATE="$data"
  if [ -n "${3:-}" ]; then
    git commit -q --author="$3" -m "$msg"
  else
    git commit -q -m "$msg"
  fi
}

# marcar "<data ISO>" "<tag>" "<mensagem>"
marcar() {
  GIT_COMMITTER_DATE="$1" git tag -a "$2" -m "$3"
}

mkdir -p pedidos-api/templates pagamentos-api/src estoque-worker auth-api

# ---------------------------------------------------------------- baseline
cat > pedidos-api/config.yaml <<'EOF'
servico: pedidos-api
db:
  host: db-principal
  pool_max: 20          # conexões máximas com o banco
  statement_timeout_ms: 5000
http:
  timeout_ms: 3000
dependencias:
  pagamentos_api: http://pagamentos-api:8080
  estoque_fila: estoque-reservas
EOF
cat > pedidos-api/templates/email_confirmacao.txt <<'EOF'
Assunto: Pedido recebido

Olá {{nome}}, recebemos seu pedido {{pedido_id}}.
Em breve vc recebera a confirmacao do pagamento.
EOF
cat > pedidos-api/app.py <<'EOF'
"""pedidos-api: cria pedidos, cobra no pagamentos-api e reserva estoque pela fila."""


def calcular_frete(pedido):
    cep = pedido.get("endereco", {}).get("cep", "")
    return 15.0 if cep.startswith("0") else 25.0


def criar_pedido(pedido):
    pedido["frete"] = calcular_frete(pedido)
    return pedido
EOF

cat > pagamentos-api/config.yaml <<'EOF'
servico: pagamentos-api
gateway:
  nome: PagaFacil
  url: https://api.pagafacil.com.br/v2/cobrancas
  timeout_ms: 4000
  retries: 3
  rate_limit_por_minuto: 100   # limite contratado com o PagaFácil
EOF
cat > pagamentos-api/src/PagamentoService.java <<'EOF'
package br.loja.pagamentos;

public class PagamentoService {

    public Pagamento confirmar(Pedido pedido, Cupom cupom) {
        double valor = pedido.getTotal();
        return gateway.cobrar(pedido.getId(), valor);
    }
}
EOF

cat > estoque-worker/config.yaml <<'EOF'
servico: estoque-worker
db:
  host: db-principal
  pool_max: 10
fila:
  queue_url: https://sqs.sa-east-1.example.com/estoque-reservas
  poll_interval_ms: 500
EOF
cat > estoque-worker/config.py <<'EOF'
import os

QUEUE_URL = os.environ.get("ESTOQUE_QUEUE_URL", "https://sqs.sa-east-1.example.com/estoque-reservas")
EOF
cat > estoque-worker/.env.example <<'EOF'
ESTOQUE_QUEUE_URL=https://sqs.sa-east-1.example.com/estoque-reservas
LOG_LEVEL=INFO
EOF

cat > auth-api/config.yaml <<'EOF'
servico: auth-api
idp:
  jwks_url: https://idp.loja.internal/.well-known/jwks.json
  timeout_ms: 2000
container:
  limite_memoria: 512Mi
EOF
cat > auth-api/app.py <<'EOF'
"""auth-api: emite tokens e valida JWT consultando o provedor de identidade."""


def validar_token(token, idp):
    return idp.validar(token)
EOF

cat > README.md <<'EOF'
# loja-incidentes

Este é um repositório **fictício**, criado apenas para que o professor possa
validar o projeto de curso "agente investigador de incidentes" (AI Agents com
LangChain, Infnet). Nenhum código aqui roda em produção: os arquivos são
pequenos e servem só para que o histórico git conte uma história coerente com
os cenários de incidente do laboratório. O agente consulta este repositório
pela API REST **real** do GitHub para descobrir o que mudou antes de um incidente.

## Serviços e dependências

O sistema simulado é uma loja online com quatro serviços, cada um em sua pasta:

- `pedidos-api`: recebe e cria pedidos. Chama o `pagamentos-api` para cobrar e
  publica reservas na fila consumida pelo `estoque-worker`. Usa o banco
  `db-principal`.
- `pagamentos-api`: confirma pagamentos e chama o gateway externo PagaFácil
  (que não é um serviço deste repositório; só aparece na configuração).
- `estoque-worker`: consome a fila `estoque-reservas` e atualiza a tabela
  `estoque` no `db-principal`.
- `auth-api`: emite e valida tokens, consultando o provedor de identidade
  `idp.loja.internal`.

## Tags

As tags seguem o padrão `<servico>/vX.Y.Z` e são anotadas. Cada serviço tem uma
tag base (estado saudável) e, quando o incidente tem causa em código ou
configuração versionada, uma tag posterior com o commit responsável. O agente
compara duas tags do mesmo serviço para ver a causa.

| Tag | Base de comparação | Cenário | O que mudou |
|---|---|---|---|
| `pedidos-api/v3.1.0` | - | (baseline) | pool de conexões em 20 |
| `pagamentos-api/v2.13.4` | - | (baseline) | estado saudável |
| `estoque-worker/v1.5.2` | - | (baseline) | estado saudável |
| `auth-api/v1.7.9` | - | (baseline) | estado saudável |
| `pagamentos-api/v2.14.0` | `pagamentos-api/v2.13.4` | `deploy_com_bug` | desconto de cupom aplicado sem checar `cupom == null` (NullPointerException) |
| `pedidos-api/v3.2.0` | `pedidos-api/v3.1.0` | `pool_esgotado` | `pool_max` reduzido de 20 para 10; o pico de tráfego esgota o pool |
| `estoque-worker/v1.6.0` | `estoque-worker/v1.5.2` | `env_var_faltando` | `ESTOQUE_QUEUE_URL` passa a ser obrigatória e sai do `.env.example` e do `config.yaml` |
| `auth-api/v1.8.0` | `auth-api/v1.7.9` | `vazamento_memoria` | cache em memória de tokens sem limite (OOMKilled) |
| `pedidos-api/v3.2.1` | `pedidos-api/v3.2.0` | `banco_lento_com_deploy` | **distração**: só corrige o texto do e-mail de confirmação |

## Cenários sem commit (causa externa)

Alguns cenários têm causa fora do código versionado, e por isso **não têm
commit nem tag** neste repositório. O agente deve concluir que não há mudança
relevante no GitHub e buscar a causa em logs e métricas:

- `gateway_fora`: o PagaFácil ficou indisponível (HTTP 503).
- `certificado_expirado`: o certificado TLS de `idp.loja.internal` expirou.
- `rate_limit`: o tráfego estourou o limite de 100 req/min do PagaFácil (o
  valor aparece em `pagamentos-api/config.yaml`, mas não foi alterado).
- `banco_lento_com_deploy`: a causa real é uma reindexação no `db-principal`.
  O deploy `pedidos-api/v3.2.1` é um **distrator deliberado**: a mudança é
  inofensiva (texto de e-mail) e ocorre perto do incidente para testar se o
  agente evita culpar o deploy errado.

## Endpoints usados pelo agente

- `GET /repos/{owner}/{repo}/compare/{base}...{head}` (ex.:
  `compare/pagamentos-api/v2.13.4...pagamentos-api/v2.14.0`)
- `GET /repos/{owner}/{repo}/tags`
- `GET /repos/{owner}/{repo}/commits`

Repositório público: **não é preciso token** (limite de 60 requisições por
hora por IP). Se a variável de ambiente `GITHUB_TOKEN` estiver definida, ela
pode ser usada para subir o limite, mas é opcional.

## Recriar o histórico

O histórico é gerado de forma determinística (datas fixas em outubro de 2026)
por `criar_repo.sh <diretorio>`.
EOF

# Cada serviço tem seu bloco contíguo (base, mudança, ...), para que o compare
# entre duas tags do mesmo serviço contenha só os commits daquele serviço.
base() {  # base <servico> <data> <versao>
  git add "$1"
  commitar "$2" "chore($1): estado inicial saudável"
  marcar "$2" "$1/v$3" "$1 $3"
}

git add README.md
commitar "2026-10-01T09:00:00-03:00" "docs: README do repositório fictício loja-incidentes"

# ------------------------------------------------------------- pedidos-api
base pedidos-api "2026-10-01T10:00:00-03:00" 3.1.0

sed -i 's/pool_max: 20 .*/pool_max: 10          # conexões máximas com o banco/' pedidos-api/config.yaml
git add pedidos-api
commitar "2026-10-06T09:40:00-03:00" "perf: reduz pool máximo de 20 para 10 para aliviar o db-principal"
marcar "2026-10-06T09:50:00-03:00" pedidos-api/v3.2.0 "pedidos-api 3.2.0: pool máximo de conexões 10"

# distrator: mudança inofensiva
cat > pedidos-api/templates/email_confirmacao.txt <<'EOF'
Assunto: Pedido recebido

Olá {{nome}}, recebemos seu pedido {{pedido_id}}.
Em breve você receberá a confirmação do pagamento.
EOF
git add pedidos-api
commitar "2026-10-08T15:30:00-03:00" "fix: corrige texto do e-mail de confirmação (e90a4d7)" "joao.pereira <joao.pereira@example.com>"
marcar "2026-10-08T15:40:00-03:00" pedidos-api/v3.2.1 "pedidos-api 3.2.1: correção de texto do e-mail"

# ---------------------------------------------------------- pagamentos-api
base pagamentos-api "2026-10-12T10:00:00-03:00" 2.13.4

cat > pagamentos-api/src/PagamentoService.java <<'EOF'
package br.loja.pagamentos;

public class PagamentoService {

    public Pagamento confirmar(Pedido pedido, Cupom cupom) {
        double valor = pedido.getTotal() - cupom.getDesconto();
        return gateway.cobrar(pedido.getId(), valor);
    }
}
EOF
git add pagamentos-api
commitar "2026-10-14T14:20:00-03:00" "feat: aplica desconto de cupom na confirmação do pagamento (a1f3c9e)" "ana.souza <ana.souza@example.com>"
marcar "2026-10-14T14:30:00-03:00" pagamentos-api/v2.14.0 "pagamentos-api 2.14.0: desconto de cupom"

# ---------------------------------------------------------- estoque-worker
base estoque-worker "2026-10-16T10:00:00-03:00" 1.5.2

cat > estoque-worker/config.py <<'EOF'
import os

QUEUE_URL = os.environ["ESTOQUE_QUEUE_URL"]
EOF
cat > estoque-worker/.env.example <<'EOF'
LOG_LEVEL=INFO
EOF
sed -i '/queue_url:/d' estoque-worker/config.yaml
git add estoque-worker
commitar "2026-10-19T16:05:00-03:00" "refactor: lê a URL da fila da variável de ambiente ESTOQUE_QUEUE_URL (7bd0e21)" "carlos.lima <carlos.lima@example.com>"
marcar "2026-10-19T16:15:00-03:00" estoque-worker/v1.6.0 "estoque-worker 1.6.0: URL da fila via variável de ambiente"

# ---------------------------------------------------------------- auth-api
base auth-api "2026-10-22T10:00:00-03:00" 1.7.9

cat > auth-api/app.py <<'EOF'
"""auth-api: emite tokens e valida JWT consultando o provedor de identidade."""

_cache_tokens = {}  # token -> claims, nunca é limpo


def validar_token(token, idp):
    if token not in _cache_tokens:
        _cache_tokens[token] = idp.validar(token)
    return _cache_tokens[token]
EOF
git add auth-api
commitar "2026-10-27T11:10:00-03:00" "feat: adiciona cache em memória sem limite para tokens validados (c44e8b0)" "beatriz.alves <beatriz.alves@example.com>"
marcar "2026-10-27T11:20:00-03:00" auth-api/v1.8.0 "auth-api 1.8.0: cache em memória de tokens"

echo
echo "=== git log --oneline --decorate ==="
git log --oneline --decorate
echo
echo "=== tags ==="
git tag -n
