"""
JSON API for the Statistics page. Thin: parse filters, call one selector, serialise.

Routes (all GET, all need statistics.view, mounted under /statistics/api/):
    summary/         headline KPIs
    demographics/    population, gender, sectors, civil status, age bands
    purok-density/   residents and households per purok, ranked
    appointments/    status, category, document type, health service, issued documents
    revenue/         monthly revenue series, total, per document type
    blotter/         blotter cases by status, type and purok, monthly filed vs settled,
                     settlement rate and average days to settle (aggregate counts only)

Optional query filters: date_from, date_to (YYYY-MM-DD) and purok (id). A bad filter
returns 400 {"error": "..."}. Shape: {"filters": {...}, "generated_at": "...", "data": {...}}.
"""
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from apps.accounts.permissions import require_perm
from apps.statistics import selectors


def _respond(request, compute):
    try:
        filters = selectors.parse_filters(request.GET)
    except selectors.FilterError as exc:
        response = JsonResponse({'error': str(exc)}, status=400)
    else:
        response = JsonResponse({
            'filters': filters.as_dict(),
            'generated_at': timezone.now().isoformat(),
            'data': compute(filters),
        })
    response['Cache-Control'] = 'no-store'
    return response


@require_perm('statistics', 'view')
@require_GET
def summary(request):
    return _respond(request, selectors.summary_block)


@require_perm('statistics', 'view')
@require_GET
def demographics(request):
    return _respond(request, selectors.demographics)


@require_perm('statistics', 'view')
@require_GET
def purok_density(request):
    return _respond(request, selectors.purok_density)


@require_perm('statistics', 'view')
@require_GET
def appointments(request):
    return _respond(request, selectors.appointments)


@require_perm('statistics', 'view')
@require_GET
def revenue(request):
    return _respond(request, selectors.revenue)


@require_perm('statistics', 'view')
@require_GET
def blotter(request):
    return _respond(request, selectors.blotter)
