import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change

from .const import CONF_THRESHOLD, CONF_HYSTERESIS_TIME

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    _LOGGER.debug("Setting up sensors for Appliance Sensor integration")
    devices = config_entry.data.get("devices", [])

    sensors = []
    for device in devices:
        entity_id = device.get(CONF_ENTITY_ID)
        threshold = device.get(CONF_THRESHOLD)
        hysteresis_time = timedelta(seconds=device.get(CONF_HYSTERESIS_TIME))
        
        appliance_sensor = ApplianceSensor(hass, entity_id, threshold, hysteresis_time, config_entry)
        counter_sensor = ApplianceSensorOnCounter(hass, entity_id, config_entry)
        
        sensors.append(appliance_sensor)
        sensors.append(counter_sensor)
        
        appliance_sensor.set_counter_sensor(counter_sensor)

    async_add_entities(sensors, update_before_add=True)
    _LOGGER.debug("Sensors added: %s", sensors)

class ApplianceSensor(SensorEntity):

    def __init__(self, hass, entity_id, threshold, hysteresis_time, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._threshold = threshold
        self._hysteresis_time = hysteresis_time
        self._state = "off"
        self._current_power = None
        self._below_threshold_since = None
        self._counter_sensor = None
        self._config_entry = config_entry
        _LOGGER.debug(f"Initialized ApplianceSensor for {entity_id}")

    def set_counter_sensor(self, counter_sensor):
        self._counter_sensor = counter_sensor
        _LOGGER.debug(f"Set counter sensor for {self._entity_id}")

    @property
    def name(self):
        return f"Appliance Sensor {self._entity_id}"

    @property
    def state(self):
        return self._state

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_appliance_sensor"

    @property
    def should_poll(self):
        return True

    def update(self):
        _LOGGER.debug(f"Updating sensor {self._entity_id}")
        state = self._hass.states.get(self._entity_id)
        if state is None:
            _LOGGER.error(f"Entity {self._entity_id} not found in Home Assistant states.")
            self._state = "unknown"
            return

        if state.state == STATE_UNKNOWN:
            _LOGGER.warning(f"State of entity {self._entity_id} is unknown.")
            self._state = "unknown"
            return

        try:
            power = float(state.state)
            self._current_power = power
            _LOGGER.debug(f"Power for {self._entity_id}: {power}")
            current_time = datetime.now()

            if power > self._threshold:
                if self._state == "off":
                    _LOGGER.debug(f"Power above threshold for {self._entity_id}: Turning ON")
                    self._state = "on"
                    self._below_threshold_since = None
                    if self._counter_sensor:
                        self._hass.async_add_job(self._counter_sensor.increment_count)
            else:
                if self._state == "on":
                    if self._below_threshold_since is None:
                        self._below_threshold_since = current_time
                    else:
                        elapsed = current_time - self._below_threshold_since
                        if elapsed >= self._hysteresis_time:
                            _LOGGER.debug(f"Power below threshold for {self._entity_id} for hysteresis time: Turning OFF")
                            self._state = "off"
                            self._below_threshold_since = None
        except ValueError:
            _LOGGER.error(f"Unable to convert state to float: {state.state} for {self._entity_id}")
            self._state = "unknown"

class ApplianceSensorOnCounter(SensorEntity):

    def __init__(self, hass, entity_id, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._count = 0
        self._config_entry = config_entry
        self._reset_at_midnight()
        _LOGGER.debug(f"Initialized ApplianceSensorOnCounter for {entity_id}")

    @property
    def name(self):
        return f"Appliance Sensor On Counter {self._entity_id}"

    @property
    def state(self):
        return self._count

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_appliance_counter"

    @property
    def should_poll(self):
        return False

    @callback
    def increment_count(self):
        _LOGGER.debug(f"Incrementing count for {self._entity_id}")
        self._count += 1
        self._hass.async_add_job(self.async_write_ha_state)

    def _reset_at_midnight(self):
        _LOGGER.debug(f"Setting up midnight reset for {self._entity_id}")
        async_track_time_change(self._hass, self._reset_counter, hour=0, minute=0, second=0)

    @callback
    def _reset_counter(self, time):
        _LOGGER.debug(f"Resetting count to 0 for {self._entity_id} at midnight")
        self._count = 0
        self._hass.async_add_job(self.async_write_ha_state)
