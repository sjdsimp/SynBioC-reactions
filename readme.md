# Reaction Platform

Control software for a **fully automated modular flow-chemistry platform**, developed during my PhD at Ghent University in collaboration with Johnson & Johnson.

The platform integrates **liquid handling, gas dosing, thermal control, and photochemistry** with an optimization framework, enabling automated reaction discovery and process intensification.

---

## ✨ Features
- Support for up to **7 pumps** (Cetoni syringe or Isco).  
- Integration of **Huber circulators**, **Bronkhorst MFCs and pressure controllers**, and a **Borealis photoreactor**.  
- Central `Controller` class for coordinated experiment execution.  
- Automatic **data logging** to `.csv`.  
- Extensible architecture — add new drivers without changing core logic.  
- Designed for **Bayesian optimization** workflows (BoTorch, Gryffin, Phoenics).  
- All devices can also be **addressed individually** after initialization.


---

## 🚀 Usage

```python
from reaction_platform import platform_controller

# Initialize the platform
reaction_platform = platform_controller.Controller(config_file="example_config.csv")

# Prepare equipment (fill pumps, start huber, open logs)
reaction_platform.ready_equipment()

# Start an experiment with setpoints
setpoints = [0.5, 0.5, 20, 10, 1.0]  # pumps, huber, MFC, pressure
reaction_platform.start_experiment(setpoints=setpoints)

# Stop when finished
reaction_platform.stop_experiment()
```

You can also interact with individual devices directly:

```python
reaction_platform.pump1.start(flowrate=0.5)
reaction_platform.huber.setpoint(30)
reaction_platform.photoreactor.enable()
```

Configuration files are `.csv` files describing the equipment setup.  
See the [API Reference](docs/api_reference.md) for full details.

---

## 📚 Documentation
- [Overview](docs/overview.md) — background, architecture, motivation  
- [API Reference](docs/api_reference.md) — classes and methods in `platform_controller.py`

---

## 📄 License
Released under the [MIT License](LICENSE).  
This permissive license maximizes adoption while protecting you from liability:  
others may freely use and modify the code, but without warranty.

---

## 🙌 Acknowledgements
Developed during my PhD at **Ghent University**, in collaboration with **Johnson & Johnson Innovative Medicine**.

## 📖 Citation

If you use this platform in your work, please cite the following article:

**S. Desimpel, et al.**  
*Automated flow platform for Bayesian optimization of photochemical reactions.*  
**Chemical Engineering Journal** (2024), 483, 152064.  
[https://doi.org/10.1016/j.cej.2024.152064](https://doi.org/10.1016/j.cej.2024.152064)

