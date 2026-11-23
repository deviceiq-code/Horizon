from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone, translation
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from accounts.models import UserPreferences
from catalogs.models import MAX_TERM_MONTHS, SubVertical
from catalogs.names import english_plural, localized
from catalogs.serializers import sub_vertical_label
from config.keywords import KeywordsField
from pricing.curves import value_at
from pricing.models import AveragePrice, PricingSettings
from pricing.positioning import is_expired, price_position, valid_until, variation_percent
from users.display import full_name_in, person_ref
from users.models import UserProfile, is_account_manager

from .calculations import (
    Line,
    covers_term,
    efmv_percent_of_unit,
    line_total,
    percent_of_value,
    scenario_totals,
    split_service,
    weight_percent,
)
from .models import (
    EfmvAnalysis,
    EfmvScenario,
    EfmvScenarioItem,
    ServiceMode,
    in_scope,
    title_key,
)
from .scope import ScopeGroup, scope_summary

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


def curve_value(row: AveragePrice, term_months: int):
    """The average price's value at the scenario's term (None beyond its curve)."""
    anchors = {point.term_months: point.value for point in row.points.all()}
    return value_at(row.original_value, anchors, term_months)


def asset_detail(row: AveragePrice) -> dict:
    return {
        "average_price": row.id,
        "asset_class": {"name": row.asset_class.name, "icon": row.asset_class.icon},
        "manufacturer": row.manufacturer.name,
        "model": row.model,
        # Template fields with their values, as stored with the price
        "specs": row.specs,
        "sub_vertical": sub_vertical_label(row.sub_vertical),
        "original_value": str(row.original_value),
        "currency": row.currency,
        "terms": price_terms(row),
    }


def scope_label(vertical, sub_vertical) -> str | None:
    """ "Healthcare" or "Healthcare / Diagnostics" (the general sub-vertical shows translated)."""
    if vertical is None:
        return None
    return sub_vertical_label(sub_vertical) if sub_vertical else vertical.name


def totals_payload(totals) -> dict:
    as_text = lambda value: None if value is None else str(value)  # noqa: E731
    return {
        "lo": str(totals.lo),
        # eFMV at the end of the lease: the items' eFMV weighted over the LO
        "efmv_total": str(totals.efmv_total),
        "efmv_percent": as_text(totals.efmv_percent),
        "hw_percent": as_text(totals.hw_percent),
        "sw_percent": as_text(totals.sw_percent),
        "sv_percent": as_text(totals.sv_percent),
        # The same shares in money
        "hw_total": str(totals.hw_total),
        "sw_total": str(totals.sw_total),
        "sv_total": str(totals.sv_total),
    }


class Context:
    """What positioning and the scope need, read once per request: the control panel, today,
    the language and the user's negligible threshold for the scope."""

    def __init__(self, request=None):
        self.settings = PricingSettings.current()
        self.limits = self.settings.limits()
        self.today = timezone.localdate()
        self.language = translation.get_language() or "en"
        user = getattr(request, "user", None)
        self.scope_threshold = (
            UserPreferences.for_user(user).scope_threshold
            if user is not None and user.is_authenticated
            else Decimal("5")
        )

    def expired(self, row: AveragePrice) -> bool:
        return is_expired(
            timezone.localtime(row.created_at), self.today, self.settings.validity_months
        )


def price_check(row: AveragePrice, unit_value, ctx: Context) -> dict:
    """How the typed value compares with the average price, and whether that price is still
    current (the date of its current version + the validity of the control panel)."""
    priced_on = timezone.localtime(row.created_at).date()
    data = {
        "priced_on": priced_on.isoformat(),
        "valid_until": valid_until(priced_on, ctx.settings.validity_months).isoformat(),
        "expired": ctx.expired(row),
        "variation_percent": None,
        "position": None,
    }
    if unit_value is not None:
        data["variation_percent"] = str(variation_percent(unit_value, row.original_value))
        data["position"] = str(price_position(unit_value, row.original_value, ctx.limits))
    return data


def resolve_service(service: dict | None, unit_value) -> dict | None:
    """A service's unit value (typed, or a percentage of the asset's value as typed, before any
    deduction) and the asset's value with it (`split_service`; None when deducting it would
    leave the asset with nothing)."""
    if not service or unit_value is None:
        return None
    value = service.get("value")
    if value is None:
        percent = service.get("percent")
        value = percent_of_value(unit_value, percent) if percent is not None else Decimal("0")
    split = split_service(unit_value, value, service.get("mode") == ServiceMode.DEDUCT)
    return {
        "name": service.get("name", ""),
        "mode": service.get("mode", ServiceMode.ADD),
        "value": value,
        "asset_value": split[0] if split else None,
    }


