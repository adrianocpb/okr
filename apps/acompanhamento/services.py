"""Registro de check-ins (somente inserção) e retificações."""

from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.acompanhamento.models import AtualizacaoIniciativa, CheckIn, CheckInMarco
from apps.cadastros.models import Pessoa
from apps.core import services as core_services
from apps.core.acesso import Ator, EscopoAcesso
from apps.core.erros import ErroDeNegocio
from apps.okrs import selectors as okrs
from apps.okrs.models import Iniciativa, Objetivo, ResultadoChave, problema_do_responsavel

Tipo = ResultadoChave.TipoMedicao


def _validar(kr: ResultadoChave, dados: dict, hoje: date) -> None:
    objetivo, ciclo = kr.objetivo, kr.objetivo.ciclo
    if kr.status == ResultadoChave.Status.CANCELADO:
        raise ErroDeNegocio("KR cancelado não recebe check-ins.")
    if objetivo.status == Objetivo.Status.CANCELADO:
        raise ErroDeNegocio("Objetivo cancelado não recebe check-ins.")
    if kr.tipo_medicao == Tipo.MARCOS and not kr.marcos.exists():
        raise ErroDeNegocio("Cadastre os marcos do KR antes de registrar check-ins.")

    erros = {}
    data_referencia = dados.get("data_referencia")
    if data_referencia is None:
        erros["data_referencia"] = "Informe a data de referência."
    elif data_referencia > hoje:
        erros["data_referencia"] = "A data de referência não pode ser futura."
    elif data_referencia < ciclo.data_inicio:
        erros["data_referencia"] = (
            f"A data de referência é anterior ao início do ciclo ({ciclo.periodo})."
        )
    elif data_referencia > ciclo.data_fim:
        erros["data_referencia"] = (
            f"A data de referência deve estar dentro do ciclo ({ciclo.periodo})."
        )
    if hoje > ciclo.data_fim and not dados.get("confirmar_ciclo_encerrado"):
        erros["confirmar_ciclo_encerrado"] = (
            f"O ciclo terminou em {ciclo.data_fim:%d/%m/%Y}. "
            "Confirme para registrar um check-in de fechamento."
        )

    autor = dados.get("autor_informado")
    if autor is None:
        erros["autor_informado"] = "Informe quem está registrando o check-in."
    else:
        problema = problema_do_responsavel(autor, objetivo.empresa_id)
        if problema:
            erros["autor_informado"] = problema

    if dados.get("status_informado") not in CheckIn.Status.values:
        erros["status_informado"] = "Escolha o status do check-in."

    if kr.tipo_medicao in (Tipo.NUMERICO, Tipo.MANUTENCAO) and dados.get("valor") is None:
        erros["valor"] = "Informe o valor medido."
    if kr.tipo_medicao == Tipo.BINARIO and dados.get("concluido") is None:
        erros["concluido"] = "Informe se foi concluído."
    if kr.tipo_medicao == Tipo.MARCOS:
        ids = set(dados.get("marcos_ids") or [])
        if not ids <= set(kr.marcos.values_list("pk", flat=True)):
            erros["marcos"] = "Selecione apenas marcos deste KR."
    if erros:
        raise ValidationError(erros)


def _gravar(kr: ResultadoChave, dados: dict, ator: Ator, retifica: CheckIn | None) -> CheckIn:
    tipo = kr.tipo_medicao
    checkin = CheckIn(
        kr=kr,
        data_referencia=dados["data_referencia"],
        valor=dados.get("valor") if tipo in (Tipo.NUMERICO, Tipo.MANUTENCAO) else None,
        concluido=dados.get("concluido") if tipo == Tipo.BINARIO else None,
        status_informado=dados["status_informado"],
        comentario=(dados.get("comentario") or "").strip(),
        dificuldades=(dados.get("dificuldades") or "").strip(),
        proximos_passos=(dados.get("proximos_passos") or "").strip(),
        autor_informado=dados["autor_informado"],
        registrado_por_id=ator.usuario_id,
        tipo_medicao_vigente=tipo,
        regra_vigente=kr.regra,
        valor_inicial_vigente=kr.valor_inicial,
        meta_vigente=kr.meta,
        limite_inferior_vigente=kr.limite_inferior,
        limite_superior_vigente=kr.limite_superior,
        total_marcos_vigente=kr.marcos.count() if tipo == Tipo.MARCOS else None,
        retifica=retifica,
        justificativa_retificacao=(dados.get("justificativa_retificacao") or "").strip(),
    )
    try:
        with transaction.atomic():
            checkin.save()
            if tipo == Tipo.MARCOS:
                for marco_id in sorted(set(dados.get("marcos_ids") or [])):
                    CheckInMarco.objects.create(checkin=checkin, marco_id=marco_id)
    except IntegrityError as exc:
        raise ErroDeNegocio("Este check-in já foi retificado por outra pessoa.") from exc
    return checkin


