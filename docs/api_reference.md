# API Reference — Reaction Platform Controller

This module provides the core software control for the modular flow-chemistry reaction platform.  
It handles configuration, hardware connections (pumps, huber, MFC, pressure control, photoreactor), experiment execution, and logging.

---

## Classes

### `Configuration`
Generates a platform configuration object from a CSV configuration file.

**Attributes**
- `no_pumps` (int): Number of pumps.  
- `datalog` (str): Name of the data log file.  
- `platform_log` (str): Name of the platform event log file.  
- `pumps` (dict): Pump configurations.  
- `huber`, `MFC`, `P_control`, `photoreactor` (dict or "disabled"): Equipment configs.

**Methods**
- `parse_configuration(file)`: Parse the CSV config file.

---

### `Controller`
Central controller that connects to all equipment and coordinates experiments.

**Key attributes**
- `_errorstate`: Counts hardware connection errors.  
- `_no_pumps_connected`: Tracks number of pumps.  
- `_any_cetoni`: True if a Cetoni bus is required.  
- `platform_logger`: CSV writer for platform log.  
- `logging_state`, `platform_state`: Threading events for control.  
- `huber_SP`, `MFC_SP`, `P_control_SP`, `photoreactor_SP`: Internal setpoints.  
- `pump1`–`pump7`: Pump objects (Cetoni or Isco).  
- `huber`, `MFC`, `P_control`, `photoreactor`: Connected hardware objects.

**Key methods**
- `append_platform_log(msg)`: Write message to platform log.  
- `add_pump(name, config)`: Initialize a pump.  
- `update_setpoints(setpoints)`: Update pump and instrument setpoints.  
- `ready_equipment()`: Fill pumps, start huber, initialize logging.  
- `start_pump(pump, setpoint, volume=None, echo=True)`: Start a single pump.  
- `start_experiment(setpoints=None, volumes=None, pump_echo=True)`: Start all equipment and logging.  
- `stop_experiment(empty=False)`: Stop and disconnect all equipment.  
- `pause_experiment(logging=False)`: Pause pumps and gas flow, keep T/P control.  
- `resume_experiment()`: Resume pumps and gas flow.  
- `toggle_logging()`: Start/stop logging.  
- `change_setpoints(setpoints, volumes=None, pump_echo=True)`: Update setpoints mid-experiment.  
- `data_logger(logging_interval=2)`: Run datalogging loop in a thread.  
- `get_pump_data(pump)`: Helper to fetch setpoint, flowrate, fill level.  
- `start_all_pumps(volumes=None, pump_echo=True)`: Start all pumps with current setpoints.

---