# Especificação Funcional — Sistema de Gestão de OKRs

> **Status:** proposta para validação (Etapa 0).
> **Data:** 14/10/2026.
> **Documentos relacionados:** [ARQUITETURA.md](ARQUITETURA.md) · [PLANO_IMPLEMENTACAO.md](PLANO_IMPLEMENTACAO.md)

Convenção:

- **[Requisito]**: definido pelo solicitante.
- **[Decisão proposta]**: escolha deste documento para cobrir uma lacuna; depende de validação e está ligada a uma dúvida da seção 11 quando aplicável.
- **(Q-nn)**: referência a uma dúvida pendente.

---

## 1. Objetivo e escopo

### 1.1. Objetivo

Oferecer uma aplicação web para cadastrar, organizar, acompanhar e analisar a evolução dos OKRs (Objectives and Key Results) das empresas de um grupo empresarial, preservando o histórico de acompanhamentos e de alterações.

### 1.2. Escopo da primeira versão (local)

- Execução local na máquina do desenvolvedor, para desenvolvimento, validação funcional e testes.
- Cadastros de empresas, pessoas e ciclos.
- Objetivos, KRs, marcos, iniciativas, check-ins e atualizações de iniciativas.
- Histórico de check-ins e histórico de alterações estruturais (auditoria).
- Dashboard com filtros e alertas **visuais**.
- Backup e restauração do banco.

### 1.3. Fora do escopo desta versão

- Publicação em servidor ou acesso por outros usuários (exige a etapa de segurança; ver seção 9).
- Notificações por e-mail, chat ou outros canais.
- Integração com sistemas externos (ERP, BI, diretório corporativo).
- Importação de planilhas [Decidido em Q-15: não será necessária].
- Aplicativo móvel nativo.

---

## 2. Glossário

| Termo | Definição |
|---|---|
| **Objetivo** | Declaração qualitativa do que se quer alcançar em um ciclo. |
| **Resultado-chave (KR)** | Medida verificável que indica o alcance do objetivo. |
| **Iniciativa** | Ação ou projeto executado para contribuir com um objetivo ou KR. Não mede resultado. |
| **Ciclo** | Período de vigência dos OKRs: anual ou trimestral. |
| **Check-in** | Registro periódico de acompanhamento de um KR (valor, status, comentários). |
| **Atualização de iniciativa** | Registro periódico de acompanhamento da execução de uma iniciativa. |
| **Owner** | Pessoa responsável pela condução do objetivo. |
| **Sponsor** | Pessoa patrocinadora do objetivo, que apoia e remove impedimentos. |
| **Responsável** | Pessoa responsável principal por um KR ou por uma iniciativa. |
| **Linha de base** | Valor inicial de um KR no começo do ciclo. |
| **Arquivamento** | Retirada de um registro do uso ativo sem excluí-lo; o histórico é mantido. |

---

## 3. Requisitos funcionais

### 3.1. Empresas

| ID | Requisito |
|---|---|
| RF-01 | Cadastrar empresa com nome (obrigatório e único, sem distinguir maiúsculas, acentos e espaços repetidos) e sigla/nome curto (obrigatória, única, gravada em maiúsculas). [Decidido em Q-01: somente esses campos] |
| RF-02 | Editar empresa; toda edição gera um registro de auditoria. |
| RF-03 | Arquivar e reativar empresa. Uma empresa arquivada não recebe novos objetivos, mas seus OKRs continuam consultáveis. |
| RF-04 | Consultar os OKRs de uma empresa (por ciclo). |
| RF-05 | Filtrar as listagens e o dashboard por empresa. |
| RF-06 | Nenhuma consulta pode misturar dados de empresas fora do escopo de acesso do usuário (ver seção 9). |

### 3.2. Pessoas

