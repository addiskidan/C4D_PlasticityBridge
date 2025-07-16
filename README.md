# Plasticity Bridge for Cinema 4D

A live-link plugin for integrating [Plasticity](https://www.plasticity.xyz) with Cinema 4D.

This plugin allows you to receive and update geometry from Plasticity in real-time, supporting hierarchy groups, mesh updates, and seamless refreshes — all while preserving scene structure.

---

## 🔧 Installation

1. **Install NumPy for Cinema 4D**

   If your C4D Python doesn't include NumPy, install it manually or use the bundled `site-packages` method for your version.

2. **Set Plugin Directory in `dev_reload.py`**

   Open `dev_reload.py` in the Script Editor, and update this line to point to your local plugin folder:
   ```python
   PLUGIN_DIR = r"C:\C4D_dev\C4D_PlasticityBridge"
