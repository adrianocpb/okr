# Plano de Implementação — Sistema de Gestão de OKRs

> **Status:** proposta para validação (Etapa 0).
> **Data:** 14/10/2026.
> **Documentos relacionados:** [ESPECIFICACAO_FUNCIONAL.md](ESPECIFICACAO_FUNCIONAL.md) · [ARQUITETURA.md](ARQUITETURA.md)

---

## 1. Princípios de execução

1. **Uma etapa por vez.** Cada etapa só começa após a validação da anterior.
2. **Funcionalidade ponta a ponta.** Uma etapa entrega modelo, regras, persistência, tela funcional e testes. Telas estáticas ou botões sem efeito não contam como entrega.
3. **Critérios de aceite verificáveis.** A etapa é concluída quando todos os critérios são atendidos e demonstrados, não quando a interface fica pronta.
4. **Relato fiel.** Ao fim de cada etapa: o que foi feito, quais testes foram **efetivamente executados** e seus resultados, o que ficou pendente.
5. **Sem dados reais no Git.** Testes usam dados fictícios gerados no próprio teste.

### Definição de pronto (vale para todas as etapas a partir da 1)

- [ ] Testes automatizados da etapa escritos e **executados**, com a suíte completa passando.
- [ ] `ruff check` e `ruff format --check` sem erros.
- [ ] `manage.py makemigrations --check` sem migrações pendentes.
- [ ] `manage.py check` sem erros.
- [ ] Textos da interface em pt-BR.
- [ ] Documentação atualizada (README e/ou docs afetados).
- [ ] `git status` sem banco, backup, `.env` ou dados reais.
- [ ] Roteiro de verificação manual descrito e executado no navegador.

---

## 2. Etapas

Visão geral e dependências:

```
E0 → E1 → E2 → E3 → E4 → E5 → E6 → E7 → E8 → E9 → E10 → E11
                                                   │
          (antes de qualquer acesso multiusuário)  ▼
                                    E12 (PostgreSQL) → E13 (Segurança) → E14 (Servidor)
```

E8 depende de E6 (KRs) e pode correr em paralelo com E7 se for conveniente. E12 pode começar após E7, porque a partir daí o modelo de dados central está estável.

---

### E0 — Inspeção, arquitetura e documentação ✅ (esta etapa)

**Objetivo:** definir a stack, a arquitetura, o modelo conceitual e o plano.
**Entregáveis:** `.gitignore`, `README.md`, `docs/ARQUITETURA.md`, `docs/ESPECIFICACAO_FUNCIONAL.md`, `docs/PLANO_IMPLEMENTACAO.md`.
**Critérios de aceite:**
- [ ] Ambiente inspecionado e registrado (Arquitetura §1).
- [ ] Stack justificada, com alternativas.
- [ ] Modelo de entidades e regras de responsabilidade explícitos.
- [ ] Estratégia SQLite → PostgreSQL e caminho para servidor documentados.
- [ ] Riscos, requisitos de segurança e dúvidas registrados.
- [ ] **Validação do solicitante.**

---

### E1 — Fundação técnica ✅

**Objetivo:** projeto executável localmente, com configuração por ambiente, testes e qualidade automatizados.
**Dependências:** E0 validada (identidade Git já configurada no repositório).
**Entregáveis:**
- Ambiente virtual `.venv` criado com `py -3.14`; `requirements/base.txt` e `requirements/dev.txt` com versões fixadas.
- Projeto Django (`config/`) com `settings/base.py`, `dev.py`, `test.py` e `prod.py` (o `prod.py` só com verificações de segurança, sem servidor).
- `.env.example` com variáveis fictícias; leitura de `.env` em dev.
- Modelo de usuário customizado (`Usuario`), ainda sem login ativo.
- pt-BR, fuso `America/Sao_Paulo`, formatos de data e número brasileiros.
- Layout base (cabeçalho, menu, área de mensagens) e página inicial que confirma a conexão com o banco.
- `pyproject.toml` com configuração de ruff e pytest; testes de fumaça.
- `README.md` com instruções de instalação e execução no Windows.
- Workflow de CI no GitHub Actions rodando lint, `makemigrations --check` e testes, somente com dados fictícios (DT-03 aprovada).

