import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    EntitySelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode
)
from .const import DOMAIN, CONF_ENTITY_ID, CONF_THRESHOLD, CONF_HYSTERESIS_TIME
import logging

_LOGGER = logging.getLogger(__name__)

class ApplianceSensorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def async_step_user(self, user_input=None):
        _LOGGER.debug("Starting user step of Appliance Sensor config flow")
        errors = {}
        if user_input is not None:
            try:
                entity_id = user_input[CONF_ENTITY_ID]
                threshold = float(user_input[CONF_THRESHOLD])
                hysteresis_time = int(user_input[CONF_HYSTERESIS_TIME])

                devices = [{
                    CONF_ENTITY_ID: entity_id,
                    CONF_THRESHOLD: threshold,
                    CONF_HYSTERESIS_TIME: hysteresis_time
                }]

                _LOGGER.debug(f"User input: {user_input}")
                return self.async_create_entry(title="Appliance Sensor", data={"devices": devices})
            except Exception as e:
                _LOGGER.error(f"Error processing user input: {e}")
                errors["base"] = "invalid_input"

        return self.async_show_form(
            step_id="user",
            data_schema=self._get_schema(),
            errors=errors
        )

    def _get_schema(self):
        return vol.Schema({
            vol.Required(CONF_ENTITY_ID): EntitySelector(),
            vol.Required(CONF_THRESHOLD): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    step=0.1,
                    mode=NumberSelectorMode.BOX
                )
            ),
            vol.Required(CONF_HYSTERESIS_TIME): NumberSelector(
                NumberSelectorConfig(
                    min=0,
                    step=1,
                    mode=NumberSelectorMode.BOX
                )
            )
        })

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return ApplianceSensorOptionsFlow(config_entry)

class ApplianceSensorOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        _LOGGER.debug("Starting options flow of Appliance Sensor config")
        errors = {}
        if user_input is not None:
            try:
                entity_id = user_input[CONF_ENTITY_ID]
                threshold = float(user_input[CONF_THRESHOLD])
                hysteresis_time = int(user_input[CONF_HYSTERESIS_TIME])

                devices = [{
                    CONF_ENTITY_ID: entity_id,
                    CONF_THRESHOLD: threshold,
                    CONF_HYSTERESIS_TIME: hysteresis_time
                }]

                _LOGGER.debug(f"User input: {user_input}")
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data={"devices": devices}
                )
                return self.async_create_entry(title="", data={})
            except Exception as e:
                _LOGGER.error(f"Error processing options input: {e}")
                errors["base"] = "invalid_input"

        device = self.config_entry.data["devices"][0]
        return self.async_show_form(
            step_id="init",
            data_schema=self._get_options_schema(device),
            errors=errors
        )

    def _get_options_schema(self, device=None):
        if device:
            return vol.Schema({
                vol.Required(CONF_ENTITY_ID, default=device[CONF_ENTITY_ID]): EntitySelector(),
                vol.Required(CONF_THRESHOLD, default=device[CONF_THRESHOLD]): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        step=0.1,
                        mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_HYSTERESIS_TIME, default=device[CONF_HYSTERESIS_TIME]): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        step=1,
                        mode=NumberSelectorMode.BOX
                    )
                )
            })
        else:
            return vol.Schema({
                vol.Required(CONF_ENTITY_ID): EntitySelector(),
                vol.Required(CONF_THRESHOLD): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        step=0.1,
                        mode=NumberSelectorMode.BOX
                    )
                ),
                vol.Required(CONF_HYSTERESIS_TIME): NumberSelector(
                    NumberSelectorConfig(
                        min=0,
                        step=1,
                        mode=NumberSelectorMode.BOX
                    )
                )
            })
