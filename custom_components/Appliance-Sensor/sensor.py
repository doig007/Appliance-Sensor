import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_ENTITY_ID, STATE_UNKNOWN, ENERGY_KILO_WATT_HOUR
from homeassistant.helpers.event import async_track_time_change
from homeassistant.core import HomeAssistant

from .const import CONF_THRESHOLD, CONF_HYSTERESIS_TIME

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry, async_add_entities):
    _LOGGER.debug("Setting up sensors for Appliance Sensor integration")
    devices = config_entry.data["devices"]

    sensors = []
    for device in devices:
        entity_id = device[CONF_ENTITY_ID]
        threshold = device[CONF_THRESHOLD]
        hysteresis_time = timedelta(seconds=device[CONF_HYSTERESIS_TIME])
        appliance_sensor = ApplianceSensor(hass, entity_id, threshold, hysteresis_time, config_entry)
        counter_sensor = ApplianceOnCounterSensor(hass, entity_id, config_entry)
        consumption_sensor = ApplianceConsumptionSensor(hass, entity_id, config_entry)
        peak_power_sensor = AppliancePeakPowerSensor(hass, entity_id, config_entry)
        runtime_sensor = ApplianceRuntimeSensor(hass, entity_id, config_entry)
        sensors.append(appliance_sensor)
        sensors.append(counter_sensor)
        sensors.append(consumption_sensor)
        sensors.append(peak_power_sensor)
        sensors.append(runtime_sensor)
        # Link the appliance sensor to the other sensors
        appliance_sensor.set_counter_sensor(counter_sensor)
        appliance_sensor.set_consumption_sensor(consumption_sensor)
        appliance_sensor.set_peak_power_sensor(peak_power_sensor)
        appliance_sensor.set_runtime_sensor(runtime_sensor)

    async_add_entities(sensors, update_before_add=True)

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
        self._consumption_sensor = None
        self._peak_power_sensor = None
        self._runtime_sensor = None
        self._config_entry = config_entry

    def set_counter_sensor(self, counter_sensor):
        self._counter_sensor = counter_sensor

    def set_consumption_sensor(self, consumption_sensor):
        self._consumption_sensor = consumption_sensor

    def set_peak_power_sensor(self, peak_power_sensor):
        self._peak_power_sensor = peak_power_sensor

    def set_runtime_sensor(self, runtime_sensor):
        self._runtime_sensor = runtime_sensor

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
                        if self._consumption_sensor:
                            self._consumption_sensor.update_consumption(self._current_power, current_time)
                        if self._peak_power_sensor:
                            self._peak_power_sensor.update_peak_power(self._current_power)
                        if self._runtime_sensor:
                            self._runtime_sensor.start_timer()
                else:
                    if self._state == "on":
                        if self._below_threshold_since is None:
                            self._below_threshold_since = current_time
                        else:
                            elapsed = current_time - self._below_threshold_since
                            if elapsed >= self._hysteresis_time:
                                self._state = "off"
                                if self._runtime_sensor:
                                    self._runtime_sensor.stop_timer()
            except ValueError:
                _LOGGER.error("Unable to convert state to float: %s", state.state)
                self._state = "unknown"
        else:
            self._state = "unknown"

class ApplianceOnCounterSensor(SensorEntity):

    def __init__(self, hass, entity_id, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._count = 0
        self._config_entry = config_entry
        self._reset_at_midnight()

    @property
    def name(self):
        return f"Appliance On Counter {self._entity_id}"

    @property
    def state(self):
        return self._count

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_appliance_counter"

    @property
    def should_poll(self):
        return False

    def increment_count(self):
        self._count += 1
        self.async_write_ha_state()

    def _reset_at_midnight(self):
        async_track_time_change(self._hass, self._reset_counter, hour=0, minute=0, second=0)

    def _reset_counter(self, time):
        self._count = 0
        self.async_write_ha_state()

class ApplianceConsumptionSensor(SensorEntity):

    def __init__(self, hass, entity_id, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._config_entry = config_entry
        self._consumption = 0.0  # in kWh
        self._last_update = datetime.now()
        self._reset_at_midnight()

    @property
    def name(self):
        return f"Appliance Consumption {self._entity_id}"

    @property
    def state(self):
        return self._consumption

    @property
    def unit_of_measurement(self):
        return ENERGY_KILO_WATT_HOUR

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_appliance_consumption"

    @property
    def should_poll(self):
        return False

    def update_consumption(self, current_power, current_time):
        time_diff = (current_time - self._last_update).total_seconds() / 3600.0  # hours
        self._consumption += (current_power * time_diff) / 1000.0  # kWh
        self._last_update = current_time
        self.async_write_ha_state()

    def _reset_at_midnight(self):
        async_track_time_change(self._hass, self._reset_consumption, hour=0, minute=0, second=0)

    def _reset_consumption(self, time):
        self._consumption = 0.0
        self._last_update = datetime.now()
        self.async_write_ha_state()

class AppliancePeakPowerSensor(SensorEntity):

    def __init__(self, hass, entity_id, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._config_entry = config_entry
        self._peak_power = 0.0
        self._reset_at_midnight()

    @property
    def name(self):
        return f"Appliance Peak Power {self._entity_id}"

    @property
    def state(self):
        return self._peak_power

    @property
    def unit_of_measurement(self):
        return "W"

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_appliance_peak_power"

    @property
    def should_poll(self):
        return False

    def update_peak_power(self, current_power):
        if current_power > self._peak_power:
            self._peak_power = current_power
            self.async_write_ha_state()

    def _reset_at_midnight(self):
        async_track_time_change(self._hass, self._reset_peak_power, hour=0, minute=0, second=0)

    def _reset_peak_power(self, time):
        self._peak_power = 0.0
        self.async_write_ha_state()

class ApplianceRuntimeSensor(SensorEntity):

    def __init__(self, hass, entity_id, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._config_entry = config_entry
        self._runtime = 0  # in seconds
        self._is_running = False
        self._last_start_time = None
        self._reset_at_midnight()

    @property
    def name(self):
        return f"Appliance Runtime {self._entity_id}"

    @property
    def state(self):
        return self._runtime

    @property
    def unit_of_measurement(self):
        return "s"

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_appliance_runtime"

    @property
    def should_poll(self):
        return False

    def start_timer(self):
        if not self._is_running:
            self._is_running = True
            self._last_start_time = datetime.now()

    def stop_timer(self):
        if self._is_running:
            self._is_running = False
            elapsed = (datetime.now() - self._last_start_time).total_seconds()
            self._runtime += elapsed
            self.async_write_ha_state()

    def _reset_at_midnight(self):
        async_track_time_change(self._hass, self._reset_runtime, hour=0, minute=0, second=0)

    def _reset_runtime(self, time):
        self._runtime = 0
        self._is_running = False
        self._last_start_time = None
        self.async_write_ha_state()