| ID | Requisito |
|---|---|
| RF-07 | Cadastrar pessoa com nome (obrigatório), e-mail (opcional e único quando informado) e empresas às quais está vinculada. Uma pessoa pode estar vinculada a várias empresas do grupo [Decidido em Q-02] e precisa estar vinculada a **ao menos uma** empresa [Decisão de implementação na E3: todas as responsabilidades exigem vínculo (Q-02b), e o isolamento por empresa depende dele]. Empresas arquivadas não recebem novos vínculos; vínculos existentes são mantidos. |
| RF-08 | Editar e arquivar pessoa. Uma pessoa arquivada não pode receber novas responsabilidades, mas continua exibida nos registros históricos. |
| RF-09 | Consultar as responsabilidades de uma pessoa: objetivos como Owner ou Sponsor, KRs e iniciativas como responsável. |
| RF-10 | Pessoa é uma entidade de negócio, independente de conta de acesso. Uma pessoa pode existir sem login; quando houver autenticação, uma conta de usuário poderá ser associada a uma pessoa. |

### 3.3. Ciclos

| ID | Requisito |
|---|---|
| RF-11 | **Cada empresa tem seus próprios ciclos** [Decidido em Q-03]. Cadastrar, por empresa, ciclo **anual** (ano de referência, data de início, data de fim) e **trimestral** (ano, trimestre 1–4, datas). As datas são livres, o que permite ano fiscal diferente do ano civil. Sem datas informadas, o ciclo anual assume o ano civil (01/01 a 31/12) e o trimestre assume o bloco de 3 meses correspondente a partir do início do ano. Ação de apoio: gerar de uma vez os trimestres que faltam (quando o ano começa no dia 1 e dura 12 meses). |
| RF-12 | Um ciclo trimestral é associado a um ciclo anual **da mesma empresa** que o contém; suas datas devem estar dentro das datas do anual. |
| RF-13 | Situação do ciclo: *Planejado*, *Em andamento*, *Encerrado*, **calculada pelas datas** em relação ao dia atual [Decisão de implementação na E4: evita situação manual desatualizada]. Ciclos podem ser arquivados (um ciclo anual só depois de seus trimestres); empresa, tipo e ciclo anual não mudam após a criação, e o ano de um ciclo com trimestres não pode ser alterado. Ciclos encerrados permanecem consultáveis; novos check-ins em ciclo encerrado são permitidos com confirmação explícita e data de referência dentro do ciclo [Decidido em Q-11]. |
| RF-14 | Não é permitido haver, **na mesma empresa**, dois ciclos do mesmo tipo com períodos sobrepostos. Empresas diferentes podem ter ciclos com datas diferentes. |
| RF-15 | Consultar ciclos anteriores com seus OKRs e históricos. |

### 3.4. Objetivos

| ID | Requisito |
|---|---|
| RF-16 | Cadastrar objetivo com: título (obrigatório), descrição, empresa (obrigatória), ciclo (obrigatório, **da mesma empresa**), **Owner** (obrigatório), **Sponsor** (obrigatório) e status. |
| RF-17 | O **período** do objetivo é sempre o período do seu ciclo; o objetivo não tem datas próprias. [Decidido em Q-04] |
| RF-18 | Status do objetivo (ciclo de vida, manual): *Rascunho*, *Ativo*, *Concluído*, *Cancelado*. Cancelar ou concluir exige comentário. |
| RF-19 | Vincular explicitamente um objetivo trimestral a um ou mais objetivos anuais (relação de desdobramento). O vínculo é **opcional**: um objetivo trimestral pode existir sem objetivo anual. |
| RF-20 | Validações do vínculo: o objetivo de origem deve estar em ciclo anual e o de destino em ciclo trimestral contido nele; ambos **obrigatoriamente da mesma empresa** [Decidido em Q-06: não há vínculo entre empresas]; sem vínculos duplicados. |
| RF-21 | A tela do objetivo exibe: dados, KRs com progresso individual, iniciativas, vínculos (anual ↔ trimestrais), histórico de check-ins dos KRs e histórico de alterações. |
| RF-22 | Editar objetivo, com auditoria. A empresa não muda após a criação; o ciclo só pode ser trocado se o objetivo não tiver vínculos. Objetivos não são arquivados: encerram-se pelo status (Concluído ou Cancelado) [Decisão de implementação na E5: evita dois conceitos para o mesmo fim]. A criação começa pela escolha da empresa, para que o formulário ofereça apenas os ciclos e as pessoas dela. |

### 3.5. Resultados-chave (KRs)

