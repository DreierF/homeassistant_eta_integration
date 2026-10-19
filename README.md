[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz/docs/faq/custom_repositories)

# ETA Integration for Home Assistant

Integration of ETA heating units into Home Assistant via the [ETA RESTful webservices API](https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0).

This is a fork of [Tidone's integration](https://github.com/Tidone/homeassistant_eta_integration), which in turn is a fork of [nigl's integration](https://github.com/nigl/homeassistant_eta_integration). Version 2.0 updates it to current Home Assistant practices and the API specification. It is not compatible with configurations of version 1.x; remove the old integration and set it up again (see [Changes in 2.0](#changes-in-20)).

## Features

-   Sensors for all numeric and text values of the ETA terminal, with friendly names from the terminal's menu
-   One device per functional block (`Kessel`, `HK`, `WW`, …) below a device for the ETA terminal
-   Switches for on/off variables
-   Writable values as number, time and select entities ([details](#writable-entities))
-   Time slots with an optional target temperature, writable via a service ([details](#services))
-   Counters such as the total pellet consumption or full load hours with long-term statistics
-   Error sensors:
    -   A binary sensor, which activates if the ETA terminal reports at least one error
    -   A sensor, which shows the number of active errors
    -   A sensor, which shows the latest active error message
-   Error events ([details](#error-events))
-   All selected values are read with a single request per update, using the variable sets of the API

## Screenshots

|            Sensors             |             Controls             |              Diagnostic              |
| :----------------------------: | :------------------------------: | :----------------------------------: |
| ![Sensors](images/sensors.png) | ![Controls](images/controls.png) | ![Diagnostic](images/diagnostic.png) |

## Installation

This integration can be installed via HACS as a custom repository:

1. Go to `HACS` -> Click on the three dots in the top right corner -> `Custom repositories`
1. Insert `https://github.com/DreierF/homeassistant_eta_integration` into the field `Repository`
1. Choose `Integration` as `Type` and click on `Add`
1. Search for the `ETA` integration, open it and click on `Download`
1. Restart Home Assistant
1. Go to `Settings` -> `Devices & services` -> `Add Integration`, search for `Eta Sensors` and follow the instructions
    - **Note**: After entering the host and port the integration queries information about every variable of the terminal. This can take a long time; on newer ETA units with around `800` variables it takes around `8-15 minutes`.
    - **Note**: This only affects adding the integration. Afterwards only the selected entities are queried.

## General Notes

-   You have to activate the webservices API on your ETA heating unit first, see the [documentation](https://www.meineta.at/javax.faces.resource/downloads/ETA-RESTful-v1.2.pdf.xhtml?ln=default&v=0):

    -   Log in to `meinETA`
    -   Go to `Settings` in the middle of the page (not the bottom one!)
    -   Click on `Activate Webservices`
    -   Follow the instructions

-   For best results, your ETA heating unit has to support at least API version **1.2**. On older versions the integration falls back to a compatibility mode, in which some variables may not be detected correctly and writable values may set wrong values, because version 1.1 lacks the functions to query details about variables.\
    You can find firmware updates on `meinETA` (`Settings at the bottom` -> `Installation & Software`).

-   Your ETA heating unit needs a static IP address. Either configure it on the ETA terminal, or give the ETA unit a static DHCP lease on your router.

-   Each ETA terminal can only be added once. You can add several ETA terminals with different addresses.

## Related Integrations

You can check out the HACS integration [eta-flow](https://github.com/orazefabian/eta-flow), which provides an animated heat-flow card for visualizing an ETA heating system.

## Updating the List of Entities

If the variables on the ETA unit change, for example after adding a heating circuit, you can update the integration:

1. Go to `Settings` -> `Devices & services` -> `Eta Sensors`
1. Click on the gear symbol (`Configure`)
1. Select one of these actions:
    - `Update parallel API requests only`: Only updates the request limit.
    - `Update selected entities`: Refreshes the values of the variables in the selection lists, without rediscovering them.
    - `Rediscover available entities and update selected entities`: Performs a full rediscovery and then opens the entity selection.
1. `Maximum parallel API requests` controls how many API requests are sent in parallel.
    - Higher values speed up the discovery, but increase the load on the ETA unit and may cause errors on older or slower devices.
    - Practical starting points are `3-5` for older ETA units and `8-15` for newer ones.
    - If you see API errors or timeouts, reduce this value step by step.

Entities are identified by the CAN address of their variable, e.g. `40/10021/0/0/12016`, so renaming a variable on the terminal or changing the IP address of the terminal keeps their history. Variables that no longer exist on the terminal remain as orphaned entities, which you can remove in Home Assistant.

## Logs

If you have problems setting up this integration you can enable verbose logs on the dialog where you enter the host and port of the ETA terminal.
This logs all responses of the terminal, which may help locating the problem.
After setting up the integration you can download the logs at `Settings` -> `System` -> `Logs` -> `Download Full Log`.
These logs may be very large and contain sensitive information from other integrations. Before posting them, remove the lines from before you started setting up this integration.

## Error Events

This integration publishes an event whenever the ETA terminal reports a new error, or when an active error is cleared.
These events can be used in automations.

### Event Info

If a new error is reported, an `eta_webservices_error_detected` event is published.\
If an error is cleared, an `eta_webservices_error_cleared` event is published.

Every event has the following data:
| Name | Info | Sample Data |
|------------|----------------------------------------------------|---------------------------------------------------------------------------------------------|
| `msg` | Short error message | Water pressure too low 0,00 bar |
| `priority` | Error priority | Error |
| `time` | Time of the error, as reported by the ETA terminal | 2011-06-29T12:48:12 |
| `text` | Detailed error message | Top up heating water! If this warning occurs more than once a year, please contact plumber. |
| `fub` | Functional Block of the error | Kessel |
| `host` | Address of the ETA terminal connection | 0.0.0.0 |
| `port` | Port of the ETA terminal connection | 8080 |

### Checking Event Info

To check the data of an active error, follow these steps.

**Note**: This is only possible if the ETA terminal actually reports an active error!

1. Open Home Assistant in two tabs
1. On the first tab go to `Settings` -> `Devices & services` -> `Devices` -> `ETA`
1. On the second tab go to `Developer tools` -> `Events` -> Enter `eta_webservices_error_detected` in the field `Event to subscribe to` -> Click on `Start Listening`
1. On the first tab click on the `Resend Error Events` button
1. On the second tab you can now see the detailed event info

### Sending a Test Event

To check if your automations work, you can send a test event:

1. Go to `Developer tools` -> `Events`
1. Enter `eta_webservices_error_detected` in the field `Event type`
1. Enter your test payload in the `Event data` field
    - ```
      msg: Test
      priority: Error
      time: "2023-11-06T12:48:12"
      text: This is a test error.
      fub: Kessel
      host: 0.0.0.0
      port: 8080
      ```
1. Click on `Fire Event`

## Writable Entities

Writable variables can be selected in the list of writable entities:

-   Numeric values with a unit of `°C`, `%`, `kg`, `kW` or without a unit become number entities
-   Times of day become time entities
-   Variables with a list of named values, e.g. `Frei` and `Gesperrt`, become select entities
-   Time slots stay sensors, and can be changed with the `write_timeslot` [service](#services)

You find these entities on the device pages under `Configuration`.

On API v1.1 the terminal cannot report which variables are writable and what their valid values are. The integration then offers all variables with a suitable unit and guesses their valid ranges, so you have to choose the ones that are actually writable yourself.

### Legal Notes

The authors cannot be made responsible if the user renders their ETA heating unit unusable by setting a variable to an invalid value.

## Services

| Service | Target | Description |
|---------|--------|-------------|
| `eta_webservices.write_timeslot` | Writable time slot sensors | Sets `begin` and `end` of a time slot, and `temperature` for time slots with a target temperature. Times are rounded to the nearest quarter hour; use `23:59` for midnight at the end of the day. |
| `eta_webservices.write_value_scaled` | Number entities | Sets a value, applying the scale factor of the variable. With `force_decimals` decimal places are kept even if the terminal does not report any for the variable. |
| `eta_webservices.write_value` | ETA system | Writes a raw, unscaled `value` to the variable at `endpoint_url`, e.g. `/120/10101/0/0/12080`, optionally with `begin` and `end` in quarter hours since midnight. `config_entry_id` is only needed if more than one ETA terminal is set up. **Use with caution**, the value is not validated. |

## Integrating the ETA Unit into the Energy Dashboard

The total pellet consumption is recorded with long-term statistics. To add the ETA unit to the energy dashboard, convert the consumption into kWh with a template sensor in your `configuration.yaml`:

```
# Convert pellet consumption (kg) to energy consumption (kWh)
template:
  - sensor:
    - name: eta_total_energy
      unit_of_measurement: kWh
      device_class: energy
      state_class: total_increasing
      state: >
        {% if states('sensor.kessel_zahlerstande_gesamtverbrauch') | float(default=none) is not none %}
          {{ states('sensor.kessel_zahlerstande_gesamtverbrauch') | float(default=0.0) | multiply(4.8) | round(1) }}
        {% else %}
          {{ states('sensor.kessel_zahlerstande_gesamtverbrauch') }}
        {% endif %}
```

Check the entity ID of the consumption sensor on the `Kessel` device page, as it depends on the language of your terminal.

You can also use the web interface to create a template helper:
![template helper](images/template_sensor.png)

Then add the new sensor to the list of gas sources in your energy dashboard.

## Changes in 2.0

-   Entities are identified by the CAN address of their variable instead of the IP address and menu path. This keeps entities when the IP address changes, and finds variables whose menu path was identical to another one, which version 1.x dropped.
-   Entity IDs are derived from the device and entity names, e.g. `sensor.kessel_zahlerstande_gesamtverbrauch` instead of `sensor.eta_192_168_0_10_kessel_zahlerstande_gesamtverbrauch`.
-   The services `write_timeslot` and `write_timeslot_plus_temperature` are merged into `write_timeslot` with an optional temperature.
-   Configurations of version 1.x are not migrated.

## Tests

You can run the tests by executing `python3 -m pytest tests/` in the root directory of the project.\
Install the requirements before: `pip3 install -r requirements_test.txt`.
