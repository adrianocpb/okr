# Arquitetura — Sistema de Gestão de OKRs

> **Status:** proposta para validação (Etapa 0).
> **Data:** 14/10/2026.
> **Documentos relacionados:** [ESPECIFICACAO_FUNCIONAL.md](ESPECIFICACAO_FUNCIONAL.md) · [PLANO_IMPLEMENTACAO.md](PLANO_IMPLEMENTACAO.md)

Convenção usada neste documento:

- **[Fato]**: verificado no ambiente ou em fonte consultada.
- **[Recomendação]**: decisão proposta, que depende de validação.
- **[Hipótese]**: suposição ainda não verificada, com o modo de confirmá-la.

---

## 1. Ambiente encontrado (inspeção de 14/10/2026)

| Item | Situação | Tipo |
|---|---|---|
| Sistema operacional | Windows 11 Home (10.0.26200) | [Fato] |
| Repositório | `okr`, branch `main`, **sem commits**; remote `https://github.com/adrianocpb/okr.git` | [Fato] |
| Conteúdo inicial | Apenas a pasta `.git` (repositório vazio) | [Fato] |
| Identidade Git | `user.name` e `user.email` **não configurados**: commits falharão até a configuração | [Fato] |
| Python | 3.14.8 (64 bits) em `%LOCALAPPDATA%\Python\pythoncore-3.14-64`, acessível pelo launcher `py` | [Fato] |
| Alias `python` | Aponta para `WindowsApps\python.exe` (alias da Microsoft Store) e responde de forma **inconsistente**; usar `py` para criar o ambiente virtual e, depois, o Python do `.venv` | [Fato] |
| pip / venv | pip 26.2.1 e módulo `venv` disponíveis; nenhum pacote além do pip instalado globalmente | [Fato] |
| SQLite (embutido no Python) | 3.50.4 | [Fato] |
| OpenSSL | 3.5.9 | [Fato] |
| Node.js / npm | 24.21.0 / 11.19.0 | [Fato] |
| CLI `sqlite3` | Não instalada (não é necessária; o Python já inclui o SQLite) | [Fato] |
| Docker, WSL, `psql`, `pg_dump` | **Não disponíveis** | [Fato] |
| GitHub CLI (`gh`) | Não instalada | [Fato] |
| Acesso ao PyPI | Funcional; Django disponível nas versões 5.2.18 (LTS), 6.0.9 e 6.1.2 | [Fato] |

**Limitações identificadas**

1. Sem Docker nem PostgreSQL local, testes contra PostgreSQL exigirão instalar o PostgreSQL no Windows, usar um projeto Supabase **de testes** ou rodar em CI (GitHub Actions). A decisão está registrada no plano.
2. A instabilidade do alias `python` pode causar confusão; os scripts e o README usarão `py -3.14` apenas para criar o `.venv` e, a partir daí, `.venv\Scripts\python`.
3. Sem identidade Git configurada, nenhum commit pode ser criado. Isso precisa ser resolvido pelo usuário (`git config user.name` / `user.email`).

---

## 2. Stack técnica recomendada

### 2.1. Recomendação principal [Recomendação]

| Camada | Tecnologia | Versão-alvo |
|---|---|---|
| Linguagem | Python | 3.14 (já instalado) |
| Framework web | **Django** (LTS) | 5.2.x (suporte de segurança até abril de 2028) |
| Interface | Templates do Django renderizados no servidor, CSS próprio e JavaScript mínimo; **HTMX** opcional para interações parciais, servido localmente (sem CDN) | adotar somente quando necessário |
| Gráficos | Chart.js servido localmente (`static/vendor/`) | a partir da etapa de visualizações |
| Banco local | SQLite (via ORM do Django) | embutido |
| Banco em servidor | PostgreSQL (próprio ou gerenciado, como o Supabase) | 16+ |
| Driver PostgreSQL | psycopg 3 | somente quando a etapa de PostgreSQL começar |
| Configuração | Variáveis de ambiente + `.env` local (lido por `python-dotenv` somente em dev); `DATABASE_URL` interpretada por `dj-database-url` | — |
| Criptografia de backups | `cryptography` (Fernet: AES + HMAC) | a partir da E2 |
| Testes | pytest + pytest-django + coverage | — |
| Qualidade de código | ruff (lint e formatação) | — |
| Servidor de produção (futuro) | gunicorn + proxy reverso com HTTPS (Caddy ou nginx); arquivos estáticos via WhiteNoise | não instalar agora |