| ID | Requisito |
|---|---|
| RF-23 | Cadastrar KR com: título (obrigatório), descrição, objetivo (obrigatório), **responsável principal** (obrigatório), tipo de medição, unidade, direção ou regra, valor inicial, meta e casas decimais, conforme o tipo (ver seção 7). |
| RF-24 | **O KR não possui campos de Owner nem de Sponsor.** |
| RF-25 | O valor atual do KR **não é digitado no cadastro**: é sempre o valor do check-in vigente mais recente (ver seção 8). |
| RF-26 | Status do KR (ciclo de vida, manual): *Ativo*, *Concluído*, *Cancelado*. A **situação de acompanhamento** vem do último check-in (ver 7.3). |
| RF-27 | Frequência de check-in por KR, com padrão **quinzenal (14 dias)** e opções semanal (7), mensal (30) ou personalizada (em dias). |
| RF-28 | Alterações de meta, linha de base, responsável, unidade ou frequência são registradas na auditoria com valores anterior e novo. |
| RF-29 | Não é permitido mudar o tipo de medição de um KR que já tenha check-ins. É preciso cancelar o KR e criar outro, preservando o histórico. [Decisão proposta] |
| RF-30 | KRs **não** têm vínculo direto entre ciclos; a relação anual ↔ trimestral existe apenas entre objetivos. [Decidido em Q-07] |

### 3.6. Iniciativas

| ID | Requisito |
|---|---|
| RF-31 | Cadastrar iniciativa com: título (obrigatório), descrição, **objetivo (obrigatório)**, **KRs para os quais contribui (zero, um ou vários)** [Decidido em Q-08], **responsável principal** (obrigatório), prazo (data prevista) e status. Os KRs vinculados devem ser do mesmo objetivo [Decisão proposta; ver Q-21]. |
| RF-32 | Status: *Não iniciada*, *Em andamento*, *Concluída*, *Cancelada*. A data de conclusão é registrada ao concluir. |
| RF-33 | Registrar **atualizações de execução** (somente inserção): data, status, comentário, dificuldades/impedimentos, próximos passos e autor. |
| RF-34 | Alterações estruturais (prazo, responsável, inclusão ou remoção de KR vinculado, descrição) vão para a auditoria. |
| RF-35 | A iniciativa não altera o progresso do KR. O progresso do KR vem apenas dos check-ins do KR. |

### 3.7. Check-ins

| ID | Requisito |
|---|---|
| RF-36 | Registrar check-in de KR com: data de referência, valor (quando aplicável ao tipo), status informado, comentário, dificuldades/riscos/impedimentos, próximos passos e autor. |
| RF-37 | Check-ins **nunca são editados nem excluídos**. Correções são feitas por um novo check-in de **retificação**, que referencia o original e exige justificativa; o original continua visível, marcado como retificado. |
| RF-38 | O check-in guarda uma **cópia da linha de base e da meta vigentes** no momento do registro, para que o progresso histórico possa ser reproduzido mesmo que a meta mude depois. |
| RF-39 | Sem autenticação, o autor é **selecionado manualmente** entre as pessoas e exibido como "informado, não verificado". Com autenticação, o sistema também registra o usuário autenticado, e só então o autor aparece como verificado. |
| RF-40 | A data/hora de registro é atribuída pelo sistema e não é editável. A data de referência é informada pelo usuário e não pode ser futura. |
| RF-41 | Histórico de check-ins do KR em ordem cronológica, com valores, status, comentários e autor. |

### 3.8. Dashboard, visualizações e alertas