**Critérios de aceite:**
- [ ] `manage.py check` sem erros, com Django instalado e compatível com Python 3.14 (verificação da hipótese da Arquitetura §2.2).
- [ ] `manage.py migrate` cria `var/okr.sqlite3`; os dados sobrevivem à reinicialização do servidor.
- [ ] `pytest` executa e passa (fumaça: página inicial responde 200 em pt-BR; settings de prod recusam `DEBUG=True` e `SECRET_KEY` ausente).
- [ ] Servidor de desenvolvimento acessível em `http://127.0.0.1:8000`.
- [ ] `git status` não lista `var/`, `.env` nem `.venv`.
- [ ] Nenhum caminho absoluto da máquina no código.

---

### E2 — Núcleo transversal: base, auditoria, erros e backup ✅

**Objetivo:** criar os mecanismos dos quais todos os módulos dependem antes que existam dados a proteger.
**Dependências:** E1.
**Entregáveis:**
- Modelo abstrato (`criado_em`, `atualizado_em`, `versao`, arquivamento).
- Objetos `Ator` e `EscopoAcesso` e o padrão services/selectors documentado com um exemplo.
- App `auditoria` com `RegistroAlteracao` e a função de registro de diferenças.
- Tratamento de erros: exceções de domínio → mensagens amigáveis; páginas 404/500 em pt-BR; logging em `var/logs` (dev).
- Bloqueio otimista: utilitário e erro de "registro alterado por outra pessoa".
- Comandos `gerar_chave_backup`, `backup_banco`, `restaurar_banco` e `verificar_banco` (SQLite isolado em `core/banco/`), com criptografia, manifesto, checksum e retenção de 30 backups.
- Pasta `C:\Users\user\Backups\OKR` criada na primeira execução (caminho vindo do `.env`).
- Scripts PowerShell `scripts/backup.ps1` e `scripts/agendar_backup.ps1` (o registro da tarefa diária no Windows só será feito com sua aprovação).

**Critérios de aceite:**
- [ ] Teste: uma alteração cujo registro de auditoria falha é **revertida** por completo.
- [ ] Teste: a auditoria registra os valores anterior e novo de cada campo alterado.
- [ ] Teste: uma edição com `versao` desatualizada é recusada sem sobrescrever.
- [ ] Teste: backup gerado → integridade verificada → restauração em banco temporário → contagens idênticas.
- [ ] Teste: a restauração cria um backup de segurança do banco atual antes de substituí-lo.
- [ ] Teste: o arquivo de backup é criptografado (não abre como SQLite sem a chave), e a restauração com chave errada falha sem alterar o banco atual.
- [ ] Teste: a retenção mantém apenas os N backups mais recentes.
- [ ] `backup_banco` recusa gravar dentro da pasta do repositório.
- [ ] Procedimento de restauração documentado no README e **executado** manualmente uma vez, com resultado registrado.

---

### E3 — Empresas e Pessoas ✅

**Objetivo:** cadastros base, funcionais e auditados.
**Dependências:** E2.
**Entregáveis:** listagem, criação, edição, arquivamento e reativação de Empresas e Pessoas; vínculo pessoa ↔ empresas; filtros e busca simples (sem distinguir acentos). A seção de responsabilidades da pessoa entra na E5, junto com os objetivos (não foi criada vazia).
**Critérios de aceite:**
- [ ] Unicidade de nome e sigla da empresa e de e-mail da pessoa garantida no banco e com mensagem em pt-BR.
- [ ] Arquivamento não exclui o registro; o registro arquivado não aparece nas opções de novas atribuições.
- [ ] Toda criação, edição e arquivamento gera auditoria (teste).
- [ ] Teste de escopo: um `EscopoAcesso` restrito à empresa A não lista a empresa B nem pessoas vinculadas só a B.
- [ ] Fluxo completo executado no navegador (roteiro manual registrado).

---

### E4 — Ciclos ✅

**Objetivo:** gestão de ciclos anuais e trimestrais.
**Dependências:** E3 (cada empresa tem seus próprios ciclos, decisão Q-03).
**Entregáveis:** CRUD de ciclos por empresa; associação trimestral → anual da mesma empresa; situação do ciclo; consulta de ciclos anteriores; ação de apoio "gerar trimestres que faltam" (implementada). Situação calculada pelas datas.
**Critérios de aceite:**
- [ ] Testes: trimestre fora das datas do anual ou de outra empresa é recusado; sobreposição de ciclos do mesmo tipo na mesma empresa é recusada (em empresas diferentes é permitida); datas com início > fim são recusadas.
- [ ] Ciclo encerrado continua listado e consultável.
- [ ] Auditoria de alterações de datas e situação.

