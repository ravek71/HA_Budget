"""Budżet domowy — budget planning integration for Home Assistant.

Stores income/expense categories, transactions and planned budgets in a
per-entry SQLite file. Entities:
- sensors:  month income/expenses/balance/remaining, previous month,
  per-category amount and remaining (vs planned category budget),
- numbers:  total monthly budget and per-category planned budgets.
History:    all data stays in the database; the ``get_history`` service
returns the last 12 months plus a month's detail, and previous-month
sensors make the HA History panel show a monthly series.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Optional

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady, ServiceValidationError
from homeassistant.helpers.event import async_track_point_in_utc_time
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator
from homeassistant.util import dt as dt_util

from .const import CONF_AUTO_RECURRING, DEFAULT_AUTO_RECURRING, DOMAIN
from .data import BudgetData

log = logging.getLogger(__package__)

PLATFORMS = [Platform.SENSOR, Platform.NUMBER]

SERVICE_ADD_CATEGORY = "add_category"
SERVICE_UPDATE_CATEGORY = "update_category"
SERVICE_REMOVE_CATEGORY = "remove_category"
SERVICE_ADD_TRANSACTION = "add_transaction"
SERVICE_DELETE_TRANSACTION = "delete_transaction"
SERVICE_SET_TOTAL_BUDGET = "set_total_budget"
SERVICE_SET_CATEGORY_BUDGET = "set_category_budget"
SERVICE_GET_HISTORY = "get_history"


class BudgetCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Caches the current month summary, previous month and categories."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, data: BudgetData) -> None:
        super().__init__(hass, log, name=f"{DOMAIN}:{entry.entry_id[:8]}", update_interval=None)
        self._data = data
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        now = dt_util.now()
        d = self._data
        prev_year, prev_month = (now.year - 1, 12) if now.month == 1 else (now.year, now.month - 1)
        month = await self.hass.async_add_executor_job(d.month_summary, now.year, now.month)
        prev = await self.hass.async_add_executor_job(d.month_summary, prev_year, prev_month)
        return {
            "year": now.year,
            "month": now.month,
            "prev_year": prev_year,
            "prev_month": prev_month,
            "summary": month,
            "prev": prev,
            "categories": await self.hass.async_add_executor_job(d.categories),
            "total_budget": await self.hass.async_add_executor_job(d.get_total_budget),
        }


# ------------------------------------------------------------------ setup


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Register services (valid entries at call time)."""
    hass.services.async_register(DOMAIN, SERVICE_ADD_CATEGORY, _svc_add_category, schema=_SCHEMA_ADD_CATEGORY)
    hass.services.async_register(DOMAIN, SERVICE_UPDATE_CATEGORY, _svc_update_category, schema=_SCHEMA_UPDATE_CATEGORY)
    hass.services.async_register(DOMAIN, SERVICE_REMOVE_CATEGORY, _svc_remove_category, schema=_SCHEMA_REMOVE_CATEGORY)
    hass.services.async_register(DOMAIN, SERVICE_ADD_TRANSACTION, _svc_add_transaction, schema=_SCHEMA_ADD_TRANSACTION)
    hass.services.async_register(DOMAIN, SERVICE_DELETE_TRANSACTION, _svc_delete_transaction, schema=_SCHEMA_DELETE_TRANSACTION)
    hass.services.async_register(DOMAIN, SERVICE_SET_TOTAL_BUDGET, _svc_set_total_budget, schema=_SCHEMA_SET_TOTAL_BUDGET)
    hass.services.async_register(DOMAIN, SERVICE_SET_CATEGORY_BUDGET, _svc_set_category_budget, schema=_SCHEMA_SET_CATEGORY_BUDGET)
    hass.services.async_register(DOMAIN, SERVICE_GET_HISTORY, _svc_get_history, schema=_SCHEMA_GET_HISTORY)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    path = hass.config.path(f"budget_{entry.entry_id}.db")
    data = BudgetData(path)
    coordinator = BudgetCoordinator(hass, entry, data)
    try:
        await coordinator.async_refresh()
    except Exception as err:  # noqa: BLE001
        data.close()
        raise ConfigEntryNotReady(f"Nie udało się otworzyć bazy danych: {err}") from err

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    entry.async_on_unload(_schedule_month_rollover(hass, entry, coordinator, data))
    log.info("%s: wpis %s załadowany (baza: %s)", DOMAIN, entry.title, path)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    if await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        info = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if info is not None:
            info._data.close()
    return True


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Keep the database file — the user's history must survive re-add."""
    info = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if info is not None:
        info._data.close()


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    await coordinator.async_refresh()