| ID | Requisito |
|---|---|
| RF-42 | Visão consolidada de objetivos e KRs, com filtros combináveis por **empresa**, **ciclo**, **período** e **status/situação**. Como cada empresa tem seus ciclos, o filtro **ciclo** lista os ciclos das empresas selecionadas e o filtro **período** usa intervalo de datas (mostra os ciclos que se sobrepõem ao intervalo), o que permite visões entre empresas mesmo com calendários diferentes. [Decisão proposta; ver Q-20] |
| RF-43 | Cada KR exibe seu progresso **individualmente**, com valor atual, meta e unidade próprios. |
| RF-44 | O agrupamento por objetivo, empresa ou ciclo exibe **contagens por situação** (por exemplo, "3 no ritmo, 1 em risco, 1 sem check-in"), **nunca média ou soma de percentuais** de KRs distintos. Não haverá indicador numérico agregado por objetivo [Decidido em Q-09]. |
| RF-45 | Cada KR exibe uma **cor de progresso** que migra do vermelho ao verde conforme se aproxima da meta (ver 7.5); alertas visuais (ver 7.6) são destacados no dashboard e nas telas de objetivo e KR. [Decidido em Q-12] |
| RF-46 | Gráfico de evolução de cada KR ao longo dos check-ins, com a meta e a linha de base. |
| RF-47 | Comparação entre períodos: o mesmo KR ao longo dos seus check-ins; entre ciclos (por exemplo, um objetivo anual e seus objetivos trimestrais vinculados), os KRs são exibidos **lado a lado**, cada um com sua unidade e progresso, sem cálculo combinado. |
| RF-48 | Identificação dos responsáveis (Owner, Sponsor e responsáveis) nas visões. |
| RF-49 | Acesso ao histórico de check-ins e de alterações a partir das telas de detalhe. |

---

## 4. Requisitos não funcionais

| ID | Requisito |
|---|---|
| RNF-01 | Interface, mensagens de erro e validação inteiramente em **português brasileiro**; datas no formato dd/mm/aaaa e números com vírgula decimal. |
| RNF-02 | Funciona nas versões atuais de Chrome, Edge e Firefox, sem plugins. |
| RNF-03 | Dados persistidos em banco relacional; nada depende apenas da memória do processo ou do armazenamento do navegador. |
| RNF-04 | Banco local SQLite; arquitetura preparada para PostgreSQL (ver Arquitetura §12). |
| RNF-05 | Mudanças de esquema somente por migrações versionadas. |
| RNF-06 | Configurações e segredos por variáveis de ambiente; nenhum segredo no código ou no Git. |
| RNF-07 | Banco de dados, backups e `.env` excluídos do Git. |
| RNF-08 | Toda gravação ocorre em transação; falha em qualquer parte (incluindo auditoria) reverte o conjunto, sem perda silenciosa. |
| RNF-09 | Erros apresentados ao usuário com mensagem compreensível; detalhes técnicos apenas em log. |
| RNF-10 | Edição concorrente protegida por bloqueio otimista (nenhuma alteração sobrescreve outra sem aviso). |
| RNF-11 | Testes automatizados de regras de negócio, persistência e interface (ver Plano §3). |
| RNF-12 | Navegação consistente: menu fixo com Painel, Objetivos, Ciclos, Empresas, Pessoas; layout base único reaproveitado pelos módulos. |
| RNF-13 | Telas de listagem com resposta inferior a 1 s em ambiente local para até 10 empresas [Decidido em Q-16], 2.000 objetivos e 50.000 check-ins (os dois últimos números são margem de segurança proposta). |
| RNF-14 | Acessibilidade básica: rótulos nos campos, contraste adequado e situação não indicada apenas por cor (sempre com texto ou ícone). |

---

## 5. Entidades e relacionamentos

### 5.1. Diagrama conceitual

```
Empresa 1───N Ciclo
Empresa 1───N Objetivo N───1 Ciclo (da mesma empresa)
Ciclo(trimestral) N───1 Ciclo(anual) (da mesma empresa)
Objetivo N───1 Pessoa (Owner)
Objetivo N───1 Pessoa (Sponsor)
Objetivo(anual) N───N Objetivo(trimestral)   via VinculoObjetivo
Objetivo 1───N ResultadoChave N───1 Pessoa (Responsável)
ResultadoChave 1───N Marco
ResultadoChave 1───N CheckIn N───N Marco (marcos concluídos, via CheckInMarco)
CheckIn 0..1───1 CheckIn (retificação → original)
Objetivo 1───N Iniciativa N───N ResultadoChave   via IniciativaKR (zero ou mais KRs)
Iniciativa N───1 Pessoa (Responsável)
Iniciativa 1───N AtualizacaoIniciativa
Pessoa N───N Empresa   via VinculoPessoaEmpresa
Pessoa 0..1───0..1 Usuario   (quando houver autenticação)
RegistroAlteracao N───1 (qualquer entidade auditada)
```

### 5.2. Atributos principais