### 2.2. Justificativa

| Critério | Por que o Django atende |
|---|---|
| Facilidade de desenvolvimento | ORM, formulários com validação, templates, roteamento, administração, i18n e testes vêm integrados. Uma única base de código, sem build de front-end. |
| Manutenção | Framework maduro, com versões LTS e política de depreciação previsível. Menos dependências para atualizar. |
| Segurança | Proteção contra CSRF, XSS (escape automático), SQL injection (ORM parametrizado) e clickjacking, além de hashing de senhas, sessões seguras e `check --deploy`. |
| Testabilidade | Cliente de testes HTTP, banco de testes isolado e transações por teste; integração madura com pytest. |
| Persistência | ORM com **migrações versionadas** e suporte oficial a SQLite e PostgreSQL com a mesma API. |
| Multiusuário | Autenticação, grupos e permissões nativos, sessões no servidor e base pronta para SSO (OIDC/SAML) via bibliotecas consolidadas. |
| Custo e complexidade | Roda localmente com um comando; em servidor, um processo Python + PostgreSQL. Não exige filas, cache ou containers no início. |

**Por que a versão 5.2 LTS e não a 6.1?** [Recomendação] A 5.2 tem a janela de suporte mais longa (até abril de 2028). A 6.1 é mais recente, mas seu suporte termina antes. A migração para a próxima LTS (6.2, prevista para 2027) fica planejada como manutenção.
**[Hipótese]** O Django 5.2 é compatível com Python 3.14 desde a versão 5.2.8. **Como confirmar:** instalar no `.venv` na Etapa 1 e executar `manage.py check` e a suíte de testes. Se falhar, usar Django 6.1 ou instalar Python 3.13.

### 2.3. Alternativas avaliadas

| Alternativa | Avaliação |
|---|---|
| **FastAPI + SQLAlchemy/Alembic + SPA (React/Vue)** | Viável e performática, mas exige construir à mão autenticação, sessões, CSRF, formulários, validação de UI e administração, além de manter duas bases (API e front-end) com build. Mais custo para um sistema de cadastros e acompanhamento. |
| **Node.js (Next.js + Prisma ou Drizzle)** | Node 24 está disponível. É viável, mas autenticação, autorização, migrações e validação dependem de várias bibliotecas independentes, e o ecossistema muda rápido, o que aumenta a manutenção. |
| **Supabase como back-end completo (Auth + RLS + cliente no navegador)** | Reduz código de servidor, mas move regras de negócio e de acesso para políticas RLS e para o navegador, dificulta testes locais (sem Docker) e cria dependência de fornecedor. **Recomendação:** usar o Supabase, se escolhido, **apenas como PostgreSQL gerenciado**, com o Django como único caminho de acesso aos dados. |
| **Planilha ou ferramenta low-code** | Não atende de forma confiável aos requisitos de histórico imutável, auditoria, controle de acesso por empresa e evolução. |

---

## 3. Arquitetura da aplicação

### 3.1. Visão geral

Monólito modular: uma aplicação Django dividida em módulos (apps) por domínio, com camadas internas bem definidas.

```
 Navegador (HTML renderizado no servidor, pt-BR)
        │  HTTP (local: 127.0.0.1; futuro: HTTPS)
        ▼
 ┌──────────────────────────────────────────────────────────┐
 │ Apresentação: views, forms, templates, static            │  ← só formata e valida entrada
 ├──────────────────────────────────────────────────────────┤
 │ Aplicação: services (comandos) e selectors (consultas)   │  ← transações, auditoria, escopo
 ├──────────────────────────────────────────────────────────┤
 │ Domínio: regras puras (cálculo de progresso, alertas,    │  ← Python puro, sem ORM
 │          validações de negócio)                          │
 ├──────────────────────────────────────────────────────────┤
 │ Persistência: models + migrações (ORM do Django)         │  ← único ponto que conhece o banco
 └──────────────────────────────────────────────────────────┘
        │
        ▼
 SQLite (local)  ──── evolução ────►  PostgreSQL (servidor)
```