def scenario_payload(
    term_months: int,
    items: list[dict],
    prices: dict,
    ctx: Context,
    scope: tuple = (None, None),
) -> dict:
    """`items`: {id, lineage, quantity, unit_value, efmv_value, efmv_percent, service} — typed
    values or None; `service`: None or {name, mode, value or percent}. `scope`: the analysis's
    (vertical id, sub-vertical id). Without a typed value the average price's value counts
    (`value_from_price`); without a typed eFMV value, the average price's curve at the term
    (`efmv_from_curve`). A service deducted from the asset leaves it worth the rest
    (`net_unit_value`: what is positioned, totalled and what its eFMV % is of). Items whose
    price was deleted, whose curve no longer reaches the term, that are outside the analysis's
    vertical or whose deducted service is worth as much as the asset are flagged and left out
    of the totals."""
    lines, rows, counted, groups = [], [], [], []
    for item in items:
        quantity = item["quantity"]
        row = prices.get(item["lineage"])
        typed = item.get("unit_value")
        unit_value = typed if typed is not None or row is None else row.original_value
        service = resolve_service(item.get("service"), unit_value)
        service_too_high = service is not None and service["asset_value"] is None
        net = service["asset_value"] if service and not service_too_high else unit_value
        typed_efmv = item.get("efmv_value")
        if typed_efmv is None and item.get("efmv_percent") is not None and net is not None:
            # Typed as a percentage of the unit value: resolved here (the form shows the value)
            typed_efmv = percent_of_value(net, item["efmv_percent"])
        from_curve = None if row is None else curve_value(row, term_months)
        efmv_value = typed_efmv if typed_efmv is not None else from_curve
        entry = {
            "id": item.get("id"),
            "quantity": quantity,
            "unit_value": None if unit_value is None else str(unit_value),
            # The asset's own value: without the service when it was deducted from it
            "net_unit_value": None if net is None else str(net),
            "value_from_price": typed is None and row is not None,
            "line_total": None if net is None else str(line_total(quantity, net)),
            # One unit at the end of the term: typed, or the curve's value at the term
            "efmv_value": None if efmv_value is None else str(efmv_value),
            "curve_value": None if from_curve is None else str(from_curve),
            "efmv_from_curve": typed_efmv is None and from_curve is not None,
            # The eFMV as a percentage of the asset's value (shown below it)
            "efmv_percent": (
                None
                if efmv_value is None or not net
                else str(efmv_percent_of_unit(efmv_value, net))
            ),
            "available": row is not None,
            # Share of the scenario's LO; null when left out of the totals
            "weight_percent": None,
            "service": None,
        }
        if service:
            entry["service"] = {
                "name": service["name"],
                "mode": service["mode"],
                "value": str(service["value"]),
                "line_total": str(line_total(quantity, service["value"])),
                "weight_percent": None,
                # Worth more than the asset or, deducted, leaving it with nothing (refused)
                "too_high": service_too_high,
            }
        if row is None:
            entry.update(
                {
                    "average_price": None,
                    "out_of_curve": False,
                    "out_of_scope": False,
                    "expired": False,
                }
            )
        else:
            out = not covers_term(price_terms(row), term_months)
            outside = not in_scope(*scope, row.sub_vertical)
            entry.update(asset_detail(row))
            entry.update(price_check(row, net, ctx))
            # For the scope: the asset's manufacturer and class (its plural, in the language)
            asset_class = row.asset_class
            groups.append(
                ScopeGroup(
                    row.manufacturer.name,
                    localized(
                        asset_class.name,
                        asset_class.plural_name or english_plural(asset_class.name),
                        asset_class.translations,
                        ctx.language,
                        many=True,
                    ),
                    quantity,
                )
            )
            entry["out_of_curve"] = out
            entry["out_of_scope"] = outside
            if not out and not outside and net is not None and not service_too_high:
                lines.append(Line("hw", quantity, net, efmv_value))
                counted.append(entry)
                if service:
                    # Services are not resold: nothing left at the end of the term
                    lines.append(Line("sv", quantity, service["value"], Decimal("0")))
                    counted.append(entry["service"])
        rows.append(entry)
    totals = scenario_totals(lines)
    for entry, line in zip(counted, lines, strict=True):
        weight = weight_percent(line.quantity, line.unit_value, totals.lo)
        entry["weight_percent"] = None if weight is None else str(weight)
    return {
        "items": rows,
        "totals": totals_payload(totals),
        "has_expired": any(entry["expired"] for entry in rows),
        # Smart Tools: the scope written from the assets (the form uses it while the scope is
        # not written by hand)
        "scope_suggestion": scope_summary(groups, ctx.language, ctx.scope_threshold),
    }