Todos os registros possuem: `id`, `criado_em`, `atualizado_em`. As entidades editáveis possuem também `versao` (bloqueio otimista) e `arquivado_em` (quando aplicável).

**Empresa**: nome (único), sigla (única), arquivada.

**Pessoa**: nome, e-mail (opcional, único), empresas vinculadas, arquivada, usuário associado (futuro).

**Ciclo**: **empresa**, tipo (ANUAL | TRIMESTRAL), ano, trimestre (1–4, só trimestral), data de início, data de fim, ciclo anual (só trimestral), situação.

**Objetivo**: empresa, ciclo, título, descrição, owner, sponsor, status, comentário de status, arquivado.

**VinculoObjetivo**: objetivo anual, objetivo trimestral, criado em/por. Restrição única no par.

**ResultadoChave (KR)**: objetivo, título, descrição, **responsável**, tipo de medição, unidade, direção/regra, valor inicial, meta, limite inferior/superior (faixa), casas decimais, frequência de check-in (dias, padrão 14), status.

**Marco**: KR, descrição, ordem, prazo (opcional).

**CheckIn**: KR, data de referência, valor (decimal, opcional conforme tipo), valor booleano (binário), status informado, comentário, dificuldades, próximos passos, autor informado (Pessoa), usuário registrador (nulo enquanto não houver login), registrado em (sistema), linha de base vigente, meta vigente, retifica (check-in original, opcional), justificativa de retificação.

**CheckInMarco**: check-in, marco (estado dos marcos concluídos naquele check-in).

**Iniciativa**: objetivo, título, descrição, **responsável**, prazo, status, data de conclusão.

**IniciativaKR**: iniciativa, KR. Restrição única no par; inclusão e remoção auditadas.

**AtualizacaoIniciativa**: iniciativa, data de referência, status, comentário, dificuldades, próximos passos, autor informado, usuário registrador, registrado em.

**RegistroAlteracao**: entidade, id do registro, empresa, ação (CRIAÇÃO, ALTERAÇÃO, ARQUIVAMENTO, REATIVAÇÃO, VÍNCULO, DESVÍNCULO), diferenças `{campo: {antes, depois}}`, ator (descrição e usuário quando houver), data/hora, origem (interface, comando, importação).

---

## 6. Regras de responsabilidade

| Entidade | Campos de responsabilidade | Obrigatoriedade | Proibido |
|---|---|---|---|
| **Objetivo** | **Owner** e **Sponsor** | Ambos obrigatórios | — |
| **KR** | **Responsável principal** (um único) | Obrigatório | Campos Owner ou Sponsor |
| **Iniciativa** | **Responsável principal** (um único) | Obrigatório | Campos Owner ou Sponsor |

Regras complementares:

1. A mesma pessoa pode ter papéis diferentes em objetivos, KRs e iniciativas distintos (por exemplo, Owner de um objetivo, Sponsor de outro e responsável por KRs de um terceiro).
2. Somente pessoas **ativas** podem ser atribuídas a novas responsabilidades.
3. Owner e Sponsor do mesmo objetivo **podem ser a mesma pessoa**; nesse caso a tela exibe um aviso. [Decidido em Q-05]
4. Uma pessoa pode estar vinculada a várias empresas do grupo [Decidido em Q-02]. Para ser Owner, Sponsor ou responsável, a pessoa **precisa estar vinculada à empresa do objetivo**. [Decidido em Q-02b]
5. Toda troca de Owner, Sponsor ou responsável é registrada na auditoria.
6. Arquivar uma pessoa não remove suas responsabilidades atuais; o sistema gera um alerta "responsável inativo" (ver 7.6).

---

## 7. Regras de cálculo de progresso

### 7.1. Tipos de medição

| Tipo | Uso | Campos | Direção/regra |
|---|---|---|---|
| **NUMÉRICO** | Valores absolutos (clientes, R$, dias, unidades) **e percentuais como métrica** (por exemplo, margem de 12% → 15%) | linha de base, meta, unidade, casas decimais | CRESCENTE ou DECRESCENTE |
| **MANUTENÇÃO** (valor-alvo) | Manter um indicador em um patamar (por exemplo, NPS ≥ 70; prazo ≤ 5 dias; estoque entre 10 e 20) | limite(s), unidade | MANTER ≥, MANTER ≤ ou MANTER ENTRE |
| **BINÁRIO** | Entrega única sim/não (por exemplo, "certificação obtida") | — | — |
| **MARCOS** | Etapas de conclusão (por exemplo, 5 etapas de um projeto) | lista de marcos ordenados | — |