### 3.2. Responsabilidades por camada [Recomendação]

| Camada | Arquivos típicos | Pode | Não pode |
|---|---|---|---|
| Apresentação | `views.py`, `forms.py`, `urls.py`, `templates/` | Validar o formato da entrada, chamar services/selectors e renderizar | Gravar no banco diretamente; conter regra de negócio |
| Aplicação | `services.py`, `selectors.py` | Abrir transações, aplicar regras, registrar auditoria e filtrar pelo escopo de acesso | Depender de request/HTML |
| Domínio | `dominio/*.py` | Calcular progresso, situação e alertas com tipos simples (`Decimal`, `date`) | Importar o ORM ou acessar o banco |
| Persistência | `models.py`, `migrations/` | Definir o esquema, as restrições (`CheckConstraint`, `UniqueConstraint`) e os índices | Conter SQL específico de um banco fora de pontos isolados e documentados |

Regras transversais:

- **Toda gravação passa por um service.** O service recebe um `Ator` (quem está agindo) e um `EscopoAcesso` (empresas permitidas). Na versão local sem login, o `Ator` é "usuário local não autenticado" e o escopo cobre todas as empresas. Quando a autenticação for implementada, apenas a construção desses objetos muda, não as regras.
- **Toda consulta de dados de empresa passa por um selector** que recebe o `EscopoAcesso`. Isso prepara o isolamento entre empresas no servidor, e não só na interface.
- **Auditoria na mesma transação** da alteração: se o registro de auditoria falhar, a alteração é revertida (sem perda silenciosa).
- **Django Admin** [Recomendação]: não habilitado para entidades de negócio, porque contornaria services, auditoria e escopo. Pode ser usado somente leitura em desenvolvimento, se útil.
- **SQL específico de banco** fica isolado em `apps/core/banco/` (por exemplo, o backup SQLite), atrás de uma interface por motor.

### 3.2.1. Padrão de services (implementado na E2)

Os módulos de negócio usam as funções genéricas de `apps/core/services.py`, que já garantem validação (`full_clean`), bloqueio otimista, auditoria na mesma transação e arquivamento em vez de exclusão:

```python
# apps/<modulo>/services.py — exemplo do padrão
from apps.core import services
from apps.core.acesso import Ator, EscopoAcesso
from apps.core.erros import AcessoNegado


def alterar_empresa(empresa_id: int, dados: dict, *, versao: int, ator: Ator, escopo: EscopoAcesso):
    if not escopo.permite(empresa_id):
        raise AcessoNegado()
    empresa = Empresa.objects.get(pk=empresa_id)
    return services.atualizar(
        empresa, dados, versao_esperada=versao, ator=ator, empresa_id=empresa_id
    )


# apps/<modulo>/selectors.py — consultas sempre filtradas pelo escopo
def listar_objetivos(escopo: EscopoAcesso):
    return escopo.filtrar(Objetivo.objects.all(), campo="empresa_id")
```

A view recebe `versao` de um campo oculto do formulário. Em `ConflitoDeVersao`, a tela informa que o registro foi alterado por outra pessoa. Erros de negócio não tratados pela view são convertidos em página amigável (400/409) pelo `ErroDeNegocioMiddleware`; erros inesperados geram a página 500 em pt-BR e são registrados em log.

### 3.3. Multiempresa (isolamento de dados) [Recomendação]

- Modelo **banco compartilhado, coluna de empresa**: `Objetivo.empresa` é obrigatório; KRs, iniciativas, check-ins e atualizações herdam a empresa pelo objetivo. Registros de auditoria guardam `empresa_id` desnormalizado para permitir filtragem.
- O isolamento é garantido no servidor pelos selectors/services com `EscopoAcesso`, e não por ocultação na interface.
- No PostgreSQL, **Row Level Security** pode ser avaliada como defesa adicional, mas não substitui as verificações na aplicação.
- Testes automatizados verificarão que um escopo restrito à empresa A nunca retorna dados da empresa B, já na versão local.

### 3.4. Concorrência e integridade [Recomendação]