def _schedule_month_rollover(
    hass: HomeAssistant, entry: ConfigEntry, coordinator: BudgetCoordinator, data: BudgetData
) -> Callable[[], None]:
    """At local 00:05 on each first of month: book recurring expenses, refresh."""
    zone = dt_util.get_time_zone(hass.config.time_zone)

    async def _handle(now: datetime) -> None:
        try:
            if entry.data.get(CONF_AUTO_RECURRING, DEFAULT_AUTO_RECURRING):
                added = await hass.async_add_executor_job(data.apply_recurring, dt_util.now().date())
                if added:
                    log.info("Wydatki stałe: dodano %d transakcji", added)
            await coordinator.async_refresh()
        except Exception:  # noqa: BLE001
            log.exception("Job zmiany miesiąca nie powiódł się")
        _schedule_next()

    def _next_first(now: datetime) -> datetime:
        year, month = (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
        local = datetime(year, month, 1, 0, 5, tzinfo=zone)
        return dt_util.as_utc(local)

    cancel: Optional[Callable[[], None]] = None

    def _schedule_next() -> None:
        nonlocal cancel
        cancel = async_track_point_in_utc_time(
            hass, _handle, _next_first(dt_util.now())
        )

    _schedule_next()
    return lambda: cancel and cancel()


# --------------------------------------------------------------- services


def _entry_and_coordinator(
    hass: HomeAssistant, entry_id: Optional[str]
) -> tuple[ConfigEntry, BudgetCoordinator]:
    entries = hass.config_entries.async_loaded_entries(DOMAIN)
    if entry_id:
        for ent in entries:
            if ent.entry_id == entry_id:
                return ent, hass.data[DOMAIN][entry_id]
        raise ServiceValidationError("Nie znaleziono wpisu konfiguracji o podanym ID")
    if len(entries) == 1:
        ent = next(iter(entries))
        return ent, hass.data[DOMAIN][ent.entry_id]
    if not entries:
        raise ServiceValidationError("Brak aktywnego wpisu 'Budżet domowy'")
    raise ServiceValidationError("Jest kilka wpisów — podaj config_entry_id")


async def _refresh(hass: HomeAssistant, coordinator: BudgetCoordinator) -> None:
    await coordinator.async_refresh()


async def _reload_entities(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Re-create sensor/number entities after the category list changes."""
    await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


async def _run(hass: HomeAssistant, fn: Callable, *args: Any) -> Any:
    try:
        return await hass.async_add_executor_job(fn, *args)
    except ValueError as err:
        raise ServiceValidationError(str(err)) from err


async def _svc_add_category(hass: HomeAssistant, call) -> None:
    entry, coordinator = _entry_and_coordinator(hass, call.data.get("config_entry_id"))
    await _run(
        coordinator._data.add_category,
        call.data["name"],
        call.data.get("kind", "expense"),
        call.data.get("recurring", False),
        call.data.get("monthly_budget", 0.0),
    )
    await _refresh(hass, coordinator)
    await _reload_entities(hass, entry)


async def _svc_update_category(hass: HomeAssistant, call) -> None:
    entry, coordinator = _entry_and_coordinator(hass, call.data.get("config_entry_id"))
    await _run(
        coordinator._data.update_category,
        call.data["category"],
        call.data.get("name"),
        call.data.get("kind"),
        call.data.get("recurring"),
        call.data.get("monthly_budget"),
    )
    await _refresh(hass, coordinator)
    await _reload_entities(hass, entry)


async def _svc_remove_category(hass: HomeAssistant, call) -> None:
    entry, coordinator = _entry_and_coordinator(hass, call.data.get("config_entry_id"))
    await _run(coordinator._data.remove_category, call.data["category"])
    await _refresh(hass, coordinator)
    await _reload_entities(hass, entry)


async def _svc_add_transaction(hass: HomeAssistant, call) -> None:
    _entry, coordinator = _entry_and_coordinator(hass, call.data.get("config_entry_id"))
    await _run(
        coordinator._data.add_transaction,
        call.data["category"],
        call.data["amount"],
        call.data.get("date"),
        call.data.get("note", ""),
    )
    await _refresh(hass, coordinator)


async def _svc_delete_transaction(hass: HomeAssistant, call) -> None:
    _entry, coordinator = _entry_and_coordinator(hass, call.data.get("config_entry_id"))
    if not await _run(coordinator._data.delete_transaction, call.data["id"]):
        raise ServiceValidationError(f"Brak transakcji o ID {call.data['id']}")
    await _refresh(hass, coordinator)


async def _svc_set_total_budget(hass: HomeAssistant, call) -> None:
    _entry, coordinator = _entry_and_coordinator(hass, call.data.get("config_entry_id"))
    await _run(coordinator._data.set_total_budget, call.data["value"])
    await _refresh(hass, coordinator)


async def _svc_set_category_budget(hass: HomeAssistant, call) -> None:
    _entry, coordinator = _entry_and_coordinator(hass, call.data.get("config_entry_id"))
    await _run(
        coordinator._data.update_category,
        call.data["category"],
        monthly_budget=call.data["value"],
    )
    await _refresh(hass, coordinator)


async def _svc_get_history(hass: HomeAssistant, call) -> dict[str, Any]:
    _entry, coordinator = _entry_and_coordinator(hass, call.data.get("config_entry_id"))
    data = coordinator._data
    now = dt_util.now()
    year = call.data.get("year") or now.year
    month = call.data.get("month") or now.month

    months: list[dict[str, Any]] = []
    for i in range(11, -1, -1):
        y, m = now.year, now.month - i
        while m < 1:
            m += 12
            y -= 1
        months.append(
            await _run(data.month_summary, y, m)
            | {"year": y, "month": m, "budget": await _run(data.get_total_budget)}
        )

    detail = await _run(data.month_summary, year, month)
    detail["year"] = year
    detail["month"] = month
    cat_names = {c["key"]: c["name"] for c in coordinator.data["categories"]}
    detail["transactions"] = [
        {**tx, "category": cat_names.get(tx["category_key"], tx["category_key"])}
        for tx in await _run(data.transactions, year, month)
    ]
    return {"months": months, "month": detail, "total_budget": await _run(data.get_total_budget)}


# service schemas (imported lazily below to avoid a circular import)
from homeassistant.helpers import config_validation as cv  # noqa: E402
import voluptuous as vol  # noqa: E402

_CATEGORY = vol.In(["income", "expense"])

_SCHEMA_ADD_CATEGORY = vol.Schema(
    {
        vol.Required("name"): cv.string,
        vol.Optional("kind", default="expense"): _CATEGORY,
        vol.Optional("recurring", default=False): cv.boolean,
        vol.Optional("monthly_budget", default=0.0): cv.positive_float,
        vol.Optional("config_entry_id"): cv.string,
    }
)
_SCHEMA_UPDATE_CATEGORY = vol.Schema(
    {
        vol.Required("category"): cv.string,
        vol.Optional("name"): cv.string,
        vol.Optional("kind"): _CATEGORY,
        vol.Optional("recurring"): cv.boolean,
        vol.Optional("monthly_budget"): cv.positive_float,
        vol.Optional("config_entry_id"): cv.string,
    }
)
_SCHEMA_REMOVE_CATEGORY = vol.Schema(
    {
        vol.Required("category"): cv.string,
        vol.Optional("config_entry_id"): cv.string,
    }
)
_SCHEMA_ADD_TRANSACTION = vol.Schema(
    {
        vol.Required("category"): cv.string,
        vol.Required("amount"): cv.positive_float,
        vol.Optional("date"): cv.string,  # YYYY-MM-DD, default: today
        vol.Optional("note"): cv.string,
        vol.Optional("config_entry_id"): cv.string,
    }
)
_SCHEMA_DELETE_TRANSACTION = vol.Schema(
    {
        vol.Required("id"): cv.positive_int,
        vol.Optional("config_entry_id"): cv.string,
    }
)
_SCHEMA_SET_TOTAL_BUDGET = vol.Schema(
    {
        vol.Required("value"): cv.positive_float,
        vol.Optional("config_entry_id"): cv.string,
    }
)
_SCHEMA_SET_CATEGORY_BUDGET = vol.Schema(
    {
        vol.Required("category"): cv.string,
        vol.Required("value"): cv.positive_float,
        vol.Optional("config_entry_id"): cv.string,
    }
)
_SCHEMA_GET_HISTORY = vol.Schema(
    {
        vol.Optional("year"): cv.positive_int,
        vol.Optional("month"): cv.range(1, 13),
        vol.Optional("config_entry_id"): cv.string,
    }
)