A unidade é texto livre curto (por exemplo, "R$", "%", "clientes", "dias"). Moeda é tratada como unidade; conversão entre moedas não está no escopo.

### 7.2. Fórmulas

**NUMÉRICO (CRESCENTE ou DECRESCENTE)**

```
progresso = (valor_atual − linha_de_base) / (meta − linha_de_base) × 100
```

- CRESCENTE exige `meta > linha_de_base`; DECRESCENTE exige `meta < linha_de_base`. A mesma fórmula atende os dois sentidos.
- `meta = linha_de_base` é inválido (divisão por zero e meta sem significado).
- O valor calculado **é preservado sem truncar**: pode ser negativo (regressão) ou maior que 100% (superação). A barra visual é limitada a 0–100%, mas o número exibido é o real.
- Exemplos: vendas 100 → 150, atual 125 ⇒ 50%. Prazo 10 → 6 dias, atual 8 ⇒ 50%. Margem 12% → 15%, atual 13,5% ⇒ **50% de progresso**, e não "13,5%".
- **Limitação:** pressupõe que a evolução é linear em relação ao esforço; métricas sazonais ou com teto natural podem distorcer a leitura.

**MANUTENÇÃO**

- Resultado por check-in: **Dentro** ou **Fora** do limite, sem percentual de progresso.
- **Limitação:** não indica "quão perto" do limite, apenas o atendimento. A distância ao limite é exibida como informação ("2,0 pontos abaixo do mínimo"), sem virar percentual.

**BINÁRIO**

- 0% (não concluído) ou 100% (concluído).
- **Limitação:** não mostra avanço parcial. Para isso, recomenda-se o tipo MARCOS ou o acompanhamento via iniciativas.

**MARCOS**

```
progresso = marcos_concluídos / total_de_marcos × 100
```

- Todos os marcos têm o mesmo peso. [Decidido em Q-10]
- **Limitação:** etapas de esforço desigual tornam o percentual apenas indicativo.

### 7.3. Situação de acompanhamento

- A **situação** de um KR é o **status informado no último check-in vigente**: *No ritmo*, *Atenção*, *Em risco*, *Concluído*. Sem check-in, a situação é *Sem check-in*.
- Não há cálculo de "ritmo esperado" nem alerta de tolerância [Decidido em Q-12]. A leitura visual do avanço é feita pela cor de progresso (7.5).

### 7.4. Agregação

- **Não se somam nem se tiram médias de percentuais de KRs diferentes.** Em objetivos, empresas e ciclos, o sistema apresenta:
  - a distribuição de KRs por situação;
  - a **situação mais crítica** entre os KRs ativos (ordem: Em risco > Atenção > Sem check-in > No ritmo > Concluído) como sinalizador de atenção do objetivo.
- **Não haverá indicador numérico agregado por objetivo** [Decidido em Q-09]. Uma eventual inclusão futura exigiria nova especificação.

### 7.5. Escala visual de progresso (cores) [Decidido em Q-12]

Cada KR exibe uma cor que **migra do vermelho ao verde** à medida que o valor se aproxima da meta. A cor é calculada sobre o progresso de 7.2, limitado à faixa de 0% a 100%:

| Progresso | Cor |
|---|---|
| 0% (ou negativo) | Vermelho |
| 50% | Laranja/amarelo |
| 90% ou mais (inclusive acima de 100%) | Verde |

- Entre esses pontos, a cor é **interpolada de forma contínua** (por exemplo, 10% fica vermelho e 70% fica entre amarelo e verde). Exemplo do solicitante: meta 100, valor 10 em vermelho, 50 em laranja/amarelo e de 90 a 100 em verde. [Pontos de referência derivados desse exemplo; ajustáveis em configuração; ver Q-22]
- **NUMÉRICO e MARCOS:** usam a escala acima.
- **BINÁRIO:** vermelho enquanto não concluído; verde quando concluído.
- **MANUTENÇÃO:** verde se dentro do limite; vermelho se fora.
- **Sem check-in:** cinza (sem cor de progresso). [Decisão proposta]
- A cor **sempre acompanha o número** (por exemplo, "50%" ou "Dentro do limite"); nunca é a única informação (RNF-14).
- Objetivos **não** recebem cor agregada (Q-09); a tela do objetivo mostra a cor de cada KR.