- **Bloqueio otimista** nas entidades editáveis (campo `versao`): uma edição baseada em versão desatualizada é recusada com mensagem clara, em vez de sobrescrever a alteração de outro usuário.
- Check-ins e atualizações de iniciativa são **somente inserção** (append-only). Os models bloqueiam `update`/`delete` pela aplicação e há testes para isso. No PostgreSQL será avaliado o reforço por permissões ou triggers.
- **Exclusão física** não é oferecida para entidades com histórico; usa-se **arquivamento**.
- Valores numéricos usam `Decimal` (`DecimalField`), nunca `float`.

---

## 4. Organização de pastas [Recomendação]

```
okr/
├── .gitignore
├── .gitattributes            # finais de linha normalizados (LF)
├── .github/workflows/ci.yml  # CI: lint, migrações e testes
├── .env.example              # somente nomes de variáveis e valores fictícios (Etapa 1)
├── README.md                 # como executar localmente
├── pyproject.toml            # configuração do ruff e do pytest (Etapa 1)
├── manage.py
├── requirements/
│   ├── base.txt              # dependências de execução (versões fixadas)
│   ├── dev.txt               # base + ferramentas de teste e qualidade
│   └── prod.txt              # base + gunicorn, psycopg, whitenoise (etapas de servidor)
├── config/                   # projeto Django (configuração, sem regra de negócio)
│   ├── settings/
│   │   ├── base.py           # comum a todos os ambientes
│   │   ├── dev.py            # desenvolvimento local
│   │   ├── test.py           # testes automatizados
│   │   └── prod.py           # servidor (HTTPS, cookies seguros, logs)
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── contas/               # modelo Usuario (login corporativo na E13)
│   ├── core/                 # base comum: modelo abstrato, Ator, EscopoAcesso, erros,
│   │   ├── banco/            #   utilidades, backup/restauração (isolado por motor de banco)
│   │   └── management/commands/   # gerar_chave_backup, backup_banco, restaurar_banco, verificar_banco
│   ├── auditoria/            # RegistroAlteracao (histórico estrutural)
│   ├── cadastros/            # Empresa, Pessoa, vínculo pessoa-empresa, Ciclo
│   ├── okrs/                 # Objetivo, VinculoObjetivo, ResultadoChave, Marco, Iniciativa
│   │   └── dominio/          # progresso.py, situacao.py (Python puro)
│   ├── acompanhamento/       # CheckIn, AtualizacaoIniciativa (somente inserção)
│   └── painel/               # dashboard, filtros, alertas (sem modelos próprios)
│   # cada app: models.py, services.py, selectors.py, forms.py, views.py, urls.py,
│   #           migrations/, templates/<app>/, tests/
├── templates/                # layout base, navegação, componentes compartilhados
├── static/
│   ├── css/
│   ├── js/
│   └── vendor/               # bibliotecas JS servidas localmente (sem CDN)
├── scripts/                  # utilitários PowerShell (iniciar, backup) para Windows
├── docs/
└── var/                      # (ignorada pelo Git) banco SQLite local, logs
```

Observação: o modelo `Usuario` customizado (herdando de `AbstractUser`) é criado **já na Etapa 1**, mesmo sem login ativo. Trocar o modelo de usuário depois da primeira migração é uma operação complexa no Django.

---

## 5. Modelo de dados inicial

