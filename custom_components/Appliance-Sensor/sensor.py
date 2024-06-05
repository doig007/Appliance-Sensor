import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_ENTITY_ID, STATE_UNKNOWN
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.typing import HomeAssistantType

from .const import CONF_THRESHOLD, CONF_HYSTERESIS_TIME

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistantType, config_entry, async_add_entities):
    _LOGGER.debug("Setting up sensors for Appliance Sensor integration")
    devices = config_entry.data["devices"]

    sensors = []
    for device in devices:
        entity_id = device[CONF_ENTITY_ID]
        threshold = device[CONF_THRESHOLD]
        hysteresis_time = timedelta(seconds=device[CONF_HYSTERESIS_TIME])
        power_sensor = ApplianceSensor(hass, entity_id, threshold, hysteresis_time)
        counter_sensor = ApplianceOnCounterSensor(hass, entity_id)
        sensors.append(power_sensor)
        sensors.append(counter_sensor)
        # Link the power sensor to the counter sensor
        power_sensor.set_counter_sensor(counter_sensor)

    async_add_entities(sensors, update_before_add=True)

class ApplianceSensor(SensorEntity):

    def __init__(self, hass, entity_id, threshold, hysteresis_time):
        self._hass = hass
        self._entity_id = entity_id
        self._threshold = threshold
        self._hysteresis_time = hysteresis_time
        self._state = "off"
        self._current_power = None
        self._below_threshold_since = None
        self._counter_sensor = None

    def set_counter_sensor(self, counter_sensor):
        self._counter_sensor = counter_sensor

    @property
    def name(self):
        return f"Appliance Sensor {self._entity_id}"

    @property
    def state(self):
        return self._state

    def update(self):
        _LOGGER.debug(f"Updating sensor {self._entity_id}")
        state = self._hass.states.get(self._entity_id)
        if state and state.state != STATE_UNKNOWN:
            try:
                power = float(state.state)
                self._current_power = power
                current_time = datetime.now()

                if power > self._threshold:
                    self._below_threshold_since = None
                    if self._state == "off":
                        self._state = "on"
                        if self._counter_sensor:
                            self._counter_sensor.increment_count()
                else:
                    if self._state == "on":
                        if self._below_threshold_since is None:
                            self._below_threshold_since = current_time
                        else:
                            elapsed = current_time - self._below_threshold_since
                            if elapsed >= self._hysteresis_time:
                                self._state = "off"
                    else:
                        self._state = "off"
            except ValueError:
                _LOGGER.error("Unable to convert state to float: %s", state.state)
                self._state = "unknown"
        else:
            self._state = "unknown"

class ApplianceOnCounterSensor(SensorEntity):

    def __init__(self, hass, entity_id):
        self._hass = hass
        self._entity_id = entity_id
        self._count = 0
        self._reset_at_midnight()

    @property
    def name(self):
        return f"Appliance On Counter {self._entity_id}"

    @property
    def state(self):
        return self._count

    def increment_count(self):
        self._count += 1
        self.async_write_ha_state()

    def _reset_at_midnight(self):
        async_track_time_change(self._hass, self._reset_counter, hour=0, minute=0, second=0)

    def _reset_counter(self, time):
        self._count = 0
        self.async_write_ha_state()
