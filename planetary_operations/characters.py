"""AA ownership and scoped-token checks precede every private ESI read."""

from allianceauth.authentication.models import CharacterOwnership
from esi.models import Token

from . import esi
from .models import CharacterSnapshot
from .planner import Character, PlanningError

SCOPES = ["esi-skills.read_skills.v1", "esi-planets.manage_planets.v1"]
PI_SKILLS = {
    2495: "interplanetary_consolidation",
    2505: "command_center_upgrades",
    2403: "planetology",
    2406: "advanced_planetology",
    13279: "remote_sensing",
}


def owned_characters(user):
    return CharacterOwnership.objects.filter(user=user).select_related("character")


def refresh_character(user, character_id):
    try:
        ownership = owned_characters(user).get(character__character_id=character_id)
    except CharacterOwnership.DoesNotExist as exc:
        raise PlanningError("That character is not attached to your AA account.") from exc
    token = (
        Token.objects.filter(
            user=user, character_id=character_id, character_owner_hash=ownership.owner_hash
        )
        .require_scopes(SCOPES)
        .first()
    )
    if not token:
        raise PlanningError(f"Authorize PI access for {ownership.character.character_name}.")
    try:
        access = token.valid_access_token()
    except Exception as exc:
        raise PlanningError(
            f"Reauthorize PI access for {ownership.character.character_name}."
        ) from exc
    data, _ = esi.get(f"characters/{character_id}/skills/", access_token=access)
    colonies, _ = esi.get(f"characters/{character_id}/planets/", access_token=access)
    try:
        # Active levels respect current account/skill restrictions.
        skills = {
            str(row["skill_id"]): row["active_skill_level"]
            for row in data["skills"]
            if row["skill_id"] in PI_SKILLS
        }
        if any(not isinstance(v, int) or not 0 <= v <= 5 for v in skills.values()):
            raise ValueError("Invalid skill level")
        planet_ids = [int(row["planet_id"]) for row in colonies]
    except (KeyError, TypeError, ValueError) as exc:
        raise esi.ESIUnavailable("ESI returned incomplete character data.") from exc
    # Recheck ownership after network calls, including transfers between users.
    if not CharacterOwnership.objects.filter(
        pk=ownership.pk, user=user, owner_hash=ownership.owner_hash
    ).exists():
        raise PlanningError("Character ownership changed during the refresh.")
    snapshot, _ = CharacterSnapshot.objects.update_or_create(
        ownership=ownership,
        defaults=dict(owner_hash=ownership.owner_hash, skills=skills, colonies=planet_ids),
    )
    return snapshot


def planning_character(snapshot, replace_existing=False):
    character = snapshot.ownership.character
    return Character(
        id=character.character_id,
        name=character.character_name,
        ic=snapshot.skills.get("2495", 0),
        ccu=snapshot.skills.get("2505", 0),
        reserved=0 if replace_existing else len(snapshot.colonies),
        occupied=() if replace_existing else tuple(snapshot.colonies),
    )