def stored_item(item: EfmvScenarioItem) -> dict:
    """A saved item as `scenario_payload` reads it."""
    return {
        "id": item.id,
        "lineage": item.price_lineage,
        "quantity": item.quantity,
        "unit_value": item.unit_value,
        "efmv_value": item.efmv_value,
        "service": (
            {"name": item.service_name, "value": item.service_value, "mode": item.service_mode}
            if item.service_name
            else None
        ),
    }


# --- Input ------------------------------------------------------------------------------------


class ServiceInputSerializer(serializers.Serializer):
    """An item's service (SV): a name (e.g. "Warranty"), a value per unit — typed, or as a
    percentage of the asset's value — and whether it is added to the asset or deducted."""

    name = serializers.CharField(max_length=100)
    value = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False, allow_null=True
    )
    percent = serializers.DecimalField(
        max_digits=9, decimal_places=5, min_value=Decimal("0"), required=False, allow_null=True
    )
    mode = serializers.ChoiceField(choices=ServiceMode.choices, default=ServiceMode.ADD)

    def validate_name(self, value):
        value = " ".join(value.split())
        if not value:
            raise serializers.ValidationError(_("This field may not be blank."))
        return value

    def validate(self, attrs):
        if attrs.get("value") is not None and attrs.get("percent") is not None:
            raise serializers.ValidationError(
                {"percent": [_("Send the service as a value or as a percentage, not both.")]}
            )
        return attrs


class ItemInputSerializer(serializers.Serializer):
    # Any version of the average price; its current version is the one used
    average_price = serializers.PrimaryKeyRelatedField(queryset=AveragePrice.objects.all())
    quantity = serializers.IntegerField(min_value=1, max_value=1_000_000)
    # Typed by the analyst; when not sent, the current average price's value is stored
    unit_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, min_value=Decimal("0.01"), required=False, allow_null=True
    )
    # Typed by the analyst; when not sent, the curve's value at the scenario's term counts.
    # Negative: no resale value and a disposal cost.
    efmv_value = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    # Or typed as a percentage of the unit value ("25" = 25%, "-5" = a cost): turned into
    # `efmv_value`
    efmv_percent = serializers.DecimalField(
        max_digits=9, decimal_places=5, required=False, allow_null=True
    )
    # Its service (SV), at most one; null or absent: none
    service = ServiceInputSerializer(required=False, allow_null=True)

    def validate(self, attrs):
        if attrs.get("efmv_value") is not None and attrs.get("efmv_percent") is not None:
            raise serializers.ValidationError(
                {"efmv_percent": [_("Send the eFMV as a value or as a percentage, not both.")]}
            )
        return attrs

    def validate_average_price(self, value):
        if value.deleted_at is not None:
            raise serializers.ValidationError(_("This average price was deleted."))
        return value


class ScenarioInputSerializer(serializers.Serializer):
    # Optional: the official name is the term + this name (EfmvScenario.title)
    name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    term_months = serializers.IntegerField(min_value=1, max_value=MAX_TERM_MONTHS)
    scope = serializers.CharField(required=False, allow_blank=True, default="")
    items = ItemInputSerializer(many=True, required=False, default=list)

    def validate_name(self, value):
        return " ".join(value.split())

    def validate(self, attrs):
        # Whether each asset is of the analysis's vertical is checked with the analysis
        lineages = [item["average_price"].lineage for item in attrs["items"]]
        prices = current_prices(lineages)
        ctx = Context()
        errors = {}
        # The same asset may be in several rows (e.g. a different value per delivery state)
        for index, item in enumerate(attrs["items"]):
            row = prices.get(item["average_price"].lineage)
            if row is None:
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
            elif not ctx.settings.accept_expired and ctx.expired(row):
                errors[str(index)] = {
                    "average_price": [
                        _(
                            "This average price is more than %(months)s months old and expired "
                            "prices are not accepted. Update it in Average Prices."
                        )
                        % {"months": ctx.settings.validity_months}
                    ]
                }
            elif item.get("unit_value") is None:
                # Not typed: the value of the average price counts
                item["unit_value"] = row.original_value
            if str(index) in errors:
                continue
            asset_value = item["unit_value"]
            if item.get("service"):
                service = resolve_service(item["service"], item["unit_value"])
                if service["asset_value"] is None:
                    errors[str(index)] = {
                        "service": [_("The service cannot be worth more than the asset.")]
                    }
                    continue
                # Stored as the value it gives (also when typed as a percentage)
                item["service"]["value"] = service["value"]
                asset_value = service["asset_value"]
            if item.get("efmv_percent") is not None:
                # Stored as the value it gives (a percentage of the asset's value)
                item["efmv_value"] = percent_of_value(asset_value, item["efmv_percent"])
        if errors:
            raise serializers.ValidationError({"items": errors})
        return attrs


