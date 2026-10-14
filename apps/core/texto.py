"""Normalização de textos para comparação e busca.

A busca sem distinção de maiúsculas e acentos é feita sobre uma chave
normalizada gravada no próprio registro. Isso funciona igual no SQLite e no
PostgreSQL (o `LIKE` do SQLite só ignora maiúsculas em letras sem acento).
"""

import re
import unicodedata


def espacos_simples(texto: str) -> str:
    return re.sub(r"\s+", " ", texto or "").strip()


def chave_busca(texto: str) -> str:
    """'  Água   Viva ' → 'agua viva'."""
    decomposto = unicodedata.normalize("NFKD", espacos_simples(texto))
    sem_acentos = "".join(c for c in decomposto if not unicodedata.combining(c))
    return sem_acentos.casefold()
