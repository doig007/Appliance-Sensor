# Appliance Sensor Custom Component for Home Assistant

This custom component for Home Assistant allows you to monitor the power usage of home appliances and count the number of times they have been turned on during the current day. The component includes two sensors:
- **Appliance Sensor**: Determines if the appliance is on or off based on a power threshold and hysteresis time.
- **Appliance On Counter**: Counts the number of times the appliance has been turned on during the current day and resets at midnight.

## Features
- **Appliance Sensor**: Uses power threshold and hysteresis time to determine if an appliance is on or off.
- **Appliance On Counter**: Counts the number of times the appliance is turned on each day and resets the count at midnight.

## Installation

1. **Download and Extract:**
   - Download the latest release of the custom component from the [GitHub releases page](https://github.com/doig007/appliance_sensor/releases).
   - Extract the contents of the zip file to your Home Assistant `custom_components` directory.

2. **Directory Structure:**
   Ensure your directory structure looks like this:
   ```text
   config
   └── custom_components
       └── appliance_sensor
           ├── __init__.py
           ├── const.py
           ├── config_flow.py
           ├── manifest.json
           ├── sensor.py
           ├── strings.json
           └── translations
               └── en.json

3.  **Restart Home Assistant:**
    Restart Home Assistant to recognize the new custom component.

## Configuration
    The custom component can be configured via the Home Assistant GUI.

1.  **Add Integration:**

    Go to Configuration > Devices & Services.
    Click on Add Integration and search for Appliance Sensor.
    Follow the on-screen instructions to configure the integration.

2.  **Configuration Options:**

    Entity ID: The entity ID of the power sensor that monitors the appliance.
    Threshold: The power threshold above which the appliance is considered to be on.
    Hysteresis Time: The time (in seconds) the power must remain below the threshold before the appliance is considered off.