def _resolver_autor(dados: dict) -> dict:
    dados = dict(dados)
    if isinstance(dados.get("autor_informado"), int):
        dados["autor_informado"] = Pessoa.objects.get(pk=dados["autor_informado"])
    return dados


def registrar_checkin(
    *, kr_id: int, dados: dict, ator: Ator, escopo: EscopoAcesso, hoje: date | None = None
) -> CheckIn:
    kr = okrs.obter_kr(escopo, kr_id)
    dados = _resolver_autor(dados)
    _validar(kr, dados, hoje or timezone.localdate())
    return _gravar(kr, dados, ator, retifica=None)


def retificar_checkin(
    checkin_id: int, *, dados: dict, ator: Ator, escopo: EscopoAcesso, hoje: date | None = None
) -> CheckIn:
    """Cria um novo check-in que corrige o original. O original permanece no histórico."""
    original = CheckIn.objects.select_related("kr").filter(pk=checkin_id).first()
    if original is None:
        raise ErroDeNegocio("Check-in não encontrado.")
    kr = okrs.obter_kr(escopo, original.kr_id)
    if original.retificado:
        raise ErroDeNegocio("Este check-in já foi retificado. Retifique a versão mais recente.")
    dados = _resolver_autor(dados)
    # A retificação substitui o original na mesma data de referência.
    dados["data_referencia"] = original.data_referencia
    if not (dados.get("justificativa_retificacao") or "").strip():
        raise ValidationError({"justificativa_retificacao": "Informe o motivo da retificação."})
    _validar(kr, dados, hoje or timezone.localdate())
    return _gravar(kr, dados, ator, retifica=original)


# ------------------------------------------------- execução de iniciativas


@transaction.atomic
def registrar_atualizacao(
    *,
    iniciativa_id: int,
    dados: dict,
    ator: Ator,
    escopo: EscopoAcesso,
    hoje: date | None = None,
) -> AtualizacaoIniciativa:
    """Registra o acompanhamento da execução. O status informado passa a ser o
    status da iniciativa (com registro no histórico de alterações)."""
    hoje = hoje or timezone.localdate()
    iniciativa = okrs.obter_iniciativa(escopo, iniciativa_id)
    if iniciativa.status == Iniciativa.Status.CANCELADA:
        raise ErroDeNegocio("Iniciativa cancelada não recebe atualizações.")
    dados = _resolver_autor(dados)

    erros = {}
    data_referencia = dados.get("data_referencia")
    if data_referencia is None:
        erros["data_referencia"] = "Informe a data de referência."
    elif data_referencia > hoje:
        erros["data_referencia"] = "A data de referência não pode ser futura."
    if dados.get("status") not in Iniciativa.Status.values:
        erros["status"] = "Escolha o status da iniciativa."
    autor = dados.get("autor_informado")
    if autor is None:
        erros["autor_informado"] = "Informe quem está registrando a atualização."
    else:
        problema = problema_do_responsavel(autor, iniciativa.objetivo.empresa_id)
        if problema:
            erros["autor_informado"] = problema
    if erros:
        raise ValidationError(erros)

    atualizacao = AtualizacaoIniciativa.objects.create(
        iniciativa=iniciativa,
        data_referencia=data_referencia,
        status=dados["status"],
        comentario=(dados.get("comentario") or "").strip(),
        dificuldades=(dados.get("dificuldades") or "").strip(),
        proximos_passos=(dados.get("proximos_passos") or "").strip(),
        autor_informado=autor,
        registrado_por_id=ator.usuario_id,
    )
    if iniciativa.status != dados["status"]:
        core_services.atualizar(
            iniciativa, {"status": dados["status"]}, versao_esperada=iniciativa.versao, ator=ator
        )
    return atualizacao
