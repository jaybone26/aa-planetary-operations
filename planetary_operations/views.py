import logging

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required, permission_required
from django.db import transaction
from django.http import Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from esi.decorators import token_required

from .characters import SCOPES, owned_characters, refresh_character
from .esi import ESIUnavailable
from .forms import PlanForm
from .market import valuate
from .models import CharacterSnapshot, Plan
from .planner import PlanningError
from .tasks import calculate_plan

logger = logging.getLogger(__name__)
access = permission_required("planetary_operations.basic_access", raise_exception=True)


def _enqueue(plan_id):
    try:
        calculate_plan.delay(plan_id)
    except Exception:
        logger.exception("Unable to enqueue plan %s", plan_id)
        Plan.objects.filter(pk=plan_id).update(
            status=Plan.Status.FAILED,
            error="The AA worker queue is unavailable. Ask an administrator to check Celery.",
        )


@login_required
@access
def index(request):
    initial = None
    if request.GET.get("copy"):
        try:
            source_id = int(request.GET["copy"])
        except ValueError as exc:
            raise Http404("Unknown plan.") from exc
        source = get_object_or_404(Plan, pk=source_id, owner=request.user)
        initial = dict(
            source.config,
            name=f"{source.name} (copy)"[:120],
            characters=[str(i) for i in source.character_ids],
            replace_existing=source.replace_existing,
        )
    form = PlanForm(
        request.POST if request.method == "POST" else None, user=request.user, initial=initial
    )
    if request.method == "POST" and form.is_valid():
        # Per-user active limit prevents accidental repeated expensive submissions.
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if (
                Plan.objects.filter(
                    owner=request.user, status__in=[Plan.Status.PENDING, Plan.Status.RUNNING]
                ).count()
                >= 2
            ):
                form.add_error(None, "Two plans are already building. Wait for one to finish.")
            else:
                plan = Plan.objects.create(
                    owner=request.user,
                    name=form.cleaned_data["name"],
                    config=form.config(),
                    character_ids=form.cleaned_data["characters"],
                    replace_existing=form.cleaned_data["replace_existing"],
                )
                transaction.on_commit(lambda: _enqueue(plan.pk))
                return redirect("planetary_operations:detail", pk=plan.pk)
    snapshots = {
        s.ownership_id: s for s in CharacterSnapshot.objects.filter(ownership__user=request.user)
    }
    characters = []
    for ownership in owned_characters(request.user):
        snapshot = snapshots.get(ownership.pk)
        if snapshot and snapshot.owner_hash != ownership.owner_hash:
            snapshot = None
        characters.append(
            dict(
                id=ownership.character.character_id,
                name=ownership.character.character_name,
                snapshot=snapshot,
                ccu=snapshot.skills.get("2505", 0) if snapshot else None,
                colonies=1 + snapshot.skills.get("2495", 0) if snapshot else None,
                occupied=len(snapshot.colonies) if snapshot else None,
            )
        )
    return render(
        request,
        "planetary_operations/index.html",
        dict(form=form, characters=characters, plans=Plan.objects.filter(owner=request.user)[:100]),
    )


@login_required
@access
@token_required(scopes=SCOPES, new=True)
def authorize(request, token):
    ownership = (
        owned_characters(request.user)
        .filter(character__character_id=token.character_id, owner_hash=token.character_owner_hash)
        .first()
    )
    if not ownership or token.user_id != request.user.pk:
        return HttpResponseForbidden(
            "Attach this character to your AA account before authorizing PI access."
        )
    try:
        refresh_character(request.user, token.character_id)
        messages.success(request, f"PI access updated for {ownership.character.character_name}.")
    except (PlanningError, ESIUnavailable) as exc:
        messages.error(request, str(exc))
    return redirect("planetary_operations:index")


@login_required
@access
@require_POST
def refresh(request, character_id):
    try:
        refresh_character(request.user, character_id)
        messages.success(request, "Skills and occupied colonies refreshed.")
    except (PlanningError, ESIUnavailable) as exc:
        messages.error(request, str(exc))
    return redirect("planetary_operations:index")


@login_required
@access
def detail(request, pk):
    plan = get_object_or_404(Plan, pk=pk, owner=request.user)
    colonies = {c["id"]: c for c in plan.result.get("colonies", [])}
    movements = []
    for row in plan.result.get("logistics", []):

        def label(cid, fallback):
            if cid is None:
                return fallback
            c = colonies[cid]
            return f"#{cid + 1} · {c['character']} · {c['planet']['name']}"

        movements.append(
            dict(
                row,
                source_label=label(row["source"], "Imported supply"),
                target_label=label(row["target"], "Collect / sell"),
            )
        )
    return render(request, "planetary_operations/detail.html", dict(plan=plan, movements=movements))


@login_required
@access
def status(request, pk):
    plan = get_object_or_404(Plan, pk=pk, owner=request.user)
    return JsonResponse(dict(status=plan.status))


@login_required
@access
def export(request, pk):
    plan = get_object_or_404(Plan, pk=pk, owner=request.user)
    response = JsonResponse(
        dict(
            name=plan.name,
            config=plan.config,
            characters=plan.character_snapshot,
            result=plan.result,
            valuation=plan.valuation,
        ),
        json_dumps_params={"indent": 2},
    )
    response["Content-Disposition"] = f'attachment; filename="planetary-operation-{pk}.json"'
    return response


@login_required
@access
@require_POST
def prices(request, pk):
    plan = get_object_or_404(Plan, pk=pk, owner=request.user, status=Plan.Status.READY)
    try:
        valuation = valuate(plan.result)
        Plan.objects.filter(pk=plan.pk).update(valuation=valuation, updated_at=timezone.now())
        messages.success(request, "Jita estimate refreshed (ESI cache may apply).")
    except ESIUnavailable as exc:
        messages.error(request, str(exc))
    return redirect("planetary_operations:detail", pk=pk)


@login_required
@access
@require_POST
def delete(request, pk):
    get_object_or_404(Plan, pk=pk, owner=request.user).delete()
    messages.success(request, "Saved plan deleted.")
    return redirect("planetary_operations:index")
