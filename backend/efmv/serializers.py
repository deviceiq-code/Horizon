from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from catalogs.models import MAX_TERM_MONTHS
from catalogs.serializers import sub_vertical_label
from pricing.models import AveragePrice
from users.display import full_name_in, person_ref
from users.models import is_account_manager

from .calculations import Line, covers_term, line_total, scenario_totals
from .models import EfmvAnalysis, EfmvScenario, EfmvScenarioItem

User = get_user_model()


def current_prices(lineages) -> dict:
    """Current (not deleted) average price of each lineage, with what the analysis shows."""
    rows = (
        AveragePrice.objects.active()
        .filter(lineage__in=set(lineages))
        .select_related("asset_class", "manufacturer", "sub_vertical__vertical")
        .prefetch_related("points")
    )
    return {row.lineage: row for row in rows}


def price_terms(row: AveragePrice) -> list[int]:
    return sorted(point.term_months for point in row.points.all())


def asset_detail(row: AveragePrice) -> dict:
    return {
        "average_price": row.id,
        "asset_class": {"name": row.asset_class.name, "icon": row.asset_class.icon},
        "manufacturer": row.manufacturer.name,
        "model": row.model,
        "sub_vertical": sub_vertical_label(row.sub_vertical),
        "original_value": str(row.original_value),
        "currency": row.currency,
        "terms": price_terms(row),
    }


def totals_payload(totals) -> dict:
    as_text = lambda value: None if value is None else str(value)  # noqa: E731
    return {
        "lo": str(totals.lo),
        # eFMV at the end of the lease: to come
        "efmv_percent": None,
        "hw_percent": as_text(totals.hw_percent),
        "sw_percent": as_text(totals.sw_percent),
        "sv_percent": as_text(totals.sv_percent),
    }


def scenario_payload(term_months: int, items: list[tuple], prices: dict) -> dict:
    """`items`: (item id or None, lineage, quantity). Items whose price was deleted or whose
    curve no longer reaches the term are flagged and left out of the totals."""
    lines, rows = [], []
    for item_id, lineage, quantity in items:
        row = prices.get(lineage)
        entry = {"id": item_id, "quantity": quantity, "available": row is not None}
        if row is None:
            entry.update({"average_price": None, "line_total": None, "out_of_curve": False})
        else:
            out = not covers_term(price_terms(row), term_months)
            entry.update(asset_detail(row))
            entry["line_total"] = str(line_total(quantity, row.original_value))
            entry["out_of_curve"] = out
            if not out:
                lines.append(Line("hw", quantity, row.original_value))
        rows.append(entry)
    return {"items": rows, "totals": totals_payload(scenario_totals(lines))}


# --- Input ------------------------------------------------------------------------------------


class ItemInputSerializer(serializers.Serializer):
    # Any version of the average price; its current version is the one used
    average_price = serializers.PrimaryKeyRelatedField(queryset=AveragePrice.objects.all())
    quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)

    def validate_average_price(self, value):
        if value.deleted_at is not None:
            raise serializers.ValidationError(_("This average price was deleted."))
        return value


class ScenarioInputSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=100)
    term_months = serializers.IntegerField(min_value=1, max_value=MAX_TERM_MONTHS)
    scope = serializers.CharField(required=False, allow_blank=True, default="")
    items = ItemInputSerializer(many=True, required=False, default=list)

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def validate(self, attrs):
        lineages = [item["average_price"].lineage for item in attrs["items"]]
        prices = current_prices(lineages)
        errors, seen = {}, set()
        for index, item in enumerate(attrs["items"]):
            lineage = item["average_price"].lineage
            row = prices.get(lineage)
            if lineage in seen:
                errors[str(index)] = {
                    "average_price": [_("This asset is already in the scenario.")]
                }
            elif row is None:
                errors[str(index)] = {"average_price": [_("This average price was deleted.")]}
            elif not covers_term(price_terms(row), attrs["term_months"]):
                errors[str(index)] = {
                    "average_price": [
                        _(
                            "The value curve of this asset goes up to %(last)s months; "
                            "the scenario is %(term)s months."
                        )
                        % {"last": max(price_terms(row)), "term": attrs["term_months"]}
                    ]
                }
            seen.add(lineage)
        if errors:
            raise serializers.ValidationError({"items": errors})
        return attrs


