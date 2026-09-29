import logging
from dataclasses import asdict

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from .characters import owned_characters, planning_character, refresh_character
from .esi import ESIUnavailable
from .market import valuate
from .models import Plan
from .planner import Config, PlanningError, build_plan

logger = logging.getLogger(__name__)


@shared_task(soft_time_limit=180, time_limit=200)
def calculate_plan(plan_id):
    # A duplicate queue delivery cannot run the same plan twice.
    if not Plan.objects.filter(pk=plan_id, status=Plan.Status.PENDING).update(
        status=Plan.Status.RUNNING, updated_at=timezone.now()
    ):
        return
    plan = Plan.objects.select_related("owner").filter(pk=plan_id).first()
    if plan is None:
        return
    try:
        if not plan.owner.has_perm("planetary_operations.basic_access"):
            raise PlanningError("Planetary Operations access was removed from your account.")
        characters = [
            planning_character(refresh_character(plan.owner, cid), plan.replace_existing)
            for cid in plan.character_ids
        ]
        result = build_plan(
            Config(**plan.config),
            characters,
            time_limit=min(
                120, max(5, getattr(settings, "PLANETARY_OPERATIONS_SEARCH_SECONDS", 30))
            ),
        )
        current = set(
            owned_characters(plan.owner).values_list("character__character_id", flat=True)
        )
        if not set(plan.character_ids).issubset(current):
            raise PlanningError("Character ownership changed. Create a new plan.")
        try:
            valuation = valuate(result)
        except ESIUnavailable:
            valuation = dict(
                error="Jita pricing is unavailable. The production plan is saved; refresh prices later."
            )
        Plan.objects.filter(pk=plan_id).update(
            status=Plan.Status.READY,
            result=result,
            valuation=valuation,
            character_snapshot=[asdict(c) for c in characters],
            updated_at=timezone.now(),
            error="",
        )
    except (PlanningError, ESIUnavailable) as exc:
        Plan.objects.filter(pk=plan_id).update(
            status=Plan.Status.FAILED, error=str(exc), updated_at=timezone.now()
        )
    except Exception:
        logger.exception("Plan %s failed during calculation", plan_id)
        Plan.objects.filter(pk=plan_id).update(
            status=Plan.Status.FAILED,
            error="Calculation failed. Ask an administrator to check the worker log.",
            updated_at=timezone.now(),
        )
