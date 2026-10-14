# OKR — Gestão e acompanhamento de OKRs do grupo

Aplicação web para cadastro, acompanhamento e análise de OKRs (Objectives and Key Results) de múltiplas empresas de um grupo empresarial.

> **Situação atual:** Etapa 0 (arquitetura e planejamento). Ainda não há código executável.
> As instruções de instalação e execução serão adicionadas na Etapa 1.

## Documentação

- [Especificação Funcional](docs/ESPECIFICACAO_FUNCIONAL.md): escopo, requisitos, entidades, regras de responsabilidade, cálculo de progresso e dúvidas pendentes.
- [Arquitetura](docs/ARQUITETURA.md): stack, camadas, pastas, persistência, segurança, backup, migração para PostgreSQL e implantação futura.
- [Plano de Implementação](docs/PLANO_IMPLEMENTACAO.md): etapas, critérios de aceite, testes e riscos.

## Proteção de dados

Este repositório contém **somente código e documentação**. Bancos de dados, backups, arquivos `.env` e exportações com dados empresariais são excluídos pelo [.gitignore](.gitignore) e nunca devem ser versionados.
