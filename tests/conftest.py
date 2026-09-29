from unittest.mock import patch

import pytest
from allianceauth.authentication.models import CharacterOwnership
from allianceauth.eveonline.models import EveCharacter
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.cache import cache


@pytest.fixture(autouse=True)
def isolated_cache():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def user(db):
    # AA schedules unrelated audits in signals; isolate those background jobs.
    with patch("celery.app.task.Task.apply_async"):
        user = get_user_model().objects.create_user("pilot", password="test-only")
    user.user_permissions.add(
        Permission.objects.get(
            codename="basic_access", content_type__app_label="planetary_operations"
        )
    )
    return user


@pytest.fixture
def ownership(user):
    with patch("celery.app.task.Task.apply_async"):
        character = EveCharacter.objects.create(
            character_id=90000001, character_name="Test Pilot", corporation_id=98000001
        )
        ownership = CharacterOwnership.objects.create(
            user=user, character=character, owner_hash="test-owner-hash"
        )
        user.profile.main_character = character
        user.profile.save()
    return ownership