class EfmvAnalysisSerializer(serializers.ModelSerializer):
    """An analysis with its scenarios (at least one) and their assets. Sending `scenarios`
    replaces them all. The account manager must be one of the customer's (primary or
    secondary)."""

    code = serializers.CharField(read_only=True)
    account_manager_detail = serializers.SerializerMethodField()
    customer_detail = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    scenarios = ScenarioInputSerializer(many=True, write_only=True)

    class Meta:
        model = EfmvAnalysis
        fields = [
            "id",
            "code",
            "account_manager",
            "account_manager_detail",
            "customer",
            "customer_detail",
            "scenarios",
            "created_at",
            "created_by_name",
            "updated_at",
        ]
        read_only_fields = ["id", "code", "created_at", "updated_at"]

    def get_account_manager_detail(self, obj) -> dict:
        return person_ref(self.context, obj.account_manager)

    def get_customer_detail(self, obj) -> dict:
        c = obj.customer
        return {"id": c.id, "name": c.name, "trade_name": c.trade_name, "tax_id": c.tax_id}

    def get_created_by_name(self, obj) -> str | None:
        return full_name_in(self.context, obj.created_by) if obj.created_by else None

    def validate_account_manager(self, value):
        if not (value.is_active and is_account_manager(value)):
            raise serializers.ValidationError(_("This user is not an account manager."))
        return value

    def validate_scenarios(self, value):
        if not value:
            raise serializers.ValidationError(_("Add at least one scenario."))
        errors, seen = {}, set()
        for index, scenario in enumerate(value):
            key = scenario["name"].casefold()
            if key in seen:
                errors[str(index)] = {"name": [_("Scenario names must be different.")]}
            seen.add(key)
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate(self, attrs):
        manager = attrs.get("account_manager") or getattr(self.instance, "account_manager", None)
        customer = attrs.get("customer") or getattr(self.instance, "customer", None)
        if (
            manager
            and customer
            and not (
                customer.primary_account_manager_id == manager.pk
                or customer.secondary_account_managers.filter(pk=manager.pk).exists()
            )
        ):
            raise serializers.ValidationError(
                {"customer": [_("This account manager does not serve this customer.")]}
            )
        if self.instance is None and "scenarios" not in attrs:
            raise serializers.ValidationError({"scenarios": [_("Add at least one scenario.")]})
        return attrs

    def to_representation(self, instance):
        data = super().to_representation(instance)
        scenarios = list(instance.scenarios.all())
        items = {s.pk: list(s.items.all()) for s in scenarios}
        prices = current_prices(i.price_lineage for its in items.values() for i in its)
        data["scenarios"] = [
            {
                "id": s.id,
                "name": s.name,
                "term_months": s.term_months,
                "scope": s.scope,
                **scenario_payload(
                    s.term_months,
                    [(i.id, i.price_lineage, i.quantity) for i in items[s.pk]],
                    prices,
                ),
            }
            for s in scenarios
        ]
        return data

    def _save_scenarios(self, analysis, scenarios):
        analysis.scenarios.all().delete()
        for position, scenario in enumerate(scenarios):
            row = EfmvScenario.objects.create(
                analysis=analysis,
                name=scenario["name"],
                term_months=scenario["term_months"],
                scope=scenario.get("scope", ""),
                position=position,
            )
            EfmvScenarioItem.objects.bulk_create(
                EfmvScenarioItem(
                    scenario=row,
                    price_lineage=item["average_price"].lineage,
                    quantity=item["quantity"],
                    position=index,
                )
                for index, item in enumerate(scenario["items"])
            )

    def create(self, validated_data):
        scenarios = validated_data.pop("scenarios")
        year = timezone.localdate().year
        # The next code of the year; another analysis created at the same moment → try again
        for _attempt in range(5):
            try:
                with transaction.atomic():
                    last = (
                        EfmvAnalysis.objects.filter(year=year)
                        .order_by("-sequence")
                        .values_list("sequence", flat=True)
                        .first()
                    )
                    analysis = EfmvAnalysis.objects.create(
                        **validated_data,
                        year=year,
                        sequence=(last or 0) + 1,
                        created_by=self.context["request"].user,
                    )
                    self._save_scenarios(analysis, scenarios)
                    return analysis
            except IntegrityError:
                continue
        raise serializers.ValidationError(_("Could not create the analysis. Try again."))

    def update(self, instance, validated_data):
        scenarios = validated_data.pop("scenarios", None)
        with transaction.atomic():
            for field, value in validated_data.items():
                setattr(instance, field, value)
            instance.save()
            if scenarios is not None:
                self._save_scenarios(instance, scenarios)
        return instance


class EfmvAnalysisListSerializer(serializers.ModelSerializer):
    """An analysis as listed: code, customer, account manager and its scenarios' names."""

    code = serializers.CharField(read_only=True)
    account_manager_detail = serializers.SerializerMethodField()
    customer_detail = serializers.SerializerMethodField()
    scenario_names = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = EfmvAnalysis
        fields = [
            "id",
            "code",
            "account_manager_detail",
            "customer_detail",
            "scenario_names",
            "created_at",
            "created_by_name",
        ]
        read_only_fields = fields

    get_account_manager_detail = EfmvAnalysisSerializer.get_account_manager_detail
    get_customer_detail = EfmvAnalysisSerializer.get_customer_detail
    get_created_by_name = EfmvAnalysisSerializer.get_created_by_name

    def get_scenario_names(self, obj) -> list[str]:
        return [s.name for s in obj.scenarios.all()]


class ScenarioPreviewSerializer(serializers.Serializer):
    """The totals of a scenario being edited (nothing saved): the form never computes them."""

    term_months = serializers.IntegerField(min_value=1, max_value=MAX_TERM_MONTHS)
    items = ItemInputSerializer(many=True)

    def to_representation(self, instance):
        items = [(None, i["average_price"].lineage, i["quantity"]) for i in instance["items"]]
        prices = current_prices(lineage for _, lineage, _q in items)
        return scenario_payload(instance["term_months"], items, prices)


# Silence "imported but unused" for names used only in type contexts