---

### E5 — Objetivos e vínculos anual ↔ trimestral ✅

**Objetivo:** cadastro de objetivos com Owner e Sponsor e desdobramento explícito.
**Dependências:** E3, E4.
**Entregáveis:** CRUD de objetivos com status; vínculo N:N anual ↔ trimestral; tela de detalhe (dados, vínculos e auditoria; KRs e iniciativas como seções preparadas para E6/E8); listagem por empresa e ciclo.
**Critérios de aceite:**
- [ ] Owner e Sponsor obrigatórios; somente pessoas ativas (e vinculadas à empresa, conforme Q-02b); ciclo da mesma empresa do objetivo.
- [ ] Objetivo trimestral pode ser salvo **sem** vínculo anual (teste).
- [ ] Testes de vínculo: recusado entre ciclos incompatíveis, entre empresas diferentes (proibido, Q-06) e em duplicidade.
- [ ] Concluir ou cancelar exige comentário.
- [ ] Troca de Owner ou Sponsor registrada na auditoria com antes e depois (teste).
- [ ] Teste de escopo por empresa nas listagens e no detalhe (acesso por ID de outra empresa retorna 404).

---

### E6 — KRs, métricas e cálculo de progresso ✅

**Objetivo:** KRs com medição flexível e cálculo correto e testado.
**Dependências:** E5.
**Entregáveis:** módulo de domínio `progresso.py` (Python puro) para os tipos NUMÉRICO, MANUTENÇÃO, BINÁRIO e MARCOS; CRUD de KRs com formulário que muda conforme o tipo; marcos; frequência de check-in (padrão 14 dias); função de **cor de progresso** (Especificação §7.5) no módulo de domínio.
**Critérios de aceite:**
- [ ] **Não existem campos Owner/Sponsor no KR** (teste de modelo); responsável obrigatório.
- [ ] Testes de domínio cobrindo: crescente, decrescente, percentual como métrica (12% → 15%), regressão (< 0%), superação (> 100%), meta = linha de base (erro), manutenção ≥ / ≤ / entre, binário, marcos (0, parcial, total) e precisão decimal.
- [ ] Validação: direção coerente com meta e linha de base (CRESCENTE exige meta > base etc.).
- [ ] Bloqueio de troca de tipo de medição em KR com check-ins (teste, efetivo a partir de E7).
- [ ] Cobertura de testes do módulo de domínio ≥ 95%.
- [ ] Alterações de meta e linha de base auditadas.
- [ ] Testes da cor de progresso: 0% e negativo = vermelho; 50% = laranja/amarelo; ≥ 90% e > 100% = verde; interpolação contínua entre os pontos; binário, manutenção e sem check-in conforme a especificação.

---

### E7 — Check-ins ✅

**Objetivo:** registro de acompanhamento com histórico imutável.
**Dependências:** E6.
**Entregáveis:** formulário de check-in (por tipo de medição); histórico do KR; retificação com justificativa; cópia da meta e da linha de base vigentes; autor informado marcado como "não verificado"; regra de check-in vigente; cálculo da próxima data esperada.
**Critérios de aceite:**
- [ ] Teste: não é possível alterar nem excluir um check-in pela aplicação (tentativa gera erro).
- [ ] Teste: a retificação cria um novo registro e o original permanece no histórico, marcado como retificado.
- [ ] Teste: após mudar a meta do KR, o progresso de check-ins antigos permanece o calculado com a meta da época.
- [ ] Teste: data de referência futura é recusada.
- [ ] Teste: check-in vigente segue a regra (data de referência mais recente; desempate pelo registro).
- [ ] O histórico de check-ins é exibido separadamente do histórico de alterações.
- [ ] A interface mostra explicitamente "autor informado (não verificado)".

---

### E8 — Iniciativas e acompanhamento da execução ✅

**Objetivo:** ações vinculadas a objetivos/KRs, com acompanhamento.
**Dependências:** E6 (pode correr em paralelo com E7).
**Entregáveis:** CRUD de iniciativas (objetivo obrigatório; zero, um ou vários KRs, Q-08); status e prazo; atualizações de execução (somente inserção); auditoria de alterações estruturais.
**Critérios de aceite:**
- [ ] Teste: iniciativa vinculada a vários KRs; vínculo duplicado recusado; KR fora da regra de Q-21 recusado.
- [ ] Teste: inclusão e remoção de KR vinculado registradas na auditoria.
- [ ] Teste: responsável obrigatório; sem campos Owner/Sponsor.
- [ ] Teste: atualizações não são editáveis nem excluíveis.
- [ ] Teste: iniciativa não altera o progresso do KR.
- [ ] Conclusão registra a data de conclusão automaticamente.

