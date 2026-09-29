from dataclasses import asdict
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from esi.models import Scope, Token

from planetary_operations.characters import SCOPES, planning_character, refresh_character
from planetary_operations.models import Plan
from planetary_operations.planner import Config, PlanningError
from planetary_operations.tasks import calculate_plan


def url(name, **kwargs):
    return reverse("planetary_operations:" + name, kwargs=kwargs)


@pytest.fixture
def token(ownership):
    with patch("celery.app.task.Task.apply_async"):
        token = Token.objects.create(
            user=ownership.user,
            character_id=ownership.character.character_id,
            character_name=ownership.character.character_name,
            character_owner_hash=ownership.owner_hash,
            access_token="test-token",
            refresh_token="test-refresh",
        )
        token.scopes.set([Scope.objects.get_or_create(name=s)[0] for s in SCOPES])
    return token


@pytest.fixture
def plan(user, ownership):
    return Plan.objects.create(
        owner=user,
        name="Test Operation",
        character_ids=[ownership.character.character_id],
        config=asdict(Config(9848, 2, 10000002, quantity=3)),
    )


def mock_character(requests_mock, character_id=90000001):
    requests_mock.get(
        f"https://esi.evetech.net/latest/characters/{character_id}/skills/",
        json={
            "skills": [
                {"skill_id": 2495, "active_skill_level": 4, "trained_skill_level": 5},
                {"skill_id": 2505, "active_skill_level": 4, "trained_skill_level": 5},
            ]
        },
    )
    requests_mock.get(
        f"https://esi.evetech.net/latest/characters/{character_id}/planets/",
        json=[{"planet_id": 40000002}],
    )


def test_skills_use_active_levels_and_reserve_colonies(token, ownership, requests_mock):
    mock_character(requests_mock)
    with patch.object(Token, "valid_access_token", return_value="test-token"):
        snapshot = refresh_character(ownership.user, ownership.character.character_id)
    character = planning_character(snapshot)
    assert character.ic == 4 and character.ccu == 4
    assert character.slots == 4
    assert character.occupied == (40000002,)
    assert planning_character(snapshot, True).slots == 5
    assert all(
        r.headers["Authorization"] == "Bearer test-token" for r in requests_mock.request_history
    )


def test_other_users_token_is_never_used(token, ownership, requests_mock):
    with patch("celery.app.task.Task.apply_async"):
        other = get_user_model().objects.create_user("other")
    token.user = other
    token.save()
    with pytest.raises(PlanningError, match="Authorize"):
        refresh_character(ownership.user, ownership.character.character_id)
    assert not requests_mock.called


def test_transferred_character_token_rejected(token, ownership, requests_mock):
    token.character_owner_hash = "former-owner"
    token.save()
    with pytest.raises(PlanningError):
        refresh_character(ownership.user, ownership.character.character_id)
    assert not requests_mock.called


def test_missing_scope_rejected(token, ownership, requests_mock):
    token.scopes.clear()
    with pytest.raises(PlanningError):
        refresh_character(ownership.user, ownership.character.character_id)
    assert not requests_mock.called


def test_page_renders_real_aa_template(client, user, ownership):
    client.force_login(user)
    response = client.get(url("index"))
    assert response.status_code == 200
    assert b"Test Pilot" in response.content
    assert b"Build &amp; save plan" in response.content


def test_anonymous_and_missing_permission(client, user, ownership):
    assert client.get(url("index")).status_code == 302
    user.user_permissions.clear()
    client.force_login(user)
    assert client.get(url("index")).status_code == 403


@pytest.mark.parametrize("view", ["detail", "export", "status", "prices", "delete"])
def test_saved_plan_access_is_owner_only(client, user, plan, view):
    with patch("celery.app.task.Task.apply_async"):
        other = get_user_model().objects.create_user("other")
    plan.owner = other
    plan.save()
    client.force_login(user)
    response = (
        client.post(url(view, pk=plan.pk))
        if view in ["prices", "delete"]
        else client.get(url(view, pk=plan.pk))
    )
    assert response.status_code == 404


def test_csrf_and_post_required(user, plan):
    client = Client(enforce_csrf_checks=True)
    client.force_login(user)
    assert client.get(url("delete", pk=plan.pk)).status_code == 405
    assert client.post(url("delete", pk=plan.pk)).status_code == 403
    assert Plan.objects.filter(pk=plan.pk).exists()


def test_submit_validates_owned_characters(client, user, ownership):
    client.force_login(user)
    data = dict(asdict(Config(9848, 2, 10000002)), name="Robotics", characters=["99999999"])
    response = client.post(url("index"), data)
    assert response.status_code == 200
    assert not Plan.objects.exists()


def test_submit_saves_before_queueing(client, user, ownership, django_capture_on_commit_callbacks):
    client.force_login(user)
    data = dict(
        asdict(Config(9848, 2, 10000002)),
        name="Robotics",
        characters=[ownership.character.character_id],
    )
    with patch("planetary_operations.views.calculate_plan.delay") as enqueue:
        with django_capture_on_commit_callbacks(execute=True):
            response = client.post(url("index"), data)
    assert response.status_code == 302
    saved = Plan.objects.get()
    enqueue.assert_called_once_with(saved.pk)
    assert saved.owner_id == user.pk


def test_worker_builds_and_saves_when_market_unavailable(plan, token, requests_mock, client):
    mock_character(requests_mock)
    requests_mock.get("https://esi.evetech.net/latest/markets/10000002/orders/", status_code=503)
    with patch.object(Token, "valid_access_token", return_value="test-token"):
        calculate_plan.run(plan.pk)
    plan.refresh_from_db()
    assert plan.status == Plan.Status.READY
    assert plan.result["output"] == 3
    assert "error" in plan.valuation
    assert len(plan.character_snapshot) == 1
    client.force_login(plan.owner)
    response = client.get(url("detail", pk=plan.pk))
    assert response.status_code == 200
    assert b"Production build sheet" in response.content
    exported = client.get(url("export", pk=plan.pk)).json()
    assert exported["result"]["output"] == 3
    assert "test-token" not in str(exported)


def test_worker_failure_is_actionable_and_duplicate_ignored(plan, requests_mock):
    calculate_plan.run(plan.pk)
    plan.refresh_from_db()
    assert plan.status == Plan.Status.FAILED
    assert "Authorize" in plan.error
    with patch("planetary_operations.tasks.refresh_character") as refresh:
        calculate_plan.run(plan.pk)
    refresh.assert_not_called()
