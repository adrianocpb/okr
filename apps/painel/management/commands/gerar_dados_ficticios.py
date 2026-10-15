"""Gera massa de dados fictícios para medir desempenho e demonstrar o sistema.

Só roda em banco sem empresas cadastradas, para nunca misturar dados fictícios com
dados reais. Grava em lote, sem passar pelos services (não gera auditoria): use
apenas em bancos de teste ou demonstração.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.acompanhamento.models import CheckIn
from apps.cadastros.models import Ciclo, Empresa, Pessoa, VinculoPessoaEmpresa
from apps.core.datas import fim_do_periodo, somar_meses
from apps.core.texto import chave_busca
from apps.okrs.models import Iniciativa, Objetivo, ResultadoChave

STATUS = ["no_ritmo", "no_ritmo", "atencao", "em_risco", "concluido"]


class Command(BaseCommand):
    help = "Gera dados fictícios (empresas, pessoas, ciclos, objetivos, KRs e check-ins)."

    def add_arguments(self, parser):
        parser.add_argument("--empresas", type=int, default=10)
        parser.add_argument("--objetivos", type=int, default=2000)
        parser.add_argument("--krs-por-objetivo", type=int, default=3)
        parser.add_argument("--checkins", type=int, default=50000)
        parser.add_argument("--semente", type=int, default=42)
        parser.add_argument(
            "--confirmar",
            action="store_true",
            help="Confirma a geração (obrigatório).",
        )

    def handle(self, *args, **opcoes):
        if not opcoes["confirmar"]:
            raise CommandError("Use --confirmar para gerar os dados fictícios.")
        if Empresa.objects.exists():
            raise CommandError(
                "O banco já tem empresas cadastradas. Gere dados fictícios apenas em um banco "
                "vazio (por exemplo, apontando DATABASE_URL para outro arquivo)."
            )
        aleatorio = random.Random(opcoes["semente"])
        hoje = timezone.localdate()
        with transaction.atomic():
            totais = self._gerar(aleatorio, hoje, opcoes)
        self.stdout.write(
            self.style.SUCCESS(
                "Dados fictícios gerados: "
                + ", ".join(f"{quantidade} {nome}" for nome, quantidade in totais.items())
            )
        )

    def _gerar(self, aleatorio, hoje: date, opcoes) -> dict:
        empresas = Empresa.objects.bulk_create(
            Empresa(
                nome=f"Empresa Fictícia {n:02d}",
                sigla=f"EF{n:02d}",
                chave_nome=chave_busca(f"Empresa Ficticia {n:02d}"),
            )
            for n in range(1, opcoes["empresas"] + 1)
        )
        pessoas_por_empresa = {}
        for empresa in empresas:
            pessoas = Pessoa.objects.bulk_create(
                Pessoa(
                    nome=f"Pessoa {empresa.sigla}-{n}",
                    chave_nome=chave_busca(f"Pessoa {empresa.sigla}-{n}"),
                )
                for n in range(1, 6)
            )
            VinculoPessoaEmpresa.objects.bulk_create(
                VinculoPessoaEmpresa(pessoa=pessoa, empresa=empresa) for pessoa in pessoas
            )
            pessoas_por_empresa[empresa.pk] = pessoas

        ciclos_por_empresa = {}
        inicio_ano = date(hoje.year, 1, 1)
        for empresa in empresas:
            anual = Ciclo.objects.create(
                empresa=empresa,
                tipo="anual",
                ano=hoje.year,
                data_inicio=inicio_ano,
                data_fim=date(hoje.year, 12, 31),
            )
            trimestres = [
                Ciclo.objects.create(
                    empresa=empresa,
                    tipo="trimestral",
                    ano=hoje.year,
                    trimestre=t,
                    ciclo_anual=anual,
                    data_inicio=somar_meses(inicio_ano, 3 * (t - 1)),
                    data_fim=fim_do_periodo(somar_meses(inicio_ano, 3 * (t - 1)), 3),
                )
                for t in range(1, 5)
            ]
            ciclos_por_empresa[empresa.pk] = [anual, *trimestres]

        objetivos = []
        for n in range(opcoes["objetivos"]):
            empresa = empresas[n % len(empresas)]
            pessoas = pessoas_por_empresa[empresa.pk]
            titulo = f"Objetivo fictício {n + 1}"
            objetivos.append(
                Objetivo(
                    empresa=empresa,
                    ciclo=aleatorio.choice(ciclos_por_empresa[empresa.pk]),
                    titulo=titulo,
                    chave_titulo=chave_busca(titulo),
                    owner=aleatorio.choice(pessoas),
                    sponsor=aleatorio.choice(pessoas),
                    status="ativo",
                )
            )
        objetivos = Objetivo.objects.bulk_create(objetivos, batch_size=500)

        krs = []
        for objetivo in objetivos:
            for k in range(opcoes["krs_por_objetivo"]):
                titulo = f"KR {k + 1} do {objetivo.titulo}"
                base = {
                    "objetivo": objetivo,
                    "titulo": titulo,
                    "chave_titulo": chave_busca(titulo),
                    "responsavel": aleatorio.choice(pessoas_por_empresa[objetivo.empresa_id]),
                }
                if k % 3 == 2:
                    krs.append(
                        ResultadoChave(
                            **base,
                            tipo_medicao="manutencao",
                            regra="manter_acima",
                            unidade="pontos",
                            limite_inferior=Decimal(70),
                        )
                    )
                else:
                    krs.append(
                        ResultadoChave(
                            **base,
                            tipo_medicao="numerico",
                            regra="crescente",
                            unidade="clientes",
                            valor_inicial=Decimal(100),
                            meta=Decimal(200),
                        )
                    )
        krs = ResultadoChave.objects.bulk_create(krs, batch_size=1000)
        objetivo_por_id = {o.pk: o for o in objetivos}

        checkins = []
        for n in range(opcoes["checkins"]):
            kr = krs[n % len(krs)]
            ciclo = objetivo_por_id[kr.objetivo_id].ciclo
            limite = min(hoje, ciclo.data_fim)
            if limite < ciclo.data_inicio:
                continue  # ciclo futuro: sem check-ins
            dias = (limite - ciclo.data_inicio).days
            checkins.append(
                CheckIn(
                    kr=kr,
                    data_referencia=ciclo.data_inicio + timedelta(days=aleatorio.randint(0, dias)),
                    valor=Decimal(aleatorio.randint(60, 220)),
                    status_informado=aleatorio.choice(STATUS),
                    autor_informado=kr.responsavel,
                    tipo_medicao_vigente=kr.tipo_medicao,
                    regra_vigente=kr.regra,
                    valor_inicial_vigente=kr.valor_inicial,
                    meta_vigente=kr.meta,
                    limite_inferior_vigente=kr.limite_inferior,
                )
            )
        CheckIn.objects.bulk_create(checkins, batch_size=2000)

        iniciativas = [
            Iniciativa(
                objetivo=objetivo,
                titulo=f"Iniciativa do {objetivo.titulo}",
                chave_titulo=chave_busca(f"Iniciativa do {objetivo.titulo}"),
                responsavel=objetivo.owner,
                prazo=hoje + timedelta(days=aleatorio.randint(-30, 60)),
                status="em_andamento",
            )
            for objetivo in objetivos
        ]
        Iniciativa.objects.bulk_create(iniciativas, batch_size=1000)
        return {
            "empresas": len(empresas),
            "objetivos": len(objetivos),
            "KRs": len(krs),
            "check-ins": len(checkins),
            "iniciativas": len(iniciativas),
        }
