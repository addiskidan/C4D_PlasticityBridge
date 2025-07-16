import c4d
from c4d import gui
import os, sys

PLUGIN_ID = 1058612

# Connect section
BTN_CONNECT = 1000
EDIT_HOST = 1001

# Action Buttons
BTN_REFRESH = 6006
BTN_LIVE_LINK = 6007
BTN_REFACET = 6008

# Checkbox + scale
CHK_PID_SUFFIX = 3001
EDIT_SCALE = 3002

CHK_ONLY_VISIBLE = 3011
RADIO_NGON = 3013
RADIO_TRI = 3014
RADIO_GROUP = 3015

# Tabs
TAB_FACET_MODE = 4000

# Basic
EDIT_TOLERANCE = 4101
EDIT_ANGLE = 4102

# Advanced
EDIT_MIN_WIDTH = 4201
EDIT_MAX_WIDTH = 4202
EDIT_EDGE_CHORD = 4203
EDIT_EDGE_ANGLE = 4204
EDIT_FACE_PLANE = 4205
EDIT_FACE_ANGLE = 4206

# Presets
COMBO_PRESETS = 5000

# Tools
BTN_AUTO_UV = 6001
BTN_CUT_SEW = 6002
BTN_SELECT_FACE = 6003
BTN_SELECT_EDGE = 6004
BTN_PAINT_FACE = 6005

# Footer info
TEXT_VERSION = 7000
TEXT_STATUS = 7001
TEXT_SUBSTATUS = 7002


libs = os.path.join(os.path.dirname(__file__), "libs")
if libs not in sys.path:
    sys.path.insert(0, libs)

from client import PlasticityClient

