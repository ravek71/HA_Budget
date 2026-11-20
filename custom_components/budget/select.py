"""Select platform — staging category for the "add transaction" card."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NAME


def _device_info(entry) -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": entry.title,
        "manufacturer": "ravek71",
        "model": NAME,
    }


class DraftCategorySelect(SelectEntity):
    """Staging category for the dashboard "add transaction" card.

    Picking an option does NOT book anything — the button entity
    ("Dodaj transakcję") books the staged amount + category.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:tag-multiple-outline"

    def __init__(self, entry, coordinator) -> None:
        super().__init__()
        self.entry = entry
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}:draft_category"
        self._attr_name = "Kategoria do dodania"
        self._attr_device_info = _device_info(entry)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    def _name_to_key(self) -> dict[str, str]:
        """Map display name -> category key (disambiguates duplicate names)."""
        mapping: dict[str, str] = {}
        seen: dict[str, int] = {}
        for cat in self.coordinator.data["categories"]:
            name = cat["name"]
            if name in seen:
                seen[name] += 1
                name = f"{name} ({seen[name]})"
            else:
                seen[name] = 1
            mapping[name] = cat["key"]
        return mapping

    @property
    def select_options(self) -> list[str]:
        return list(self._name_to_key().keys())

    @property
    def native_value(self) -> str | None:
        if not self.available:
            return None
        key = self.coordinator.data["draft"]["category"]
        if not key:
            return None
        for name, k in self._name_to_key().items():
            if k == key:
                return name
        return None

    @callback
    def _after_change(self) -> None:
        self.coordinator.async_update_listeners()

    async def async_select_option(self, option: str) -> None:
        key = self._name_to_key().get(option)
        if key is None:
            return
        try:
            await self.hass.async_add_executor_job(
                self.coordinator.set_draft_category, key
            )
        except ValueError as err:
            raise ServiceValidationError(str(err)) from err
        self._after_change()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([DraftCategorySelect(entry, coordinator)])