---

### E9 — Consulta de históricos ✅

**Objetivo:** tornar os dois históricos fáceis de consultar.
**Dependências:** E7, E8.
**Entregáveis:** linha do tempo do objetivo (check-ins, atualizações e alterações, com filtro por tipo); tela de auditoria com filtros (entidade, empresa, período); exibição legível das diferenças (antes → depois).
**Critérios de aceite:**
- [ ] Os históricos de acompanhamento e de alterações são distinguíveis visualmente e por filtro.
- [ ] Teste de escopo: a auditoria de uma empresa não aparece para um escopo de outra.
- [ ] Listagens paginadas.

---

### E10 — Dashboard, filtros e alertas ✅ (aguardando validação)

**Objetivo:** visão consolidada com identificação do que precisa de atenção.
**Dependências:** E7, E8.
**Entregáveis:** painel com filtros combináveis (empresa, ciclo, período, status/situação); cards de objetivo com distribuição de situação dos KRs e situação mais crítica; KRs com progresso individual, unidade própria e **cor de progresso** (vermelho → verde); alertas da Especificação §7.6; filtros preservados na URL (compartilháveis e com "voltar" funcional).
**Critérios de aceite:**
- [ ] Teste: **nenhuma** média ou soma de percentuais de KRs distintos é apresentada (o agrupamento usa contagens).
- [ ] Testes de cada regra de alerta, com datas controladas (relógio injetável no domínio).
- [ ] Teste: combinação de filtros retorna exatamente o conjunto esperado.
- [ ] Cores e alertas sempre acompanhados de número ou texto (não só cor).
- [x] Desempenho: painel com a massa de referência da RNF-13 (gerada por comando de dados fictícios) responde em < 1 s localmente (medido e registrado).
  - Medição em 15/10/2026 (10 empresas, 2.000 objetivos, 6.000 KRs, 50.000 check-ins, SQLite local, comando `gerar_dados_ficticios`): painel padrão 0,17–0,19 s; ano inteiro com todos os status 0,52–0,65 s; filtro por empresa 0,05 s. A primeira medição do ano inteiro (1,6–2,0 s) levou a três otimizações: marcos só para KRs do tipo Marcos, textos montados só para a página exibida e links de alertas gerados só quando exibidos.

---

### E11 — Visualizações de evolução e comparação entre períodos ✅ (aguardando validação)

**Objetivo:** gráficos de evolução e comparações válidas.
**Dependências:** E10.
**Entregáveis:** gráfico por KR (valores, meta e linha de base) em SVG gerado no servidor (substitui o Chart.js previsto: sem dependência externa e testável); evolução do mesmo KR ao longo dos check-ins; comparação entre ciclos (objetivo anual e trimestrais vinculados) com os KRs lado a lado, sem cálculo combinado.
**Critérios de aceite:**
- [ ] Teste: nenhuma comparação entre períodos combina valores de KRs diferentes.
- [ ] Gráficos funcionam sem internet (sem CDN).
- [ ] Dados dos gráficos conferem com o histórico de check-ins (teste da camada que gera os dados).

---

### E12 — Preparação para PostgreSQL

**Objetivo:** provar que a aplicação funciona em PostgreSQL antes do servidor.
**Dependências:** E7 (modelo central estável); decisão DT-04.
**Entregáveis:** `requirements/prod.txt` com psycopg 3; suíte de testes executando também contra PostgreSQL (CI ou instância de testes); comando de exportação/importação SQLite → PostgreSQL com relatório de validação; documento de ensaio de migração.
**Critérios de aceite:**
- [ ] Suíte completa **executada e passando** em PostgreSQL (resultado registrado).
- [ ] Migração de uma base fictícia: contagens por tabela idênticas, somatórios de controle conferidos e sequências ajustadas.
- [ ] Diferenças encontradas registradas e tratadas (Arquitetura §12.1).

---

### E13 — Autenticação, autorização e controle por empresa

