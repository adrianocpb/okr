from datetime import date
from decimal import Decimal

import pytest
from django.db import DatabaseError, connection
from django.urls import reverse
from django.utils import formats

from apps.core.selectors import situacao_banco


@pytest.mark.django_db
def test_pagina_inicial_responde_em_portugues(client):
    resposta = client.get(reverse("core:inicio"))

    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert '<html lang="pt-BR">' in html
    assert "Gestão OKR" in html
    assert "Situação do sistema" in html


@pytest.mark.django_db
def test_pagina_inicial_informa_banco_conectado_e_atualizado(client):
    html = client.get(reverse("core:inicio")).content.decode()

    assert "Conectado" in html
    assert "Atualizada" in html


@pytest.mark.django_db
def test_situacao_banco_sem_migracoes_pendentes():
    situacao = situacao_banco()

    assert situacao.conectado is True
    assert situacao.migracoes_pendentes == 0
    assert situacao.motor == "SQLite"


def test_situacao_banco_relata_falha_de_conexao(monkeypatch):
    def falhar():
        raise DatabaseError("banco indisponível")

    monkeypatch.setattr(connection, "ensure_connection", falhar)

    situacao = situacao_banco()

    assert situacao.conectado is False
    assert situacao.migracoes_pendentes is None
    assert "banco indisponível" in situacao.erro


def test_pagina_inicial_mostra_aviso_sem_conexao(client, monkeypatch):
    def falhar():
        raise DatabaseError("banco indisponível")

    monkeypatch.setattr(connection, "ensure_connection", falhar)

    html = client.get(reverse("core:inicio")).content.decode()

    assert "Sem conexão" in html
    assert "Não foi possível conectar ao banco de dados" in html


def test_formatos_brasileiros_de_data_e_numero():
    assert formats.date_format(date(2026, 10, 14), "SHORT_DATE_FORMAT") == "14/10/2026"
    assert formats.number_format(Decimal("1234.5"), 2, force_grouping=True) == "1.234,50"