### 7.6. Alertas visuais

| Alerta | Condição |
|---|---|
| Check-in atrasado | Hoje > (data do último check-in, ou início do ciclo se não houver nenhum) + frequência do KR |
| KR em risco / atenção | Situação do último check-in |
| Fora do limite | KR de MANUTENÇÃO com último check-in "Fora" |
| Iniciativa atrasada | Prazo vencido e status diferente de Concluída/Cancelada |
| Objetivo sem KR | Objetivo *Ativo* sem nenhum KR ativo |
| Responsável inativo | Owner, Sponsor ou responsável arquivado |

Os alertas são apenas visuais; nenhuma notificação é enviada.

---

## 8. Regras de acompanhamento e histórico

1. **Dois históricos separados:**
   - **Histórico de acompanhamento**: check-ins de KRs e atualizações de iniciativas. Somente inserção.
   - **Histórico de alterações estruturais**: auditoria de criação, edição, arquivamento e vínculos (responsáveis, metas, prazos, descrições, status).
2. Nenhum registro de acompanhamento é editado ou excluído. Correções são feitas por retificação (RF-37).
3. O **check-in vigente** de um KR é o de data de referência mais recente; em empate, o registrado por último. Um check-in retificado é substituído pela sua retificação.
4. Mais de um check-in na mesma data de referência é permitido (por exemplo, retificações ou atualizações no mesmo dia) e todos aparecem no histórico.
5. Check-ins fora da frequência padrão são permitidos (flexibilidade); a frequência serve apenas para o alerta de atraso.
6. Entidades com histórico não são excluídas fisicamente; são arquivadas.
7. A auditoria registra o valor anterior e o novo de cada campo alterado, o ator e a data/hora, na mesma transação da alteração.
8. O histórico de ciclos encerrados permanece consultável e não é alterado pelo encerramento.

---

## 9. Requisitos de segurança

### 9.1. Versão local

- Execução apenas em `127.0.0.1`.
- O autor dos registros é declarado, não verificado, e a interface deixa isso explícito.
- Proteções padrão do framework ativas (CSRF, escape de saída, consultas parametrizadas).
- Banco, backups e `.env` fora do Git.

### 9.2. Obrigatório antes de liberar acesso a outros usuários

| ID | Requisito |
|---|---|
| RS-01 | Login individual (sem contas compartilhadas). |
| RS-02 | Autorização por papéis e permissões. Dois perfis [Decidido em Q-13]: **Administrador** (acesso total, incluindo cadastros e usuários) e **Usuário** (acesso somente às empresas autorizadas; permissões detalhadas pendentes em Q-13b). |
| RS-03 | Controle de acesso por empresa aplicado no servidor: o usuário só vê e altera dados das empresas autorizadas. |
| RS-04 | Todas as rotas de dados exigem autenticação; operações de escrita verificam permissão no servidor. |
| RS-05 | Auditoria registra o usuário autenticado. |
| RS-06 | Sessões seguras (HTTPS, cookies `Secure`/`HttpOnly`/`SameSite`, expiração, logout). |
| RS-07 | Login por **conta corporativa** (SSO), em versão futura [Decidido em Q-14]; provedor (Microsoft ou Google) pendente em Q-14b. |
| RS-08 | Testes automatizados de acesso indevido entre empresas. |
| RS-09 | Revisão de segurança e `check --deploy` antes da publicação. |

Ocultar botões ou menus **não** é considerado controle de acesso.

---

## 10. Premissas e limitações

**Premissas**

