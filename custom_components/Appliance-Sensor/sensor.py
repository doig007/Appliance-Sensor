import logging
from datetime import datetime, timedelta

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.const import UnitOfEnergy
from homeassistant.components.history import get_significant_states

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
        counter_sensor = ApplianceSensorOnCounter(hass, entity_id, config_entry)
        peak_power_sensor = ApplianceSensorPeakPower(hass, entity_id, config_entry)
        energy_consumption_sensor = ApplianceSensorEnergyConsumption(hass, entity_id, config_entry)
        runtime_sensor = ApplianceSensorRuntime(hass, entity_id, config_entry)
        forecast_sensor = ApplianceSensorForecast(hass, entity_id, config_entry)
        
        sensors.append(appliance_sensor)
        sensors.append(counter_sensor)
        sensors.append(peak_power_sensor)
        sensors.append(energy_consumption_sensor)
        sensors.append(runtime_sensor)
        sensors.append(forecast_sensor)
        
        # Link sensors to the appliance sensor
        appliance_sensor.set_counter_sensor(counter_sensor)
        appliance_sensor.set_peak_power_sensor(peak_power_sensor)
        appliance_sensor.set_energy_consumption_sensor(energy_consumption_sensor)
        appliance_sensor.set_runtime_sensor(runtime_sensor)
        appliance_sensor.set_forecast_sensor(forecast_sensor)

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
        self._peak_power_sensor = None
        self._energy_consumption_sensor = None
        self._runtime_sensor = None
        self._forecast_sensor = None
        self._config_entry = config_entry

    def set_counter_sensor(self, counter_sensor):
        self._counter_sensor = counter_sensor

    def set_peak_power_sensor(self, peak_power_sensor):
        self._peak_power_sensor = peak_power_sensor

    def set_energy_consumption_sensor(self, energy_consumption_sensor):
        self._energy_consumption_sensor = energy_consumption_sensor

    def set_runtime_sensor(self, runtime_sensor):
        self._runtime_sensor = runtime_sensor

    def set_forecast_sensor(self, forecast_sensor):
        self._forecast_sensor = forecast_sensor

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
                _LOGGER.debug(f"Power for {self._entity_id}: {power}")
                current_time = datetime.now()

                if self._peak_power_sensor:
                    self._hass.async_add_job(self._peak_power_sensor.update_peak_power, power)

                if self._energy_consumption_sensor:
                    self._hass.async_add_job(self._energy_consumption_sensor.update_energy_consumption, power)

                if power > self._threshold:
                    if self._state == "off":
                        _LOGGER.debug(f"Power above threshold for {self._entity_id}: Turning ON")
                        self._state = "on"
                        self._below_threshold_since = None
                        if self._counter_sensor:
                            self._hass.async_add_job(self._counter_sensor.increment_count)
                        if self._runtime_sensor:
                            self._hass.async_add_job(self._runtime_sensor.start_timer)
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
                                if self._runtime_sensor:
                                    self._hass.async_add_job(self._runtime_sensor.stop_timer)
                    else:
                        self._below_threshold_since = None
            except ValueError:
                _LOGGER.error(f"Unable to convert state to float: {state.state} for {self._entity_id}")
                self._state = "unknown"
        else:
            _LOGGER.debug(f"State unknown or not available for {self._entity_id}")
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