class PlasticityDialog(gui.GeDialog):
    def __init__(self):
        super().__init__()
        from handler import SceneHandler
        self.handler = SceneHandler(self)  # store reference if UI needs updates
        self.client = PlasticityClient(handler=self.handler)

        self.connected = False
        self._signal_state = None


    def CreateLayout(self):
        self.SetTitle("Plasticity")

        # --- Connect Row ---
        self.GroupBegin(2000, c4d.BFH_SCALEFIT, 2, 1)
        self.AddButton(BTN_CONNECT, c4d.BFH_LEFT, name="Connect")
        self.AddEditText(EDIT_HOST, c4d.BFH_SCALEFIT)
        self.SetString(EDIT_HOST, "localhost:8980")
        self.GroupEnd()

        self.AddSeparatorH(10)

        # --- Options Row ---
        self.GroupBegin(3000, c4d.BFH_SCALEFIT, 2, 1)
        self.AddCheckbox(CHK_PID_SUFFIX, c4d.BFH_LEFT, initw=100, inith=0, name="PID Suffix")
        self.SetBool(CHK_PID_SUFFIX, True)
        self.AddEditNumber(EDIT_SCALE, c4d.BFH_SCALEFIT, inith=0)
        self.SetFloat(EDIT_SCALE, 100)
        self.GroupEnd()

        # --- Visibility + Facet Type ---
        self.GroupBegin(3010, c4d.BFH_SCALEFIT, 2, 1)
        self.AddCheckbox(CHK_ONLY_VISIBLE, c4d.BFH_LEFT, initw=100, inith=0, name="Only visible")
        self.SetBool(CHK_ONLY_VISIBLE, True)

        # Radio button group for Ngons/Triangles
        self.GroupBegin(3012, c4d.BFH_LEFT, 2, 1)
        self.AddRadioGroup(RADIO_GROUP, c4d.BFH_LEFT)
        self.AddChild(RADIO_GROUP, RADIO_NGON, "Ngons")
        self.AddChild(RADIO_GROUP, RADIO_TRI, "Triangles")
        self.SetInt32(RADIO_GROUP, RADIO_NGON)  # Default to Ngons
        self.GroupEnd()
        self.GroupEnd()

        self.AddSeparatorH(10)
        
        # Action Buttons
        self.GroupBegin(0, c4d.BFH_SCALEFIT, 3, 1)
        self.AddButton(BTN_REFRESH, c4d.BFH_SCALEFIT, name="Refresh")
        self.AddCheckbox(BTN_LIVE_LINK, c4d.BFH_SCALEFIT, initw=100, inith=10, name="Live-link")
        self.SetBool(BTN_LIVE_LINK, False)  # default off
        self.AddButton(BTN_REFACET, c4d.BFH_SCALEFIT, name="Refacet")
        self.GroupEnd()

        # --- Tabbed Facet Controls ---
        self.TabGroupBegin(4000, c4d.BFH_SCALEFIT)  # Start tab group

        # Basic Tab
        self.GroupBegin(4100, c4d.BFH_SCALEFIT, 1, 2, title="Basic")
        self.AddStaticText(0, c4d.BFH_LEFT, name="Tolerance:")  # Label for Tolerance
        self.AddEditNumberArrows(4101, c4d.BFH_SCALEFIT, inith=0)
        self.SetFloat(4101, 0.01)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Angle:")  # Label for Angle
        self.AddEditNumberArrows(4102, c4d.BFH_SCALEFIT, inith=0)
        self.SetFloat(4102, 0.2)
        self.GroupEnd()

        # Advanced Tab
        self.GroupBegin(4200, c4d.BFH_SCALEFIT, 1, 6, title="Advanced")
        self.AddStaticText(0, c4d.BFH_LEFT, name="Min Width:")
        self.AddEditNumberArrows(4201, c4d.BFH_SCALEFIT, inith=0)
        self.SetFloat(4201, 0.0)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Max Width:")
        self.AddEditNumberArrows(4202, c4d.BFH_SCALEFIT, inith=0)
        self.SetFloat(4202, 0.0)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Edge Chord Tol:")
        self.AddEditNumberArrows(4203, c4d.BFH_SCALEFIT, inith=0)
        self.SetFloat(4203, 0.01)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Edge Angle Tol:")
        self.AddEditNumberArrows(4204, c4d.BFH_SCALEFIT, inith=0)
        self.SetFloat(4204, 0.25)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Face Plane Tol:")
        self.AddEditNumberArrows(4205, c4d.BFH_SCALEFIT, inith=0)
        self.SetFloat(4205, 0.01)
        self.AddStaticText(0, c4d.BFH_LEFT, name="Face Angle Tol:")
        self.AddEditNumberArrows(4206, c4d.BFH_SCALEFIT, inith=0)
        self.SetFloat(4206, 0.25)
        self.GroupEnd()

        self.GroupEnd()  # End tab group

        self.AddSeparatorH(10)

        # Preset dropdown
        self.AddComboBox(5000, c4d.BFH_LEFT, initw=100)
        self.AddChild(5000, 0, "Presets ▾")

        # Utility Buttons
        self.AddButton(6001, c4d.BFH_SCALEFIT, name="Auto UV Layout")
        self.AddButton(6002, c4d.BFH_SCALEFIT, name="Cut/Sew UV Seams")
        self.AddButton(6003, c4d.BFH_SCALEFIT, name="Select Plasticity Face(s)")
        self.AddButton(6004, c4d.BFH_SCALEFIT, name="Select Plasticity Edges")
        self.AddButton(6005, c4d.BFH_SCALEFIT, name="Paint Plasticity Faces")

        self.AddSeparatorH(10)

        # Footer Info
        self.AddStaticText(7000, c4d.BFH_LEFT, name="Version: 3.4")
        self.AddStaticText(7001, c4d.BFH_SCALEFIT, name="[INFO] Connected Successfully!")
        self.AddStaticText(7002, c4d.BFH_SCALEFIT, name="[INFO] Awaiting message")

        return True


    def Command(self, id, msg):
        if id == BTN_CONNECT:
            if not self.connected:
                host = self.GetString(EDIT_HOST)
                self.SetString(BTN_CONNECT, "Connecting...")
                self.Enable(EDIT_HOST, False)

                # Do not recreate the handler/client — just connect
                self.client.connect(host)
            else:
                print("Disconnected")
                self.client = None
                self.SetString(BTN_CONNECT, "Connect")
                self.Enable(EDIT_HOST, True)
                self.connected = False

        elif id == BTN_REFRESH:
            only_visible = self.GetBool(CHK_ONLY_VISIBLE)
            print(f"C4D> Refreshing ({'only visible' if only_visible else 'all'})...")
            if self.client:
                if only_visible:
                    self.client.list_visible()
                else:
                    self.client.list_all()

        elif id == BTN_LIVE_LINK:
            self.toggle_live_link()


        return True



    def CoreMessage(self, id, bc):
        if id != PLUGIN_ID:
            return False

        state = self._signal_state
        self._signal_state = None  # ✅ clear immediately

        if state == "connected":
            self.connected = True
            self.SetString(BTN_CONNECT, "Disconnect")
            self.Enable(EDIT_HOST, False)
            print("C4D> Connected to Plasticity")

        elif state == "disconnected":
            self.connected = False
            self.SetString(BTN_CONNECT, "Connect")
            self.Enable(EDIT_HOST, True)
            print("C4D> Disconnected")

        return True

    def update_ui_connected(self):
        self._signal_state = "connected"
        c4d.SpecialEventAdd(PLUGIN_ID, 1)

    def update_ui_disconnected(self):
        self._signal_state = "disconnected"
        c4d.SpecialEventAdd(PLUGIN_ID, 1)

    def toggle_live_link(self):
        """Toggle the live link state and update the button text."""
        btn = self.GetBool(BTN_LIVE_LINK)
        if btn:
            self.SetString(BTN_LIVE_LINK, "End Link")
            self.execute_live_link_activate()
        else:
            self.SetString(BTN_LIVE_LINK, "Live-link")
            self.execute_live_link_deactivate()

    def execute_live_link_activate(self):
        print("🟢 Live Link activated")
        self.client.subscribe_all()

    def execute_live_link_deactivate(self):
        print("🔴 Live Link deactivated")
        self.client.unsubscribe_all()


    class ClientHandler:
        def __init__(self, dlg):
            self.dlg = dlg

        def on_connect(self):
            self.dlg._signal_state = "connected"
            c4d.SpecialEventAdd(PLUGIN_ID, 1)

        def on_disconnect(self):
            self.dlg._signal_state = "disconnected"
            c4d.SpecialEventAdd(PLUGIN_ID, 1)


        def on_new_file(self, filename):
            c4d.SpecialEventAdd(PLUGIN_ID, 3, hash(filename) & 0x7fffffff)

plasticity_dialog = None

def main():
    global plasticity_dialog
    if plasticity_dialog is None:
        plasticity_dialog = PlasticityDialog()
    plasticity_dialog.Open(c4d.DLG_TYPE_ASYNC, defaultw=250, defaulth=400)