# Set when the analysis is created (wizard), not changed afterwards
PREMISES = ("account_manager", "customer", "vertical", "sub_vertical")


class EfmvAnalysisSerializer(serializers.ModelSerializer):
    """An analysis with its scenarios (at least one) and their assets. The premises — account
    manager (one of the customer's, primary or secondary), customer and vertical (or one of its
    sub-verticals: the assets the scenarios admit) — are set on creation and cannot change.
    Sending `scenarios` replaces them all."""

    code = serializers.CharField(read_only=True)
    account_manager_detail = serializers.SerializerMethodField()
    customer_detail = serializers.SerializerMethodField()
    vertical_label = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    sub_vertical = serializers.PrimaryKeyRelatedField(
        queryset=SubVertical.objects.all(), required=False, allow_null=True
    )
    scenarios = ScenarioInputSerializer(many=True, write_only=True)
    keywords = KeywordsField()

    class Meta:
        model = EfmvAnalysis
        fields = [
            "id",
            "code",
            "account_manager",
            "account_manager_detail",
            "customer",
            "customer_detail",
            "vertical",
            "sub_vertical",
            "vertical_label",
            "keywords",
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

    def get_vertical_label(self, obj) -> str | None:
        """ "Industry" or "Industry / Yellow line" """
        return scope_label(obj.vertical, obj.sub_vertical)

    def validate_account_manager(self, value):
        if not (value.is_active and is_account_manager(value)):
            raise serializers.ValidationError(_("This user is not an account manager."))
        return value

    def validate_scenarios(self, value):
        if not value:
            raise serializers.ValidationError(_("Add at least one scenario."))
        errors, seen = {}, set()
        for index, scenario in enumerate(value):
            key = title_key(scenario["term_months"], scenario["name"])
            if key in seen:
                errors[str(index)] = {
                    "name": [_("Another scenario already has this term and name.")]
                }
            seen.add(key)
        if errors:
            raise serializers.ValidationError(errors)
        return value

    def validate(self, attrs):
        if self.instance is not None:
            # The premises stay as created
            errors = {
                field: [_("This cannot be changed after the analysis is created.")]
                for field in PREMISES
                if field in attrs and attrs[field] != getattr(self.instance, field)
            }
            if errors:
                raise serializers.ValidationError(errors)
        elif attrs.get("vertical") is None:
            raise serializers.ValidationError({"vertical": [_("This field is required.")]})
        vertical = attrs.get("vertical") or getattr(self.instance, "vertical", None)
        sub_vertical = attrs.get("sub_vertical", getattr(self.instance, "sub_vertical", None))
        if (
            sub_vertical is not None
            and vertical is not None
            and sub_vertical.vertical_id != vertical.pk
        ):
            raise serializers.ValidationError(
                {"sub_vertical": [_("This sub-vertical is not of the chosen vertical.")]}
            )
        manager = attrs.get("account_manager") or getattr(self.instance, "account_manager", None)
        customer = attrs.get("customer") or getattr(self.instance, "customer", None)
        if (
            self.instance is None
            and manager is not None
            and vertical is not None
            and not UserProfile.for_user(manager).verticals.filter(pk=vertical.pk).exists()
        ):
            raise serializers.ValidationError(
                {"vertical": [_("This account manager does not work in this vertical.")]}
            )
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
        if "scenarios" in attrs:
            self._check_scope(attrs["scenarios"], vertical, sub_vertical)
        return attrs

    @staticmethod
    def _check_scope(scenarios, vertical, sub_vertical):
        """Every asset must be of the analysis's vertical (or sub-vertical)."""
        if vertical is None:
            return
        items = [item for scenario in scenarios for item in scenario["items"]]
        prices = current_prices(item["average_price"].lineage for item in items)
        errors = {}
        for s_index, scenario in enumerate(scenarios):
            for i_index, item in enumerate(scenario["items"]):
                row = prices.get(item["average_price"].lineage)
                if row is not None and not in_scope(
                    vertical.pk, sub_vertical and sub_vertical.pk, row.sub_vertical
                ):
                    errors.setdefault(str(s_index), {"items": {}})["items"][str(i_index)] = {
                        "average_price": [_("This asset is not in the analysis's vertical.")]
                    }
        if errors:
            raise serializers.ValidationError({"scenarios": errors})

    def to_representation(self, instance):
        data = super().to_representation(instance)
        scenarios = list(instance.scenarios.all())
        items = {s.pk: list(s.items.all()) for s in scenarios}
        prices = current_prices(i.price_lineage for its in items.values() for i in its)
        ctx = Context(self.context.get("request"))
        data["scenarios"] = [
            {
                "id": s.id,
                "name": s.name,
                # Official name: term + name ("36 Months - Desktops", "60 Months")
                "title": s.title,
                "term_months": s.term_months,
                "scope": s.scope,
                **scenario_payload(
                    s.term_months,
                    [stored_item(i) for i in items[s.pk]],
                    prices,
                    ctx,
                    (instance.vertical_id, instance.sub_vertical_id),
                ),
            }
            for s in scenarios
        ]
        # Some average price used is past its validity: the analysis may be out of date
        data["is_outdated"] = any(s["has_expired"] for s in data["scenarios"])
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
                    unit_value=item["unit_value"],
                    efmv_value=item.get("efmv_value"),
                    service_name=(item.get("service") or {}).get("name", ""),
                    service_value=(item.get("service") or {}).get("value"),
                    service_mode=(item.get("service") or {}).get("mode", ServiceMode.ADD),
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
                        updated_by=self.context["request"].user,
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
            instance.updated_by = self.context["request"].user
            instance.save()
            if scenarios is not None:
                self._save_scenarios(instance, scenarios)
        return instance


class EfmvAnalysisListSerializer(serializers.ModelSerializer):
    """An analysis as listed: code, customer, account manager, its scenarios' names, created and
    last updated (when and by whom)."""

    code = serializers.CharField(read_only=True)
    account_manager_detail = serializers.SerializerMethodField()
    customer_detail = serializers.SerializerMethodField()
    scenario_names = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    updated_by_name = serializers.SerializerMethodField()

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
            "updated_at",
            "updated_by_name",
        ]
        read_only_fields = fields

    get_account_manager_detail = EfmvAnalysisSerializer.get_account_manager_detail
    get_customer_detail = EfmvAnalysisSerializer.get_customer_detail
    get_created_by_name = EfmvAnalysisSerializer.get_created_by_name

    def get_updated_by_name(self, obj) -> str | None:
        user = obj.updated_by or obj.created_by
        return full_name_in(self.context, user) if user else None

    def get_scenario_names(self, obj) -> list[str]:
        return [s.title for s in obj.scenarios.all()]


class ScenarioPreviewSerializer(serializers.Serializer):
    """The figures of a scenario being edited (nothing saved): the form never computes them."""

    term_months = serializers.IntegerField(min_value=1, max_value=MAX_TERM_MONTHS)
    vertical = serializers.IntegerField(required=False, allow_null=True, default=None)
    sub_vertical = serializers.IntegerField(required=False, allow_null=True, default=None)
    items = ItemInputSerializer(many=True)

    def to_representation(self, instance):
        items = [
            {
                "lineage": i["average_price"].lineage,
                "quantity": i["quantity"],
                "unit_value": i.get("unit_value"),
                "efmv_value": i.get("efmv_value"),
                "efmv_percent": i.get("efmv_percent"),
                "service": i.get("service"),
            }
            for i in instance["items"]
        ]
        prices = current_prices(item["lineage"] for item in items)
        scope = (instance.get("vertical"), instance.get("sub_vertical"))
        ctx = Context(self.context.get("request"))
        return scenario_payload(instance["term_months"], items, prices, ctx, scope)


# Silence "imported but unused" for names used only in type contexts