class ApplianceSensorPeakPower(SensorEntity):

    def __init__(self, hass, entity_id, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._peak_power = 0.0
        self._config_entry = config_entry
        self._reset_at_midnight()

    @property
    def name(self):
        return f"Appliance Sensor Peak Power {self._entity_id}"

    @property
    def state(self):
        return self._peak_power

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_peak_power"

    @property
    def should_poll(self):
        return False

    @callback
    def update_peak_power(self, power):
        _LOGGER.debug(f"Updating peak power for {self._entity_id} with power: {power}")
        if power > self._peak_power:
            self._peak_power = power
            self._hass.async_add_job(self.async_write_ha_state)

    def _reset_at_midnight(self):
        _LOGGER.debug(f"Setting up midnight reset for peak power of {self._entity_id}")
        async_track_time_change(self._hass, self._reset_peak_power, hour=0, minute=0, second=0)

    @callback
    def _reset_peak_power(self, time):
        _LOGGER.debug(f"Resetting peak power to 0 for {self._entity_id} at midnight")
        self._peak_power = 0.0
        self._hass.async_add_job(self.async_write_ha_state)

class ApplianceSensorEnergyConsumption(SensorEntity):

    def __init__(self, hass, entity_id, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._energy_consumption = 0.0
        self._last_update = datetime.now()
        self._config_entry = config_entry
        self._reset_at_midnight()

    @property
    def name(self):
        return f"Appliance Sensor Energy Consumption {self._entity_id}"

    @property
    def state(self):
        return self._energy_consumption

    @property
    def unit_of_measurement(self):
        return UnitOfEnergy.KILO_WATT_HOUR

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_energy_consumption"

    @property
    def should_poll(self):
        return False

    @callback
    def update_energy_consumption(self, power):
        now = datetime.now()
        elapsed_hours = (now - self._last_update).total_seconds() / 3600.0
        self._energy_consumption += power * elapsed_hours / 1000.0  # kWh
        self._last_update = now
        self._hass.async_add_job(self.async_write_ha_state)

    def _reset_at_midnight(self):
        async_track_time_change(self._hass, self._reset_energy_consumption, hour=0, minute=0, second=0)

    @callback
    def _reset_energy_consumption(self, time):
        self._energy_consumption = 0.0
        self._hass.async_add_job(self.async_write_ha_state)

class ApplianceSensorRuntime(SensorEntity):

    def __init__(self, hass, entity_id, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._runtime = timedelta()
        self._last_start = None
        self._config_entry = config_entry
        self._reset_at_midnight()

    @property
    def name(self):
        return f"Appliance Sensor Runtime {self._entity_id}"

    @property
    def state(self):
        return str(self._runtime)

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_runtime"

    @property
    def should_poll(self):
        return False

    @callback
    def start_timer(self):
        if self._last_start is None:
            self._last_start = datetime.now()

    @callback
    def stop_timer(self):
        if self._last_start is not None:
            self._runtime += datetime.now() - self._last_start
            self._last_start = None
            self._hass.async_add_job(self.async_write_ha_state)

    def _reset_at_midnight(self):
        async_track_time_change(self._hass, self._reset_runtime, hour=0, minute=0, second=0)

    @callback
    def _reset_runtime(self, time):
        self._runtime = timedelta()
        self._hass.async_add_job(self.async_write_ha_state)

class ApplianceSensorForecast(SensorEntity):

    def __init__(self, hass, entity_id, config_entry):
        self._hass = hass
        self._entity_id = entity_id
        self._forecast = 0
        self._config_entry = config_entry
        self._reset_at_midnight()

    @property
    def name(self):
        return f"Appliance Sensor Forecast {self._entity_id}"

    @property
    def state(self):
        return self._forecast

    @property
    def unique_id(self):
        return f"{self._config_entry.entry_id}_{self._entity_id}_forecast"

    @property
    def should_poll(self):
        return False

    def update(self):
        self._hass.async_add_job(self._calculate_forecast)

    def _calculate_forecast(self):
        # This is a simplified forecasting logic. Replace with your own forecasting method.
        past_counts = self._get_historical_counts()
        if past_counts:
            self._forecast = int(np.mean(past_counts))
        self.async_write_ha_state()

    def _get_historical_counts(self):
        # Retrieve historical data from Home Assistant
        start_time = datetime.now() - timedelta(days=30)
        end_time = datetime.now()
        history = get_significant_states(self._hass, start_time, end_time, entity_ids=[self._entity_id])
        counts = [state.state for state in history.get(self._entity_id, []) if state.state.isdigit()]
        return list(map(int, counts))

    def _reset_at_midnight(self):
        async_track_time_change(self._hass, self._reset_forecast, hour=0, minute=0, second=0)

    @callback
    def _reset_forecast(self, time):
        self._forecast = 0
        self._hass.async_add_job(self.async_write_ha_state)
