from datetime import datetime

from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.shortcuts import render

from .models import Fatura


def _parse_date(s: str):
    try:
        s = (s or "").strip()
        return datetime.strptime(s, "%Y-%m-%d").date() if s else None
    except Exception:
        return None


def faturas_pesquisa(request):
    # filtros básicos
    q       = (request.GET.get("q") or "").strip()
    status  = (request.GET.get("status") or "").strip()
    closing = _parse_date(request.GET.get("closing"))
    due     = _parse_date(request.GET.get("due"))

    # BASE: aplica busca + datas, mas AINDA sem status
    base_qs = Fatura.objects.all()

    if q:
        base_qs = base_qs.filter(Q(account_id__icontains=q) | Q(statement_id__icontains=q))
    if closing:
        base_qs = base_qs.filter(cycle_closing_at=closing)
    if due:
        base_qs = base_qs.filter(due_at=due)

    # Contagem por status deve refletir somente q/closing/due (não restringe pelo status escolhido)
    status_order = [s for s, _ in Fatura.Status.choices]
    counts_map = {s: 0 for s in status_order}
    for row in base_qs.values("status").annotate(qtd=Count("id")):
        counts_map[row["status"]] = row["qtd"]
    counts_list = [(s, counts_map[s]) for s in status_order]

    # LISTA: agora sim aplica o status (se houver) e ordena
    qs = base_qs.order_by("-due_at", "-cycle_closing_at")
    if status:
        qs = qs.filter(status=status)

    total_count = qs.count()

    paginator = Paginator(qs, 25)
    page_obj = paginator.get_page(request.GET.get("page"))

    ctx = {
        "page_obj": page_obj,
        "statuses": status_order,
        "params": {
            "q": q,
            "status": status,
            "closing": request.GET.get("closing", ""),
            "due": request.GET.get("due", ""),
        },
        "counts_list": counts_list,
        "total_count": total_count,
    }
    return render(request, "faturas/pesquisa.html", ctx)
