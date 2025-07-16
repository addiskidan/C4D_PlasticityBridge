import sys
import importlib

PLUGIN_DIR = r"C:\C4D_dev\C4D_PlasticityBridge"
if PLUGIN_DIR not in sys.path:
    sys.path.insert(0, PLUGIN_DIR)

# Reload core modules in dependency order
for mod in ["handler", "client"]:
    if mod in sys.modules:
        importlib.reload(sys.modules[mod])

# Reload UI module
MODULE_NAME = "plasticity_ui_c4d"
if MODULE_NAME in sys.modules:
    module = sys.modules[MODULE_NAME]
    if hasattr(module, "plasticity_dialog") and module.plasticity_dialog is not None:
        try:
            module.plasticity_dialog.Close()
        except Exception:
            pass
        module.plasticity_dialog = None
    importlib.reload(module)
else:
    module = importlib.import_module(MODULE_NAME)

# Relaunch UI
if hasattr(module, "main"):
    module.main()
