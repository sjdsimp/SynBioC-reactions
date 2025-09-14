# Overview — Reaction Platform

This repository contains the software controlling a **fully automated modular flow-chemistry platform**, developed during my PhD at Ghent University in collaboration with Johnson & Johnson.

The platform integrates **liquid handling, gas dosing, thermal control, and photochemistry** with an optimization framework, enabling automated reaction discovery and process intensification.

---

## Motivation
Continuous-flow chemistry offers safety and scalability advantages, but true self-optimization requires **tight integration of hardware and software**. This platform was designed to provide a flexible, open control system that allows:
- Rapid switching between chemistries and reactors.  
- Automated exploration of design spaces using Bayesian optimization.  
- Precise control of pressure, temperature, flow, and light intensity.  

---

## Design Requirements
- **Modularity:** Support for different pumps (Cetoni, Isco), reactors (thermal, photochemical), and controllers (Huber, Bronkhorst).  
- **Safety & reliability:** Error handling and logging of every event.  
- **Extensibility:** New hardware drivers can be added without changing the controller logic.  
- **Integration with optimizers:** Provide hooks for BO frameworks (BoTorch, Gryffin, Phoenics).  

---

## Hardware Architecture
- **Liquid handling:** Up to 7 pumps (Cetoni syringe pumps or Isco pumps).  
- **Thermal control:** Huber circulators for precise temperature regulation.  
- **Gas dosing:** Bronkhorst mass-flow and pressure controllers.  
- **Photochemistry:** Borealis photoreactor with LED power control and temperature monitoring.  

---

## Software Architecture
- **Drivers:** Individual Python modules handle communication with each device.  
- **Master Controller:** Central `Controller` class manages initialization, coordination, and safety shutdown.  
- **Logging:** Continuous data capture to `.csv` for flow rates, pressures, temperatures, and photoreactor status.  
- **Optimization loop:** External BO algorithms can connect by updating configuration files and setpoints.  

---

## Flexibility and Limitations
- **Scalable:** Supports up to 7 pumps and optional modules (MFC, photoreactor, pressure controller).  
- **Extendable:** New hardware classes can be added with minimal changes.  
- **Limitations:** Current setup relies on serial connections; error recovery is still manual in some cases.  

---

## Future Developments
- Web-based dashboard for real-time monitoring.  
- Automated safety interlocks and recovery after equipment faults.  
- Native integration with optimization libraries (e.g., BoTorch) without manual scripting.  
- Expansion to parallel multi-reactor operation.  

---
