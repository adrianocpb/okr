from django.core.exceptions import ValidationError
from django.db import models

from apps.core.models import ModeloArquivavel


class ItemTeste(ModeloArquivavel):
    nome = models.CharField(max_length=100, unique=True)
    valor = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    empresa_id = models.PositiveBigIntegerField(null=True, blank=True)

    def __str__(self):
        return self.nome

    def clean(self):
        if self.valor is not None and self.valor < 0:
            raise ValidationError({"valor": "O valor não pode ser negativo."})