**Objetivo:** controles obrigatórios antes de qualquer acesso por outros usuários.
**Dependências:** E12; decisões Q-13b e Q-14b.
**Entregáveis:** login por conta corporativa (SSO via OIDC) e logout; associação usuário ↔ pessoa; perfis Administrador e Usuário; `EscopoAcesso` derivado do usuário; proteção de todas as rotas; auditoria e check-ins com usuário autenticado (autor verificado); limitação de tentativas; configuração de sessão segura.
**Critérios de aceite:**
- [ ] Testes: acesso sem login redireciona para o login em **todas** as rotas de dados (teste que percorre as rotas registradas).
- [ ] Testes: usuário da empresa A recebe 404/403 ao acessar por URL ou ID qualquer recurso da empresa B, inclusive em operações de escrita.
- [ ] Testes: cada perfil (Administrador, Usuário) só executa as operações permitidas.
- [ ] Check-ins feitos com login exibem o autor como verificado; os anteriores continuam "não verificados".
- [ ] `manage.py check --deploy` (settings de prod) sem alertas críticos.
- [ ] Revisão de segurança documentada.

---

### E14 — Homologação e implantação em servidor

**Objetivo:** primeira publicação controlada.
**Dependências:** E13; decisão de hospedagem (Q-19).
**Entregáveis:** roteiro de implantação; servidor de homologação com HTTPS; PostgreSQL central; backup agendado e restauração testada; logs e endpoint de saúde; procedimento de atualização e reversão.
**Critérios de aceite:**
- [ ] Restauração de backup testada no ambiente de homologação.
- [ ] Deploy e reversão de versão ensaiados.
- [ ] Usuários de teste de empresas diferentes validam o isolamento.
- [ ] Aprovação explícita do solicitante antes da produção.

---

## 3. Estratégia de testes

| Tipo | Escopo | Quando |
|---|---|---|
| Unidade de domínio | Cálculo de progresso, situação, alertas (Python puro, datas injetadas) | E6 em diante |
| Services | Regras, transações, auditoria, imutabilidade, bloqueio otimista, escopo | E2 em diante |
| Persistência | Restrições do banco, migrações do zero, integridade referencial | E1 em diante |
| Interface | Rotas, formulários, mensagens pt-BR, CSRF, códigos HTTP | E1 em diante |
| Isolamento entre empresas | Selectors e rotas com escopos diferentes | E3 em diante (com usuários reais em E13) |
| Backup/restauração | Ciclo completo em banco temporário | E2 em diante |
| PostgreSQL | Suíte completa no banco de destino | E12 em diante |
| Manual no navegador | Roteiro por etapa, executado e registrado | Todas as etapas |

Regras:

- Dados de teste criados por fábricas no próprio teste; nada de dados reais em fixtures.
- Datas controladas por um relógio injetável, para testes determinísticos de alertas.
- Testes de navegador automatizados (por exemplo, Playwright) ficam como decisão futura, não incluídos inicialmente.
- Resultados de testes informados como executados somente quando de fato executados, com o comando e o resumo da saída.

---

## 4. Riscos técnicos

