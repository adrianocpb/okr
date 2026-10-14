"""Utilitários de datas."""

import calendar
from datetime import date, timedelta


def somar_meses(data: date, meses: int) -> date:
    """Soma meses mantendo o dia (limitado ao último dia do mês de destino)."""
    indice = data.month - 1 + meses
    ano, mes = data.year + indice // 12, indice % 12 + 1
    return date(ano, mes, min(data.day, calendar.monthrange(ano, mes)[1]))


def fim_do_periodo(inicio: date, meses: int) -> date:
    """Último dia de um período de `meses` meses que começa em `inicio`."""
    return somar_meses(inicio, meses) - timedelta(days=1)
