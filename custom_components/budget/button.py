"""Button platform — "add transaction" action for the dashboard card."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, NAME

log = logging.getLogger(__package__)


def _device_info(entry) -> dict[str, Any]:
    return {
        "identifiers": {(DOMAIN, entry.entry_id)},
        "name": entry.title,
        "manufacturer": "ravek71",
        "model": NAME,
    }


class AddTransactionButton(ButtonEntity):
    """Books the staged amount + category, then clears the form.

    Companion to the "Kwota do dodania" (number) and
    "Kategoria do dodania" (select) staging entities.
    """

    _attr_has_entity_name = True
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, entry, coordinator) -> None:
        super().__init__()
        self.entry = entry
        self.coordinator = coordinator
        self._attr_unique_id = f"{entry.entry_id}:draft_add"
        self._attr_name = "Dodaj transakcję"
        self._attr_device_info = _device_info(entry)

    @property
    def available(self) -> bool:
        return self.coordinator.last_update_success

    async def async_press(self) -> None:
        draft = self.coordinator.data["draft"]
        amount = draft.get("amount") or 0.0
        key = draft.get("category")
        if amount <= 0:
            log.warning(
                "Dodaj transakcję: kwota = 0 — nic nie zapisano"
                " (najpierw ustaw encję „Kwota do dodania”)"
            )
            return
        if not key or self.coordinator._data.get_category(key) is None:
            log.warning(
                "Dodaj transakcję: brak wybranej kategorii"
                " (najpierw wybierz encję „Kategoria do dodania”)"
            )
            return
        await self.hass.async_add_executor_job(
            self.coordinator._data.add_transaction,
            key,
            amount,
            None,
            "Dodane z karty",
        )
        self.coordinator.clear_draft()
        await self.coordinator.async_refresh()


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([AddTransactionButton(entry, coordinator)])
