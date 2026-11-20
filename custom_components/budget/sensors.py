"""Sensor platform for the Budżet domowy integration."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NAME


def _device_info(entry) -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": entry.title,
        "manufacturer": "ravek71",
        "model": NAME,
    }


def _fresh_cat(coordinator: Any, key: str) -> dict[str, Any] | None:
    """Look up a category in the latest coordinator data (never a stale snapshot)."""
    for cat in coordinator.data["categories"]:
        if cat["key"] == key:
            return cat
    return None


class BaseBudgetSensor(SensorEntity):
    """Common base: coordinator data, device info, Polish unit."""

    _attr_native_unit_of_measurement = "zł"
    _attr_has_entity_name = True

    def __init__(self, entry, coordinator, unique_suffix: str, name: str) -> None:
        super().__init__()
        self.entry = entry
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}:{unique_suffix}"
        self._attr_name = name
        self._attr_device_info = _device_info(entry)

    @property
    def coordinator_data(self) -> dict[str, Any]:
        return self.coordinator.data

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success


class MonthAmountSensor(BaseBudgetSensor):
    """Current-month income or expenses."""

    def __init__(self, entry, coordinator, unique_suffix, name, key: str, icon: str) -> None:
        super().__init__(entry, coordinator, unique_suffix, name)
        self._key = key
        self._attr_icon = icon

    @property
    def native_value(self) -> float | None:
        if not self.available:
            return None
        return self.coordinator_data["summary"][self._key]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        s = self.coordinator_data["summary"]
        cats = {
            "wpływy" if c["kind"] == "income" else "wydatki": c["name"]
            for c in self.coordinator_data["categories"]
        }
        return {
            "rozbicie": {cats.get(k, k): v for k, v in s["by_category"].items()},
            "wpływy": s["income"],
            "wydatki": s["expenses"],
            "bilans": s["balance"],
            "budżet": self.coordinator_data["total_budget"],
        }


class BalanceSensor(BaseBudgetSensor):
    def __init__(self, entry, coordinator, unique_suffix, name) -> None:
        super().__init__(entry, coordinator, unique_suffix, name)
        self._attr_icon = "mdi:scale-balance"

    @property
    def native_value(self) -> float | None:
        if not self.available:
            return None
        return self.coordinator_data["summary"]["balance"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        m = self.coordinator_data["summary"]
        return {"wpływy": m["income"], "wydatki": m["expenses"]}


class RemainingSensor(BaseBudgetSensor):
    """Planned monthly budget minus actual expenses (negative = over)."""

    def __init__(self, entry, coordinator, unique_suffix, name) -> None:
        super().__init__(entry, coordinator, unique_suffix, name)
        self._attr_icon = "mdi:wallet"

    @property
    def native_value(self) -> float | None:
        if not self.available:
            return None
        budget = self.coordinator_data["total_budget"]
        if budget <= 0:
            return None
        return round(budget - self.coordinator_data["summary"]["expenses"], 2)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "budżet": self.coordinator_data["total_budget"],
            "wydatki": self.coordinator_data["summary"]["expenses"],
        }


class PrevMonthSensor(BaseBudgetSensor):
    """Closed previous month — gives the History panel a monthly series."""

    def __init__(self, entry, coordinator, unique_suffix, name, key: str, icon: str) -> None:
        super().__init__(entry, coordinator, unique_suffix, name)
        self._key = key
        self._attr_icon = icon

    @property
    def native_value(self) -> float | None:
        if not self.available:
            return None
        return self.coordinator_data["prev"][self._key]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "rok": self.coordinator_data["prev_year"],
            "miesiąc": self.coordinator_data["prev_month"],
        }


class CategoryAmountSensor(BaseBudgetSensor):
    """This month's amount for one category (0 when no transactions)."""

    def __init__(self, entry, coordinator, cat: dict[str, Any]) -> None:
        key = cat["key"]
        label = "Wpływy" if cat["kind"] == "income" else "Wydatki"
        super().__init__(entry, coordinator, f"cat:{key}", f"{label}: {cat['name']}")
        self._cat_key = key
        self._cat = cat
        self._attr_icon = "mdi:cash-plus" if cat["kind"] == "income" else "mdi:cash-minus"

    @property
    def native_value(self) -> float | None:
        if not self.available:
            return None
        return self.coordinator_data["summary"]["by_category"].get(self._cat_key, 0.0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        cat = _fresh_cat(self.coordinator, self._cat_key) or self._cat
        return {
            "kategoria": cat["key"],
            "nazwa": cat["name"],
            "typ": cat["kind"],
            "stała": bool(cat["recurring"]),
            "budżet_kategorii": cat["monthly_budget"],
        }


class CategoryRemainingSensor(BaseBudgetSensor):
    """Category budget minus spent; unknown when no budget is planned."""

    def __init__(self, entry, coordinator, cat: dict[str, Any]) -> None:
        key = cat["key"]
        super().__init__(entry, coordinator, f"cat:{key}:remaining", f"Pozostało: {cat['name']}")
        self._cat_key = key
        self._cat = cat
        self._attr_icon = "mdi:wallet-check"

    @property
    def native_value(self) -> float | None:
        if not self.available:
            return None
        cat = _fresh_cat(self.coordinator, self._cat_key) or self._cat
        budget = cat["monthly_budget"]
        if budget <= 0:
            return None
        spent = self.coordinator_data["summary"]["by_category"].get(self._cat_key, 0.0)
        return round(budget - spent, 2)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[SensorEntity] = [
        MonthAmountSensor(entry, coordinator, "income", "Wpływy (miesiąc)", "income", "mdi:cash-plus"),
        MonthAmountSensor(entry, coordinator, "expenses", "Wydatki (miesiąc)", "expenses", "mdi:cash-minus"),
        BalanceSensor(entry, coordinator, "balance", "Bilans (miesiąc)"),
        RemainingSensor(entry, coordinator, "remaining", "Pozostało z budżetu"),
        PrevMonthSensor(entry, coordinator, "income_prev", "Wpływy (poprzedni miesiąc)", "income", "mdi:calendar-month"),
        PrevMonthSensor(entry, coordinator, "expenses_prev", "Wydatki (poprzedni miesiąc)", "expenses", "mdi:calendar-month"),
    ]
    for cat in coordinator.data["categories"]:
        entities.append(CategoryAmountSensor(entry, coordinator, cat))
        entities.append(CategoryRemainingSensor(entry, coordinator, cat))
    async_add_entities(entities)