| # | Risco | Impacto | Mitigação |
|---|---|---|---|
| R-01 | Compatibilidade do Django 5.2 com Python 3.14 (versão recente) | Atraso na E1 | Verificar na E1; alternativas: Django 6.1 ou Python 3.13 |
| R-02 | Alias `python` instável no Windows | Comandos executados no interpretador errado | Usar `py -3.14` e o Python do `.venv`; documentar no README |
| R-03 | Perda de dados locais (falha de disco, exclusão acidental) | Alto | Backup na E2, antes de qualquer cadastro real; restauração testada |
| R-04 | Vazamento de dados empresariais no Git | Alto | `.gitignore` desde a E0; banco em `var/`; revisão do `git status` na definição de pronto |
| R-05 | Diferenças SQLite × PostgreSQL descobertas tarde | Médio | Somente ORM; testes em PostgreSQL na E12, antes do servidor |
| R-06 | Agregação enganosa de percentuais | Decisões erradas | Regra de agregação por contagem; teste específico na E10 |
| R-07 | Autoria não verificável na versão local | Confiança nos registros | Rótulo "não verificado"; usuário autenticado registrado a partir da E13 |
| R-08 | Incluir autenticação tarde e de forma intrusiva | Retrabalho | `Usuario` customizado na E1; `Ator` e `EscopoAcesso` em todos os services desde a E2 |
| R-09 | Requisitos ambíguos (Q-01 a Q-22) | Retrabalho | Decisões propostas registradas; validação antes da etapa afetada |
| R-10 | Sem Docker/PostgreSQL local | Dificulta a E12 | Decidir DT-04 (PostgreSQL local para Windows, projeto Supabase de testes ou CI) |
| R-11 | Concorrência de escrita no SQLite | Erros "database is locked" | WAL + `busy_timeout` em dev; PostgreSQL no servidor |
| R-12 | Identidade Git não configurada | Impossível commitar | **Resolvido:** configurada no repositório em 14/10/2026 |
| R-13 | Backups com dados sensíveis em local inseguro | Vazamento | Pasta fora do repositório, acesso restrito e criptografia obrigatória (Q-18) |
| R-16 | Perda da chave de criptografia dos backups | Backups irrecuperáveis | Guardar a chave também fora da máquina (gerenciador de senhas); restauração testada com a chave guardada |
| R-17 | KRs em vermelho no início do ciclo serem lidos como problema | Leitura equivocada | A cor mede a distância até a meta (Q-12); a situação informada no check-in aparece junto |
| R-18 | Smart App Control do Windows (ativo nesta máquina) bloqueia DLLs sem reputação: a `cryptography` 50.0.2 foi bloqueada | Atualização de dependência compilada quebra a aplicação localmente | `cryptography` fixada em 50.0.1 (carrega normalmente); antes de atualizar qualquer dependência compilada, verificar se ela carrega nesta máquina. Não desativar a proteção |
| R-14 | Uso do Supabase contornando o Django (cliente no navegador) | Falha de isolamento | Supabase apenas como PostgreSQL; chave `service_role` nunca exposta |
| R-15 | Expansão de escopo (pedidos fora do plano) | Atraso, qualidade | Novas demandas registradas e encaixadas em etapas validadas |

---

## 5. Decisões pendentes

### 5.1. Funcionais

As dúvidas Q-01 a Q-21 foram decididas em 14/10/2026 (ver [Especificação Funcional §11](ESPECIFICACAO_FUNCIONAL.md#11-dúvidas-que-dependem-de-decisão)). Restam:

| Dúvida | Necessária antes de |
|---|---|
| Q-13b (permissões do perfil Usuário), Q-14b (provedor de SSO) | E13 |
| Q-19 (hospedagem; provável teste com Supabase) | E14 |

### 5.2. Técnicas

| ID | Decisão | Recomendação |
|---|---|---|
| DT-01 | Versão do Django | **Decidido:** 5.2 LTS (suporte até abril de 2028) |
| DT-02 | Adoção de HTMX | Somente quando uma interação justificar; servido localmente |
| DT-03 | CI no GitHub Actions (lint + testes com dados fictícios) | **Decidido:** adotar na E1 |
| DT-04 | Como testar em PostgreSQL | CI com serviço PostgreSQL (sem instalar nada localmente); alternativa: projeto Supabase exclusivo de testes |
| DT-05 | Local e criptografia dos backups | **Decidido (Q-18):** `C:\Users\user\Backups\OKR`, criptografia obrigatória, 30 backups |
| DT-06 | Ferramenta de monitoramento de erros em servidor | Decidir na E14 |

---

## 6. Caminho de evolução: local → servidor

| Fase | Banco | Acesso | Autoria | Etapas |
|---|---|---|---|---|
| **1. Local de validação** | SQLite em `var/` | `127.0.0.1`, uma pessoa | Informada (não verificada) | E1–E11 |
| **2. Preparação** | SQLite local + PostgreSQL em testes | Local | Informada | E12 |
| **3. Segurança** | PostgreSQL (testes) | Local, com login | Verificada | E13 |
| **4. Homologação** | PostgreSQL central | Servidor HTTPS, usuários de teste | Verificada | E14 |
| **5. Produção** | PostgreSQL central com backups gerenciados | Usuários do grupo, por empresa | Verificada | Após aprovação |

Pontos já preparados desde a fase 1 para reduzir retrabalho:

- Somente ORM e migrações (troca de banco por `DATABASE_URL`).
- `Usuario` customizado desde a primeira migração.
- `Ator` e `EscopoAcesso` em todos os services e selectors.
- Auditoria com campo de usuário (nulo até a E13).
- Settings separados por ambiente, com `prod.py` validando segurança.
- Dados de empresa sempre filtrados no servidor.

**Nenhum acesso por outros usuários antes da conclusão e validação da E13.**
