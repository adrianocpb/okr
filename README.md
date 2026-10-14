# OKR — Gestão e acompanhamento de OKRs do grupo

Aplicação web para cadastro, acompanhamento e análise de OKRs (Objectives and Key Results) de múltiplas empresas de um grupo empresarial.

> **Situação atual:** Etapa 1 (fundação técnica). A aplicação já roda localmente, mas os módulos de negócio (empresas, ciclos, objetivos, KRs etc.) ainda serão entregues nas próximas etapas. Veja o [Plano de Implementação](docs/PLANO_IMPLEMENTACAO.md).

## Requisitos

- Windows com **Python 3.14** instalado (o launcher `py` deve listá-lo em `py -0p`).
- Git.

> Neste ambiente, o comando `python` pode abrir o atalho da Microsoft Store. Use `py -3.14` apenas para criar o ambiente virtual e, depois, sempre `.venv\Scripts\python`.

## Primeira execução (PowerShell, na pasta do projeto)

```powershell
# 1. Ambiente virtual e dependências
py -3.14 -m venv .venv
.venv\Scripts\python -m pip install -r requirements\dev.txt

# 2. Configuração local (o .env não é versionado)
Copy-Item .env.example .env
#    Edite o .env e defina DJANGO_SECRET_KEY. Para gerar uma chave:
.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(64))"

# 3. Criar ou atualizar o banco (fica em var\okr.sqlite3, fora do Git)
.venv\Scripts\python manage.py migrate

# 4. Iniciar
.venv\Scripts\python manage.py runserver 127.0.0.1:8000
```

Acesse <http://127.0.0.1:8000>. A página inicial mostra se o banco está conectado e com a estrutura atualizada.

## Testes e qualidade

```powershell
.venv\Scripts\python -m pytest                       # testes automatizados
.venv\Scripts\python -m coverage run -m pytest; .venv\Scripts\python -m coverage report
.venv\Scripts\python -m ruff check .                 # lint
.venv\Scripts\python -m ruff format .                # formatação
.venv\Scripts\python manage.py makemigrations --check --dry-run
```

O GitHub Actions executa as mesmas verificações a cada envio (`.github/workflows/ci.yml`), usando apenas dados fictícios.

## Configuração

| Variável | Uso |
|---|---|
| `DJANGO_SETTINGS_MODULE` | `config.settings.dev` (local), `config.settings.test` (testes), `config.settings.prod` (servidor) |
| `DJANGO_SECRET_KEY` | Chave secreta; obrigatória e forte em produção |
| `DJANGO_DEBUG` | `true` somente em desenvolvimento; produção recusa iniciar com debug ativo |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos, separados por vírgula |
| `DATABASE_URL` | Banco de dados; padrão `sqlite:///var/okr.sqlite3` |

Detalhes em [docs/ARQUITETURA.md](docs/ARQUITETURA.md#8-configuração-de-ambientes).

## Estrutura

```
config/            configuração do projeto (settings por ambiente, URLs)
apps/core/         núcleo: página inicial e verificações
apps/contas/       modelo de usuário (login corporativo em etapa futura)
templates/         layout base
static/            CSS e bibliotecas servidas localmente
docs/              especificação, arquitetura e plano
var/               banco local e arquivos gerados (ignorado pelo Git)
```

## Documentação

- [Especificação Funcional](docs/ESPECIFICACAO_FUNCIONAL.md)
- [Arquitetura](docs/ARQUITETURA.md)
- [Plano de Implementação](docs/PLANO_IMPLEMENTACAO.md)

## Proteção de dados

Este repositório contém **somente código e documentação**. Bancos de dados, backups, arquivos `.env` e exportações com dados empresariais são excluídos pelo [.gitignore](.gitignore) e nunca devem ser versionados.
