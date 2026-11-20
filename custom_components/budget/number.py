"""Number platform for the Budżet domowy integration (planned budgets)."""

from __future__ import annotations

from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
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


class BaseBudgetNumber(NumberEntity):
    _attr_native_unit_of_measurement = "zł"
    _attr_has_entity_name = True
    _attr_min_value = 0.0
    _attr_max_value = 10_000_000.0
    _attr_step = 50.0
    _attr_mode = NumberMode.BOX

    def __init__(self, entry, coordinator, unique_suffix: str, name: str) -> None:
        super().__init__()
        self.entry = entry
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}:{unique_suffix}"
        self._attr_name = name
        self._attr_device_info = _device_info(entry)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    @callback
    def _after_change(self) -> None:
        self.coordinator.async_update_listeners()


class TotalBudgetNumber(BaseBudgetNumber):
    """Planned total budget for the month."""

    def __init__(self, entry, coordinator) -> None:
        super().__init__(entry, coordinator, "total_budget", "Budżet miesięczny (plan)")
        self._attr_icon = "mdi:target"

    @property
    def native_value(self) -> float | None:
        if not self.available:
            return None
        return self.coordinator.data["total_budget"]

    async def async_set_native_value(self, value: float) -> None:
        data = self.coordinator._data
        await self.hass.async_add_executor_job(data.set_total_budget, value)
        await self.coordinator.async_refresh()
        self._after_change()


class CategoryBudgetNumber(BaseBudgetNumber):
    """Planned budget for one category."""

    def __init__(self, entry, coordinator, cat: dict[str, Any]) -> None:
        super().__init__(
            entry, coordinator, f"cat:{cat['key']}:budget", f"Budżet: {cat['name']}"
        )
        self._cat_key = cat["key"]
        self._cat = cat
        self._attr_icon = "mdi:target-account"

    @property
    def native_value(self) -> float | None:
        if not self.available:
            return None
        cat = _fresh_cat(self.coordinator, self._cat_key) or self._cat
        return cat["monthly_budget"]

    async def async_set_native_value(self, value: float) -> None:
        data = self.coordinator._data
        await self.hass.async_add_executor_job(
            data.update_category, self._cat_key, monthly_budget=value
        )
        await self.coordinator.async_refresh()
        self._after_change()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[NumberEntity] = [TotalBudgetNumber(entry, coordinator)]
    for cat in coordinator.data["categories"]:
        entities.append(CategoryBudgetNumber(entry, coordinator, cat))
    async_add_entities(entities)