- P-01: Cada empresa define seus ciclos, que podem seguir calendários diferentes (por exemplo, ano fiscal); por isso, comparações entre empresas usam datas, não o rótulo "1º trimestre" (Q-03 decidida; ver Q-20).
- P-02: Na fase local, um único desenvolvedor/validador usa o sistema por vez.
- P-03: Os dados digitados durante a validação local podem ser reais; por isso o banco e os backups nunca vão ao Git.
- P-04: Valores monetários são em uma única moeda por KR, sem conversão.

**Limitações conhecidas**

- L-01: Sem login na versão local, a autoria dos registros não é verificável.
- L-02: O SQLite não é adequado a escrita concorrente de muitos usuários; serve apenas para a versão local.
- L-03: Busca textual com acentos e sem distinção de maiúsculas é limitada no SQLite.
- L-04: Percentuais de progresso de tipos diferentes não são comparáveis entre si (ver 7.4).
- L-05: A cor de progresso mede a distância até a meta, não o ritmo no tempo. No início do ciclo, é esperado que a maioria dos KRs apareça em vermelho.

---

## 11. Dúvidas que dependem de decisão

### 11.1. Decididas (14/10/2026)

| ID | Dúvida | Decisão |
|---|---|---|
| Q-01 | Dados de empresa além de nome e sigla? | Somente nome e sigla. |
| Q-02 | Uma pessoa pode pertencer a várias empresas? | Sim. |
| Q-02b | Owner, Sponsor e responsável precisam estar vinculados à empresa do objetivo? | Sim. |
| Q-03 | Ciclos únicos para o grupo ou por empresa? | Cada empresa tem os seus. |
| Q-04 | O período do objetivo pode ter datas próprias? | Não; é sempre o do ciclo. |
| Q-05 | Owner e Sponsor podem ser a mesma pessoa? | Sim, com aviso na tela. |
| Q-06 | Vínculo entre objetivos de empresas diferentes? | Não. |
| Q-07 | Vínculo anual ↔ trimestral entre KRs? | Não; somente entre objetivos. |
| Q-08 | Iniciativa pode contribuir para mais de um KR? | Sim. |
| Q-09 | Indicador numérico agregado por objetivo? | Não haverá. |
| Q-10 | Marcos com pesos diferentes? | Não; pesos iguais. |
| Q-11 | Check-in após o encerramento do ciclo? | Sim, com confirmação e data de referência dentro do ciclo. |
| Q-12 | Tolerâncias de alerta de ritmo e de fim de ciclo? | Sem alertas específicos; cor de progresso do vermelho ao verde (7.5). |
| Q-13 | Perfis de acesso? | Administrador e Usuário. |
| Q-14 | Login próprio ou conta corporativa? | Conta corporativa (SSO), em versão futura. |
| Q-15 | Importar planilhas antigas? | Não. |
| Q-16 | Volume esperado? | Até 10 empresas. |
| Q-17 | Escala de confiança no check-in? | Não incluir. |
| Q-18 | Backups: local, criptografia, retenção e recuperação? | Pasta `C:\Users\user\Backups\OKR` (definida no `.env` e criada ao implementar o backup); criptografia obrigatória para backups com dados reais; últimos 30 backups diários, ajustável; restauração documentada e testada. |
| Q-19 | Hospedagem futura? | Provável teste com Supabase (PostgreSQL); decisão futura. |
| Q-20 | Filtro de período com várias empresas? | Por intervalo de datas, mostrando os ciclos que se sobrepõem a ele. |
| Q-21 | KRs de uma iniciativa podem ser de outros objetivos? | Não; do mesmo objetivo. |

### 11.2. Pendentes (não bloqueiam as próximas etapas)

| ID | Dúvida | Proposta atual | Necessária antes de |
|---|---|---|---|
| Q-22 | Os pontos de referência da escala de cores (0% vermelho, 50% laranja/amarelo, 90% verde) atendem? | Sim, ajustáveis em configuração. | E6 |
| Q-13b | O que o perfil **Usuário** pode fazer? Criar objetivos e KRs e alterar metas, ou apenas registrar check-ins e atualizações? | Registrar check-ins e atualizações de iniciativas e consultar, nas empresas autorizadas; cadastros estruturais e metas ficam com o Administrador. | E13 |
| Q-14b | Qual provedor corporativo (Microsoft Entra ID ou Google Workspace)? Haverá conta administrativa local de contingência? | Decidir antes da E13. | E13 |
