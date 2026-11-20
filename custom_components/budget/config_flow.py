"""Config flow for the Budżet domowy integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_AUTO_RECURRING,
    CONF_NAME,
    CONF_NAME_DEFAULT,
    DEFAULT_AUTO_RECURRING,
    DOMAIN,
)


class BudgetConfigFlow(ConfigFlow, domain=DOMAIN):
    """Single-entry flow: one budget per HA installation."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            if self._async_current_entries():
                return self.async_abort(reason="single_instance_allowed")
            name = (user_input.get(CONF_NAME) or "").strip() or CONF_NAME_DEFAULT
            return self.async_create_entry(
                title=name,
                data={
                    CONF_NAME: name,
                    CONF_AUTO_RECURRING: bool(
                        user_input.get(CONF_AUTO_RECURRING, DEFAULT_AUTO_RECURRING)
                    ),
                },
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_NAME, default=CONF_NAME_DEFAULT): vol.Coerce(str),
                    vol.Required(CONF_AUTO_RECURRING, default=DEFAULT_AUTO_RECURRING): vol.Coerce(bool),
                }
            ),
        )
