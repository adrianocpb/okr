# Publicar no Fly.io

O sistema roda em uma máquina pequena em São Paulo (`gru`), com o banco SQLite num
disco permanente (`/data`). Endereço: <https://gestao-okr.fly.dev>.

- **Acesso:** login por e-mail e senha. Todas as telas exigem login, menos a
  verificação de saúde (`/saude/`). Após 5 tentativas erradas, o e-mail ou o
  endereço de origem fica bloqueado por 15 minutos.
- **Contas:** o Administrador cria as contas no menu **Usuários**. O sistema gera
  uma senha temporária, mostrada uma vez, e pede uma senha nova no primeiro acesso.
- **Custo:** a máquina desliga sozinha sem uso e liga no primeiro acesso (alguns
  segundos de espera). O disco de 1 GB é cobrado mesmo com a máquina desligada.
- **Cópias do disco:** o Fly.io tira uma cópia (snapshot) do disco por dia e guarda
  por 5 dias. Backup próprio, fora do Fly.io, fica para depois do protótipo.

## Primeira publicação (uma vez)

Na pasta do projeto, no cmd:

```bat
fly apps create gestao-okr
fly volumes create dados_okr --region gru --size 1 --app gestao-okr --yes
fly secrets set DJANGO_SECRET_KEY=<chave aleatória de 50+ caracteres> --app gestao-okr --stage
fly deploy
```

Para gerar a chave: `.venv\Scripts\python -c "import secrets; print(secrets.token_urlsafe(64))"`.

Depois, crie a conta do primeiro Administrador (a senha temporária aparece no terminal):

```bat
fly ssh console --app gestao-okr -C "/app/scripts/gerenciar.sh criar_administrador --email voce@empresa.com --nome 'Seu Nome'"
```

## Atualizar o sistema publicado

Depois de testar localmente e fazer o commit:

```bat
fly deploy
```

As migrações rodam sozinhas a cada início (`scripts/iniciar_servidor.sh`). Os dados
do disco permanente não são apagados.

## Comandos úteis

| Para | Comando |
|---|---|
| Ver se está no ar | `fly status --app gestao-okr` |
| Ver os registros (logs) | `fly logs --app gestao-okr` |
| Abrir um terminal no servidor | `fly ssh console --app gestao-okr` |
| Ver as cópias do disco | `fly volumes snapshots list <id do volume>` (o id aparece em `fly volumes list`) |