Visão resumida. As regras completas estão na [Especificação Funcional](ESPECIFICACAO_FUNCIONAL.md#5-entidades-e-relacionamentos).

```
Empresa 1───N Ciclo (ANUAL | TRIMESTRAL; cada empresa tem os seus)
   │              └─ Ciclo trimestral N───1 Ciclo anual (mesma empresa)
   │
Empresa 1───N Objetivo N───1 Ciclo (da mesma empresa)
   │              │  │
   │              │  ├─ owner   ───► Pessoa
   │              │  ├─ sponsor ───► Pessoa
   │              │  └─ VinculoObjetivo (anual ◄─── trimestral), N:N opcional, só na mesma empresa
   │              │
   │              ├──1───N ResultadoChave ── responsavel ───► Pessoa
   │              │            ├──1───N Marco (para KRs do tipo MARCOS)
   │              │            └──1───N CheckIn (somente inserção)
   │              │                         └── CheckInMarco (marcos concluídos no check-in)
   │              │
   │              └──1───N Iniciativa (objetivo obrigatório)
   │                           ├── IniciativaKR N───N ResultadoChave (zero ou mais KRs)
   │                           ├── responsavel ───► Pessoa
   │                           └──1───N AtualizacaoIniciativa (somente inserção)
   │
Pessoa N───N Empresa (VinculoPessoaEmpresa)
Pessoa 0..1───0..1 Usuario (somente quando houver login)

RegistroAlteracao (auditoria): entidade, id, empresa, ação, diferenças (JSON), ator, data/hora
```

Campos comuns (modelo abstrato em `core`): `id`, `criado_em`, `atualizado_em`, `versao` (bloqueio otimista) e, quando aplicável, `arquivado_em`.

---

## 6. Estratégia de persistência

- **Local:** SQLite em `var/okr.sqlite3`, com caminho **relativo à raiz do projeto** e configurável por `DATABASE_URL`. Os dados sobrevivem à reinicialização da aplicação e nada fica apenas na memória ou no navegador.
- **Configuração do SQLite (dev):** `foreign_keys` ativado (padrão do Django), modo WAL e `busy_timeout` para reduzir erros de "database is locked". Essas opções ficam em `settings/dev.py` e em mais nenhum lugar.
- **Servidor:** PostgreSQL central, uma única fonte de dados para todos os usuários; nunca cópias locais sincronizadas.
- **Proibido:** sincronizar o banco local com o GitHub ou com pastas de nuvem pública como mecanismo de compartilhamento.

## 7. Migrações

- Todas as mudanças de esquema são feitas por **migrações do Django**, versionadas no Git.
- Migrações de dados (`RunPython`) devem ser reversíveis sempre que possível. Quando não forem, a irreversibilidade fica documentada na própria migração.
- Antes de aplicar migrações em um banco com dados reais, um **backup é obrigatório**. O comando de backup será documentado como passo prévio e, no servidor, fará parte do roteiro de implantação.
- O CI (quando aprovado) executará `makemigrations --check` para impedir alterações de modelo sem migração.

## 8. Configuração de ambientes

| Variável | Descrição | Exemplo fictício |
|---|---|---|
| `DJANGO_SETTINGS_MODULE` | Ambiente | `config.settings.dev` |
| `DJANGO_SECRET_KEY` | Chave secreta (gerada localmente, nunca versionada) | `trocar-por-chave-gerada` |
| `DJANGO_DEBUG` | Modo debug (apenas dev) | `true` |
| `DJANGO_ALLOWED_HOSTS` | Hosts permitidos | `127.0.0.1,localhost` |
| `DATABASE_URL` | Conexão com o banco | `sqlite:///var/okr.sqlite3` |
| `OKR_BACKUP_DIR` | Pasta de backups, **fora do repositório** (nesta máquina, `C:\Users\user\Backups\OKR`, definida só no `.env`) | `C:/caminho/para/backups` |
| `OKR_BACKUP_RETENCAO` | Quantidade de backups mantidos | `30` |
| `OKR_BACKUP_CHAVE` | Chave de criptografia dos backups (gerada por comando; guardar também fora da máquina, por exemplo em gerenciador de senhas) | `trocar-por-chave-gerada` |

- `settings/prod.py` falha ao iniciar se `DJANGO_SECRET_KEY` estiver ausente ou se `DEBUG` estiver ativo.
- Em dev, o servidor escuta somente em `127.0.0.1`.
- Nenhum caminho absoluto da máquina do desenvolvedor no código; caminhos derivados de `BASE_DIR` ou de variáveis de ambiente.
- Localização: `LANGUAGE_CODE = "pt-br"`, `TIME_ZONE = "America/Sao_Paulo"`, `USE_TZ = True` (datas armazenadas em UTC e exibidas no fuso local).

## 9. Estratégia de testes (resumo)

| Nível | O que cobre | Ferramenta |
|---|---|---|
| Domínio | Cálculo de progresso por tipo de métrica, situação, alertas e casos-limite | pytest (sem banco) |
| Services | Regras de negócio, transações, auditoria, imutabilidade, escopo por empresa | pytest-django (banco de teste) |
| Persistência | Restrições do banco (unicidade, checagens, FKs), migrações aplicáveis do zero | pytest-django |
| Interface | Rotas, formulários, mensagens em pt-BR, códigos HTTP, proteção CSRF | cliente de teste do Django |
| Banco-alvo | Suíte completa contra PostgreSQL antes da implantação | CI ou Postgres de testes |
| Backup | Backup gerado, verificado e restaurado em banco temporário | pytest + comando |

Detalhes no [Plano de Implementação](PLANO_IMPLEMENTACAO.md#3-estratégia-de-testes).

## 10. Segurança

**Versão local (desenvolvimento e validação):**

- Executa em `127.0.0.1`, sem exposição na rede.
- Sem login: o autor de um check-in é **informado manualmente** e exibido como "informado (não verificado)". A aplicação não o apresenta como identidade comprovada.
- Proteções nativas do Django ativas (CSRF, escape de templates, ORM parametrizado).
- Segredos apenas em `.env` (ignorado pelo Git); banco e backups fora do controle de versão.

**Obrigatório antes de qualquer acesso por outros usuários:**

1. Login individual por **conta corporativa** (SSO via OIDC; provedor Microsoft ou Google a definir, Q-14b).
2. Autorização por dois perfis, **Administrador** e **Usuário** (permissões do Usuário a detalhar, Q-13b).
3. Controle de acesso por empresa aplicado nos services/selectors, coberto por testes.
4. Todas as rotas protegidas no servidor (nenhuma rota de dados acessível sem login).
5. Auditoria com usuário autenticado.
6. Sessões seguras: cookies `Secure`, `HttpOnly`, `SameSite`, expiração e logout.
7. HTTPS obrigatório, HSTS, `check --deploy` sem alertas críticos.
8. Limitação de tentativas de login.
9. Revisão de segurança antes da publicação.

## 11. Backup e restauração

[Recomendação] Implementado como comandos de gerenciamento, independentes do repositório de código:

- `backup_banco`: no SQLite, usa a **API de backup online** do SQLite (cópia consistente mesmo com a aplicação aberta), verifica a integridade da cópia, **criptografa** o arquivo com a chave de `OKR_BACKUP_CHAVE` e grava em `OKR_BACKUP_DIR` (criada se não existir) com nome datado, checksum SHA-256 e manifesto (data, versão das migrações, tamanho). A cópia temporária não criptografada é apagada em seguida.
- `gerar_chave_backup`: gera a chave de criptografia e orienta onde guardá-la. **Sem a chave, os backups não podem ser restaurados.**
- `restaurar_banco`: exige confirmação explícita, faz antes um **backup de segurança** do banco atual, confere o checksum, descriptografa em arquivo temporário, verifica a integridade e só então substitui o banco. Deve ser executado com a aplicação parada.
- `verificar_banco`: checagem de integridade sob demanda.
- Retenção: últimos **30 backups diários**, ajustável por `OKR_BACKUP_RETENCAO`.
- Agendamento diário via Agendador de Tarefas do Windows: script em `scripts/`; o registro da tarefa no Windows só será feito com sua aprovação.
- **Restauração testada** automaticamente (backup → restauração em banco temporário → comparação de contagens).
- Backups com dados reais são **sempre criptografados** (Q-18), o que protege também cópias em pastas sincronizadas ou compartilhadas. A pasta deve ter acesso restrito.
- Procedimento de restauração documentado no README e ensaiado.
- No servidor: `pg_dump` agendado e/ou backup gerenciado do provedor (PITR), cópia em local separado e teste periódico de restauração.

## 12. Caminho de migração para PostgreSQL

### 12.1. Diferenças que exigem atenção

| Aspecto | SQLite | PostgreSQL | Mitigação |
|---|---|---|---|
| Tipagem | Dinâmica (afinidade); aceita valores fora do tipo declarado | Estrita | Validar nos forms e services; testes na suíte PostgreSQL |
| Decimal | Armazenado com afinidade numérica (pode perder precisão em valores muito longos) | `numeric` exato | `max_digits`/`decimal_places` definidos; testes de arredondamento |
| Busca textual | `LIKE` sem distinção de maiúsculas apenas para ASCII; acentos ("Ã", "ç") não são normalizados | `ILIKE` com Unicode; `unaccent` disponível | Não depender de busca com acentos no SQLite; avaliar `unaccent` no PostgreSQL |
| Concorrência | Um escritor por vez; possíveis bloqueios | MVCC, muitos escritores | Bloqueio otimista; transações curtas |
| `select_for_update` | Ignorado | Efetivo | Não depender dele para correção na versão local |
| `ALTER TABLE` | Limitado (o Django recria a tabela) | Completo | Revisar migrações grandes antes de rodar em produção |
| Restrições | CHECK e FK suportados (FK precisa estar ativo) | Completo, com restrições adiáveis | Declarar restrições nos models; testar violações nos dois bancos |
| Datas/fuso | Texto | `timestamptz` | `USE_TZ=True` em todos os ambientes |
| JSON | Extensão JSON1 (presente no 3.50) | `jsonb` | Usar apenas operações portáveis do `JSONField` |
| Sequências | Autoincremento implícito | Sequências; precisam de ajuste após carga de dados | Rodar `sqlsequencereset` após a importação |
| Ordenação de texto | Binária por padrão | Depende da collation | Definir a ordenação explicitamente onde importa |

### 12.2. Procedimento proposto

1. Manter o código livre de SQL específico (somente ORM), com exceções isoladas em `core/banco/`.
2. Executar a suíte de testes também contra PostgreSQL **antes** da fase de servidor (CI com serviço PostgreSQL ou projeto de testes isolado).
3. Criar o banco PostgreSQL vazio e aplicar `migrate` (o esquema vem das migrações, não de cópia do SQLite).
4. Exportar os dados do SQLite (`dumpdata` com chaves naturais ou comando de exportação próprio), importar no PostgreSQL e ajustar as sequências.
5. Validar: contagens por tabela, somatórios de controle, amostragem de históricos e checksums dos valores de check-in.
6. Ensaiar a migração completa ao menos uma vez em ambiente de homologação antes da migração definitiva.

### 12.3. Supabase (se avaliado)

- Usar como **PostgreSQL gerenciado**, com conexão do Django por `DATABASE_URL` e SSL obrigatório.
- Atenção ao *pooler*: no modo *transaction*, desativar *server-side cursors* (`DISABLE_SERVER_SIDE_CURSORS=True`) e evitar *prepared statements*; ou usar o modo *session*/conexão direta.
- Não expor a chave `service_role` nem usar o cliente Supabase no navegador para acessar tabelas. O Django continua sendo o único caminho de acesso.
- Verificar a região de hospedagem dos dados (LGPD), a política de backup/PITR do plano contratado e os limites do plano gratuito, como a pausa por inatividade (a confirmar na documentação vigente do provedor).

### 12.4. Recomendação de banco para multiusuário

[Recomendação] **PostgreSQL**, seja auto-hospedado ou gerenciado. O SQLite é adequado para a validação local e de um único usuário, mas não para escrita concorrente em servidor nem para backups gerenciados com recuperação pontual. A escolha entre PostgreSQL próprio, Supabase ou outro provedor depende de custo, região dos dados e de quem fará a operação, e está registrada como decisão pendente.

## 13. Caminho de implantação futura em servidor

| Tema | Proposta |
|---|---|
| Ambiente | VM Linux ou PaaS com suporte a Python; processo gunicorn atrás de proxy reverso (Caddy ou nginx) |
| Banco | PostgreSQL central (ver §12) |
| Migrações | `migrate` executado no deploy, **após** um backup e antes de ativar a nova versão |
| Variáveis de ambiente | Definidas no provedor ou no serviço do sistema, nunca em arquivos versionados |
| Armazenamento persistente | Banco no PostgreSQL; arquivos estáticos via WhiteNoise; sem uploads no escopo atual |
| Backups | `pg_dump` agendado e/ou PITR do provedor, cópia externa e teste de restauração mensal |
| HTTPS | Obrigatório (certificado automático com Caddy/Let's Encrypt ou do provedor); HSTS |
| Autenticação/autorização | Implementadas e validadas antes da publicação (ver §10) |
| Logs e monitoramento | Logs estruturados em stdout/journal; endpoint de saúde; monitoramento de erros (ferramenta a decidir) |
| Atualização | Versões marcadas com tags Git; deploy de tag específica |
| Reversão | Voltar à tag anterior; se houver migração irreversível, restaurar o backup feito antes do deploy |
| Ambientes | Homologação separada de produção, com dados fictícios ou anonimizados |
