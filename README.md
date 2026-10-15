# OKR — Gestão e acompanhamento de OKRs do grupo

Aplicação web para cadastro, acompanhamento e análise de OKRs (Objectives and Key Results) de múltiplas empresas de um grupo empresarial.

> **Situação atual:** Etapa 8 (empresas, pessoas, ciclos, objetivos, KRs, check-ins e iniciativas). A aplicação roda localmente, com linha do tempo por objetivo e tela de auditoria; o painel e os gráficos serão entregues nas próximas etapas. Veja o [Plano de Implementação](docs/PLANO_IMPLEMENTACAO.md).

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

| `OKR_BACKUP_DIR` | Pasta dos backups, **fora do repositório** |
| `OKR_BACKUP_CHAVE` | Chave de criptografia dos backups |
| `OKR_BACKUP_RETENCAO` | Quantos backups diários manter (padrão 30) |

Detalhes em [docs/ARQUITETURA.md](docs/ARQUITETURA.md#8-configuração-de-ambientes).

## Backup e restauração

Os backups são **criptografados** e gravados em `OKR_BACKUP_DIR`, com um manifesto `.json` (data, checksum, contagem de registros por tabela). São mantidos os 30 backups diários mais recentes.

### Configuração (uma vez)

```powershell
.venv\Scripts\python manage.py gerar_chave_backup     # copie a chave para OKR_BACKUP_CHAVE no .env
```

> **Guarde uma cópia da chave fora deste computador** (por exemplo, em um gerenciador de senhas). Sem ela, os backups não podem ser restaurados. Trocar a chave não afeta backups antigos, que continuam exigindo a chave com que foram criados.

### Criar um backup

```powershell
.venv\Scripts\python manage.py backup_banco
# ou
powershell -ExecutionPolicy Bypass -File scripts\backup.ps1
```

Backup diário automático (Agendador de Tarefas do Windows, usuário atual, sem privilégios de administrador):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\agendar_backup.ps1 -Horario 12:30
# remover: Unregister-ScheduledTask -TaskName "OKR - Backup diario" -Confirm:$false
```

### Verificar um backup sem restaurar

```powershell
.venv\Scripts\python manage.py verificar_banco --backup C:\caminho\okr-AAAAMMDD-HHMMSS-xxxxxx.okrbak
.venv\Scripts\python manage.py verificar_banco          # integridade do banco atual
```

### Restaurar

1. **Pare a aplicação** (feche o `runserver`).
2. Execute:
   ```powershell
   .venv\Scripts\python manage.py restaurar_banco C:\caminho\okr-AAAAMMDD-HHMMSS-xxxxxx.okrbak
   ```
   Digite `RESTAURAR` para confirmar. Antes de substituir o banco, o comando:
   - confere o checksum e descriptografa (com chave errada ou arquivo adulterado, nada é alterado);
   - verifica a integridade do banco contido no backup;
   - cria um **backup de segurança** do banco atual (`antes-restauracao-*.okrbak`, nunca removido pela retenção).
3. Execute `.venv\Scripts\python manage.py migrate` e inicie a aplicação.

Para desfazer uma restauração, restaure o arquivo `antes-restauracao-*.okrbak` indicado na saída do comando.

## Estrutura

```
config/            configuração do projeto (settings por ambiente, URLs)
apps/core/         núcleo: serviços genéricos, acesso, erros, backup (banco/ isola o SQLite)
apps/auditoria/    histórico de alterações estruturais (somente inserção)
apps/cadastros/    empresas, pessoas, vínculos pessoa ↔ empresa e ciclos (anuais e trimestrais)
apps/contas/       modelo de usuário (login corporativo em etapa futura)
templates/         layout base
static/            CSS e bibliotecas servidas localmente
apps/okrs/         objetivos, vínculos anual ↔ trimestral, KRs, marcos e iniciativas
apps/okrs/dominio/ cálculo de progresso e cor (Python puro, sem banco)
apps/acompanhamento/ check-ins, retificações e atualizações de iniciativas (somente inserção)
scripts/           utilitários PowerShell (backup e agendamento)
docs/              especificação, arquitetura e plano
var/               banco local e arquivos gerados (ignorado pelo Git)
```

## Documentação

- [Especificação Funcional](docs/ESPECIFICACAO_FUNCIONAL.md)
- [Arquitetura](docs/ARQUITETURA.md)
- [Plano de Implementação](docs/PLANO_IMPLEMENTACAO.md)

## Proteção de dados

Este repositório contém **somente código e documentação**. Bancos de dados, backups, arquivos `.env` e exportações com dados empresariais são excluídos pelo [.gitignore](.gitignore) e nunca devem ser versionados.
