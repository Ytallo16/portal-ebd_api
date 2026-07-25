import math
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import TruncMonth
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from classrooms.models import ClassGroup
from core.permissions import module_permission
from core.scoping import get_teaching_class_ids, is_campo_organization, is_somente_professor
from core.tenant import get_user_organization, resolve_active_organization
from core.viewmixins import DashboardOrganizationMixin
from finance.models import Offering

FINANCE_LANCAMENTOS_PAGE_SIZE_DEFAULT = 5


class FinanceResumoMixin(DashboardOrganizationMixin):
    request = None

    def __init__(self, request):
        self.request = request


def _org_ids(request):
    return FinanceResumoMixin(request).get_dashboard_organization_ids()


def _class_ids_filter(request):
    try:
        active_org = resolve_active_organization(request, required=False)
    except Exception:
        return None
    if active_org and is_somente_professor(request.user, active_org):
        return get_teaching_class_ids(request.user, active_org)
    return None


def _base_offerings_queryset(request):
    org_ids = _org_ids(request)
    queryset = Offering.objects.filter(organization_id__in=org_ids, is_active=True).select_related(
        'organization', 'class_group', 'lesson'
    )

    class_ids = _class_ids_filter(request)
    if class_ids is not None:
        queryset = queryset.filter(class_group_id__in=class_ids)

    class_id = request.query_params.get('class_id')
    lesson_id = request.query_params.get('lesson_id')
    date_from = request.query_params.get('date_from')
    date_to = request.query_params.get('date_to')
    trimestre = request.query_params.get('trimestre')
    ano = request.query_params.get('ano')

    if class_id:
        queryset = queryset.filter(class_group_id=class_id)
    if lesson_id:
        queryset = queryset.filter(lesson_id=lesson_id)
    if date_from:
        queryset = queryset.filter(data__gte=date_from)
    if date_to:
        queryset = queryset.filter(data__lte=date_to)
    if trimestre:
        filters = {'lesson__trimestre': trimestre}
        if ano:
            filters['lesson__ano'] = ano
        queryset = queryset.filter(**filters)

    return queryset


def _decimal(value):
    if value is None:
        return Decimal('0')
    return Decimal(value)


def _positive_int(raw, default, *, minimum=1, maximum=None):
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    if value < minimum:
        return default
    if maximum is not None:
        return min(value, maximum)
    return value


def _serialize_lancamento(offering):
    return {
        'id': offering.id,
        'data': offering.data.isoformat(),
        'valor': float(offering.valor),
        'igreja_nome': offering.organization.nome if offering.organization_id else None,
        'turma_nome': offering.class_group.nome if offering.class_group_id else None,
        'licao_tema': offering.lesson.tema if offering.lesson_id else None,
        'licao_id': offering.lesson_id,
        'turma_id': offering.class_group_id,
        'organization_id': offering.organization_id,
    }


def _paginate_lancamentos(request, queryset):
    page = _positive_int(request.query_params.get('page'), 1)
    page_size = _positive_int(
        request.query_params.get('page_size'),
        FINANCE_LANCAMENTOS_PAGE_SIZE_DEFAULT,
        maximum=50,
    )
    ordered = queryset.order_by('-data', '-id')
    total = ordered.count()
    offset = (page - 1) * page_size
    items = ordered[offset : offset + page_size]
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    return {
        'items': [_serialize_lancamento(offering) for offering in items],
        'paginacao': {
            'page': page,
            'page_size': page_size,
            'total': total,
            'total_pages': total_pages,
        },
    }


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('financeiro', 'visualizar')])
def finance_lancamentos(request):
    queryset = _base_offerings_queryset(request)
    payload = _paginate_lancamentos(request, queryset)
    return Response(
        {
            'items': payload['items'],
            'paginacao': payload['paginacao'],
        }
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated, module_permission('financeiro', 'visualizar')])
def finance_resumo(request):
    active_org = get_user_organization(request)
    scope = 'campo' if is_campo_organization(active_org) else 'igreja'
    queryset = _base_offerings_queryset(request)

    agg = queryset.aggregate(total=Sum('valor'), media=Sum('valor'), count=Count('id'))
    total = _decimal(agg['total'])
    lancamentos = agg['count'] or 0
    media = total / lancamentos if lancamentos else Decimal('0')

    evolucao_rows = (
        queryset.annotate(mes=TruncMonth('data'))
        .values('mes')
        .annotate(valor=Sum('valor'))
        .order_by('mes')
    )
    evolucao_mensal = [
        {'mes': row['mes'].strftime('%Y-%m-%d'), 'valor': float(_decimal(row['valor']))}
        for row in evolucao_rows
        if row['mes']
    ]

    por_igreja = []
    por_turma = []
    destaque = {'label': '—', 'valor': 0.0}

    if scope == 'campo':
        church_rows = (
            queryset.values('organization_id', 'organization__nome')
            .annotate(valor=Sum('valor'), lancamentos=Count('id'))
            .order_by('-valor')
        )
        por_igreja = [
            {
                'organization_id': row['organization_id'],
                'nome': row['organization__nome'] or '—',
                'valor': float(_decimal(row['valor'])),
                'lancamentos': row['lancamentos'],
            }
            for row in church_rows
        ]
        if por_igreja:
            top = por_igreja[0]
            destaque = {'label': top['nome'], 'valor': top['valor']}
    else:
        org_id = active_org.id
        turmas = ClassGroup.objects.filter(organization_id=org_id, is_active=True).order_by('nome')
        offering_by_class = {
            row['class_group_id']: _decimal(row['valor'])
            for row in queryset.filter(class_group_id__isnull=False)
            .values('class_group_id')
            .annotate(valor=Sum('valor'))
        }
        por_turma = [
            {
                'class_id': turma.id,
                'nome': turma.nome,
                'valor': float(offering_by_class.get(turma.id, Decimal('0'))),
                'cor': turma.cor or '',
            }
            for turma in turmas
        ]
        por_turma.sort(key=lambda item: item['valor'], reverse=True)
        turmas_com_valor = [item for item in por_turma if item['valor'] > 0]
        if turmas_com_valor:
            top = turmas_com_valor[0]
            destaque = {'label': top['nome'], 'valor': top['valor']}

    return Response(
        {
            'scope': scope,
            'organizacao_nome': active_org.nome,
            'summary': {
                'total': float(total),
                'media': float(media),
                'lancamentos': lancamentos,
                'destaque': destaque,
            },
            'evolucao_mensal': evolucao_mensal,
            'por_igreja': por_igreja,
            'por_turma': por_turma,
        }
    )
