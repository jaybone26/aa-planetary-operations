from dataclasses import asdict

from django import forms

from .catalog import catalog
from .characters import owned_characters
from .planner import Config, PlanningError


class PlanForm(forms.Form):
    name = forms.CharField(max_length=120, initial="My planetary operation")
    characters = forms.MultipleChoiceField(
        widget=forms.CheckboxSelectMultiple,
        help_text="Skills and occupied planets are refreshed when you build.",
    )
    product = forms.TypedChoiceField(coerce=int, label="Finished product")
    start_tier = forms.TypedChoiceField(
        coerce=int,
        choices=[
            (0, "P0 — Extract all raw resources"),
            (1, "Import P1 and lower"),
            (2, "Import P2 and lower"),
            (3, "Import P3 and lower"),
        ],
    )
    region = forms.TypedChoiceField(coerce=int)
    quantity = forms.IntegerField(
        min_value=1,
        max_value=10_000_000,
        initial=24,
        label="Target finished units per pull",
        help_text="Whole factory batches may produce a small surplus.",
    )
    hours = forms.FloatField(
        min_value=1, max_value=336, initial=24, label="Hours per extraction pull"
    )
    raw_per_hour = forms.IntegerField(
        min_value=1,
        max_value=1_000_000,
        initial=6000,
        label="Estimated raw units per hour, per ECU",
        help_text="Use the average shown by your in-game extraction program for the selected head count. This is an assumption, not a resource scan.",
    )
    heads = forms.IntegerField(
        min_value=1, max_value=10, initial=5, label="Heads per extractor control unit"
    )
    reserve_percent = forms.IntegerField(
        min_value=5, max_value=50, initial=15, label="CPU and power reserved for links (%)"
    )
    max_jumps = forms.IntegerField(
        min_value=0,
        max_value=5,
        initial=2,
        label="Maximum jumps from a nearby-system search center",
    )
    replace_existing = forms.BooleanField(
        required=False,
        label="Plan a replacement for my existing colonies",
        help_text="Uses full skill-based capacity. Existing colonies must be removed or rebuilt in game before this plan can run.",
    )

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["characters"].choices = [
            (str(o.character.character_id), o.character.character_name)
            for o in owned_characters(user)
        ]
        data = catalog()
        self.fields["product"].choices = [("", "Choose a finished product")] + [
            (p["id"], f"P{p['tier']} — {p['name']}")
            for p in sorted(data["commodities"].values(), key=lambda p: (p["tier"], p["name"]))
        ]
        regions = {str(s["region"]) for s in data["systems"].values() if s["planets"]}
        self.fields["region"].choices = [("", "Choose a region")] + sorted(
            [(int(k), v) for k, v in data["regions"].items() if k in regions], key=lambda r: r[1]
        )
        for name, field in self.fields.items():
            if name not in ("characters", "replace_existing"):
                field.widget.attrs["class"] = (
                    "form-select" if isinstance(field.widget, forms.Select) else "form-control"
                )

    def clean_characters(self):
        values = self.cleaned_data["characters"]
        if len(values) > 10 or len(set(values)) != len(values):
            raise forms.ValidationError("Select up to ten distinct characters.")
        return [int(v) for v in values]

    def clean(self):
        cleaned = super().clean()
        keys = Config.__dataclass_fields__
        if all(k in cleaned for k in keys):
            try:
                Config(**{k: cleaned[k] for k in keys}).validate()
            except PlanningError as exc:
                raise forms.ValidationError(str(exc)) from exc
        return cleaned

    def config(self):
        return asdict(Config(**{k: self.cleaned_data[k] for k in Config.__dataclass_fields__}))
