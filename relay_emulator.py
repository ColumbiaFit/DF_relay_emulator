# relay_emulator.py - Standalone script to emulate the relay hardware with RTE priority override.
import tkinter as tk
from tkinter import ttk
import serial.tools.list_ports
import json
import os
import threading
import time
import serial
import re
import traceback

# Enable debug mode
DEBUG = True


def debug_log(message):
    """Print debug messages if debug mode is enabled"""
    if DEBUG:
        print(f"DEBUG: {message}")


class RelayEmulatorApp:
    def __init__(self, root):
        debug_log("Initializing RelayEmulatorApp")
        self.root = root
        self.root.title("DFACS Relay Emulator with RTE Priority")
        self.root.geometry("800x750")  # Larger window for more controls

        # Styling
        self.style = ttk.Style()
        self.style.configure("TFrame", background="#212121")
        self.style.configure("TLabel", background="#212121", foreground="#e0e0e0")
        self.style.configure("TButton", background="#424242", foreground="#e0e0e0")
        self.style.configure("Header.TLabel", font=("Arial", 14, "bold"), foreground="#4fc3f7")

        # Main frame
        self.main_frame = ttk.Frame(root, padding="20 20 20 20")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # COM Port Selection UI
        self.com_ports = self.get_com_ports()
        debug_log(f"Available COM ports: {self.com_ports}")

        # COM Port Configuration Section
        self.create_port_selection_ui()

        # Emulation Configuration Section
        self.create_emulation_configuration_ui()

        # Status Display Section
        self.create_status_display_ui()

        # Control Section
        self.create_control_ui()

        # Event Log Section
        self.create_event_log_ui()

        # Internal state tracking
        self.running = False
        self.emulation_thread = None
        self.ser = None

        # State variables
        self.lock_state = 0  # 0: Locked, 1: Temporarily Unlocked, 2: Permanently Unlocked
        self.rte_count = 0
        self.door_state = "CLOSED"  # "OPEN" or "CLOSED"
        self.unlock_start_time = 0
        self.unlock_duration = 5000  # in milliseconds

        # RTE Priority Override Variables
        self.rte_override_active = False
        self.rte_override_start_time = 0
        self.rte_override_duration = 0
        self.last_rte_state = False

        # Configuration variables
        self.billing_partner = "DFACS"  # Default to DFACS mode
        self.aux_type = "RTE"  # Default to RTE mode
        self.aux_normally_open = True  # Default to NO for RTE
        self.rte_count_enabled = True  # Default to count RTE events

        # Load saved settings
        debug_log("Loading saved settings")
        self.load_settings()

        # Setup periodic updates
        self.root.after(100, self.update_display)
        debug_log("Initialization complete")

    def get_com_ports(self):
        """Retrieve available COM ports from the system."""
        try:
            ports = serial.tools.list_ports.comports()
            return [port.device for port in ports]
        except Exception as e:
            debug_log(f"Error getting COM ports: {e}")
            return []

    def create_port_selection_ui(self):
        debug_log("Creating port selection UI")
        # COM Port Selection Section
        port_frame = ttk.LabelFrame(self.main_frame, text="COM Port Configuration", padding="10 10 10 10")
        port_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(port_frame, text="Select/Enter COM Port:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.com_port_var = tk.StringVar()
        self.com_port_combobox = ttk.Combobox(port_frame, textvariable=self.com_port_var, values=self.com_ports)
        self.com_port_combobox.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # Refresh button
        ttk.Button(port_frame, text="Refresh Ports", command=self.refresh_ports).grid(row=0, column=2, padx=5, pady=5)

        # Connect/Disconnect buttons
        self.connect_button = ttk.Button(port_frame, text="Connect", command=self.connect_serial)
        self.connect_button.grid(row=1, column=0, padx=5, pady=5, sticky="ew")

        self.disconnect_button = ttk.Button(port_frame, text="Disconnect", command=self.disconnect_serial,
                                            state="disabled")
        self.disconnect_button.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # Connection status
        self.connection_status_label = ttk.Label(port_frame, text="Not Connected", foreground="red")
        self.connection_status_label.grid(row=1, column=2, padx=5, pady=5, sticky="w")

        port_frame.columnconfigure(1, weight=1)

    def create_emulation_configuration_ui(self):
        debug_log("Creating emulation configuration UI")
        # Configuration Section
        config_frame = ttk.LabelFrame(self.main_frame, text="Emulation Configuration", padding="10 10 10 10")
        config_frame.pack(fill=tk.X, padx=5, pady=5)

        # Billing Partner
        ttk.Label(config_frame, text="Billing Partner:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.billing_partner_var = tk.StringVar(value="DFACS")
        billing_partner_combo = ttk.Combobox(config_frame, textvariable=self.billing_partner_var,
                                             values=["ABC", "PEAK", "DFACS"], state="readonly")
        billing_partner_combo.grid(row=0, column=1, padx=5, pady=5, sticky="ew")

        # AUX Input Type
        ttk.Label(config_frame, text="AUX Input Type:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.aux_type_var = tk.StringVar(value="RTE")
        aux_type_combo = ttk.Combobox(config_frame, textvariable=self.aux_type_var,
                                      values=["RTE", "REX", "DPS", "BOND"], state="readonly")
        aux_type_combo.grid(row=1, column=1, padx=5, pady=5, sticky="ew")

        # AUX Normally Open
        self.aux_normally_open_var = tk.BooleanVar(value=True)
        aux_no_check = ttk.Checkbutton(config_frame, text="AUX Normally Open", variable=self.aux_normally_open_var)
        aux_no_check.grid(row=1, column=2, padx=5, pady=5, sticky="w")

        # RTE Count Enabled
        self.rte_count_enabled_var = tk.BooleanVar(value=True)
        rte_count_check = ttk.Checkbutton(config_frame, text="RTE Count Enabled", variable=self.rte_count_enabled_var)
        rte_count_check.grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky="w")

        config_frame.columnconfigure(1, weight=1)

    def create_status_display_ui(self):
        debug_log("Creating status display UI")
        # Status Display Section
        status_frame = ttk.LabelFrame(self.main_frame, text="Status Display", padding="10 10 10 10")
        status_frame.pack(fill=tk.X, padx=5, pady=5)

        # Lock State
        ttk.Label(status_frame, text="Lock State:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.lock_state_label = ttk.Label(status_frame, text="LOCKED", foreground="red", font=("Arial", 10, "bold"))
        self.lock_state_label.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Door State (only visible for DPS/BOND)
        ttk.Label(status_frame, text="Door State:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.door_state_label = ttk.Label(status_frame, text="CLOSED", foreground="red", font=("Arial", 10, "bold"))
        self.door_state_label.grid(row=1, column=1, padx=5, pady=5, sticky="w")

        # RTE Count
        ttk.Label(status_frame, text="RTE Count:").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.rte_count_label = ttk.Label(status_frame, text="0", font=("Arial", 10, "bold"))
        self.rte_count_label.grid(row=2, column=1, padx=5, pady=5, sticky="w")

        # Unlock Timer
        ttk.Label(status_frame, text="Unlock Timer:").grid(row=3, column=0, padx=5, pady=5, sticky="w")
        self.unlock_timer_label = ttk.Label(status_frame, text="0s", font=("Arial", 10, "bold"))
        self.unlock_timer_label.grid(row=3, column=1, padx=5, pady=5, sticky="w")

        # RTE Override Status
        ttk.Label(status_frame, text="RTE Override:").grid(row=4, column=0, padx=5, pady=5, sticky="w")
        self.rte_override_label = ttk.Label(status_frame, text="NORMAL", foreground="green", font=("Arial", 10, "bold"))
        self.rte_override_label.grid(row=4, column=1, padx=5, pady=5, sticky="w")

        # Visual Indicator
        self.led_canvas = tk.Canvas(status_frame, width=80, height=80, bg="#212121", highlightthickness=0)
        self.led_canvas.grid(row=0, column=2, rowspan=5, padx=20, pady=5)
        self.led_indicator = self.led_canvas.create_oval(10, 10, 70, 70, fill="red", outline="#e0e0e0", width=2)

    def create_control_ui(self):
        debug_log("Creating control UI")
        # Control Section
        control_frame = ttk.LabelFrame(self.main_frame, text="Manual Controls", padding="10 10 10 10")
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Unlock Duration Entry
        ttk.Label(control_frame, text="Unlock Duration (s):").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.unlock_duration_var = tk.StringVar(value="5")
        unlock_duration_entry = ttk.Entry(control_frame, textvariable=self.unlock_duration_var, width=10)
        unlock_duration_entry.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        # Manual unlock button
        unlock_button = ttk.Button(control_frame, text="Manual Unlock", command=self.manual_unlock)
        unlock_button.grid(row=0, column=2, padx=5, pady=5)

        # RTE simulation button
        rte_button = ttk.Button(control_frame, text="Trigger RTE", command=self.trigger_rte)
        rte_button.grid(row=1, column=0, padx=5, pady=5)

        # Door state toggle (for DPS/BOND)
        door_toggle_button = ttk.Button(control_frame, text="Toggle Door State", command=self.toggle_door_state)
        door_toggle_button.grid(row=1, column=1, padx=5, pady=5)

        # Lock state toggle
        lock_toggle_button = ttk.Button(control_frame, text="Toggle Lock State", command=self.toggle_lock_state)
        lock_toggle_button.grid(row=1, column=2, padx=5, pady=5)

    def create_event_log_ui(self):
        debug_log("Creating event log UI")
        # Event Log Section
        log_frame = ttk.LabelFrame(self.main_frame, text="Event Log", padding="10 10 10 10")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Create text widget with scrollbar
        log_container = ttk.Frame(log_frame)
        log_container.pack(fill=tk.BOTH, expand=True)

        self.log_text = tk.Text(log_container, height=12, bg="#2a2a2a", fg="#e0e0e0", font=("Consolas", 9))
        log_scrollbar = ttk.Scrollbar(log_container, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=log_scrollbar.set)

        self.log_text.pack(side="left", fill=tk.BOTH, expand=True)
        log_scrollbar.pack(side="right", fill="y")

        # Clear log button
        clear_log_button = ttk.Button(log_frame, text="Clear Log", command=self.clear_log)
        clear_log_button.pack(pady=5)

    def refresh_ports(self):
        """Refresh the list of available COM ports."""
        debug_log("Refreshing COM ports")
        self.com_ports = self.get_com_ports()
        self.com_port_combobox['values'] = self.com_ports
        self.log_event(f"Refreshed ports: {self.com_ports}")

    def connect_serial(self):
        """Connect to the selected COM port."""
        debug_log("Attempting to connect to serial port")
        port = self.com_port_var.get()
        if not port:
            self.log_event("Error: No COM port selected")
            return

        try:
            self.ser = serial.Serial(port, 9600, timeout=1)
            self.connect_button.config(state="disabled")
            self.disconnect_button.config(state="normal")
            self.connection_status_label.config(text="Connected", foreground="green")
            self.log_event(f"Connected to {port}")

            # Start the emulation thread
            self.running = True
            self.emulation_thread = threading.Thread(target=self.emulation_loop, daemon=True)
            self.emulation_thread.start()

        except Exception as e:
            debug_log(f"Error connecting to serial: {traceback.format_exc()}")
            self.log_event(f"Error connecting to {port}: {e}")

    def disconnect_serial(self):
        """Disconnect from the COM port."""
        debug_log("Disconnecting from serial port")
        self.running = False

        if self.ser:
            try:
                self.ser.close()
            except Exception as e:
                debug_log(f"Error closing serial: {e}")
            self.ser = None

        self.connect_button.config(state="normal")
        self.disconnect_button.config(state="disabled")
        self.connection_status_label.config(text="Not Connected", foreground="red")
        self.log_event("Disconnected from COM port")

    def emulation_loop(self):
        """Main emulation loop running in separate thread."""
        debug_log("Starting emulation loop")
        last_status_time = 0

        while self.running:
            try:
                # Handle incoming serial commands
                if self.ser and self.ser.in_waiting > 0:
                    try:
                        line = self.ser.readline().decode('utf-8').strip()
                        if line:
                            self.handle_command(line)
                    except Exception as e:
                        debug_log(f"Error reading serial: {e}")

                # Handle RTE override timer
                self.handle_rte_override_timer()

                # Handle temporary unlock timer (only if not in RTE override)
                if not self.rte_override_active:
                    self.handle_unlock_timer()

                # Send periodic status updates (1Hz) for DFACS mode
                current_time = time.time()
                if (self.billing_partner_var.get().upper() == "DFACS" and
                        current_time - last_status_time >= 1.0):
                    self.send_status()
                    last_status_time = current_time

                time.sleep(0.01)  # Small delay to prevent excessive CPU usage

            except Exception as e:
                debug_log(f"Error in emulation loop: {traceback.format_exc()}")
                time.sleep(0.1)

    def handle_rte_override_timer(self):
        """Handle RTE override timer expiration."""
        if self.rte_override_active:
            current_time = time.time() * 1000  # Convert to ms
            elapsed = current_time - self.rte_override_start_time

            if elapsed >= self.rte_override_duration:
                self.deactivate_rte_override()

    def handle_unlock_timer(self):
        """Handle normal unlock timer (only when RTE override is not active)."""
        if self.lock_state == 1:  # Temporarily unlocked
            current_time = time.time() * 1000  # Convert to ms
            elapsed = current_time - self.unlock_start_time

            if elapsed >= self.unlock_duration:
                self.lock_state = 0  # Return to locked
                self.unlock_duration = 5000  # Reset to default
                self.root.after(0, self.update_ui)
                self.send_status()
                self.log_event("Temporary unlock expired - door locked")

    def handle_command(self, command):
        """Handle incoming serial commands with RTE priority override."""
        debug_log(f"Received command: {command}")
        self.log_event(f"Received: {command}")

        # Update configuration from UI
        self.billing_partner = self.billing_partner_var.get().upper()
        self.aux_type = self.aux_type_var.get().upper()
        self.aux_normally_open = self.aux_normally_open_var.get()
        self.rte_count_enabled = self.rte_count_enabled_var.get()

        cmd = command.strip()

        # If RTE override is active, block all commands except STATUS
        if self.rte_override_active:
            if cmd.upper() == "STATUS":
                self.send_status()
                self.log_event("Status requested and sent during RTE override")
            else:
                # Send rejection message for DFACS mode
                if self.billing_partner == "DFACS":
                    if self.ser:
                        try:
                            self.ser.write("REJECTED,RTE_OVERRIDE_ACTIVE\n".encode())
                            self.log_event(f"Command rejected during RTE override: {cmd}")
                        except Exception as e:
                            debug_log(f"Error sending rejection: {e}")
            return

        # Normal command processing when RTE override is not active
        self.process_normal_commands(cmd)

    def process_normal_commands(self, cmd):
        """Process commands normally when RTE override is not active."""
        # Parse duration from command if present
        duration = 5  # Default duration
        if ' ' in cmd:
            parts = cmd.split(' ', 1)
            cmd = parts[0]
            try:
                duration = int(parts[1])
                duration = max(1, min(3600, duration))  # Limit between 1s and 1 hour
            except ValueError:
                pass

        # Handle commands based on billing partner mode
        if self.billing_partner == "ABC":
            # ABC mode: No "Open Sesame!" support
            if cmd == "0" and self.lock_state == 0:
                self.unlock_door(duration)
            elif cmd.lower() == "a" and self.lock_state == 0:
                self.lock_state = 2  # Permanently unlocked
                self.root.after(0, self.update_ui)
                self.send_status()
                self.log_event("Relay: Permanently Unlocked")
            elif cmd.lower() == "z":
                self.lock_state = 0  # Locked
                self.root.after(0, self.update_ui)
                self.send_status()
                self.log_event("Relay: Locked")

        elif self.billing_partner == "PEAK":
            # Peak mode: All original commands
            if (cmd.lower() == "open sesame!" or cmd == "0") and self.lock_state == 0:
                self.unlock_door(duration)
            elif cmd.lower() == "a" and self.lock_state == 0:
                self.lock_state = 2  # Permanently unlocked
                self.root.after(0, self.update_ui)
                self.send_status()
                self.log_event("Relay: Permanently Unlocked")
            elif cmd.lower() == "z":
                self.lock_state = 0  # Locked
                self.root.after(0, self.update_ui)
                self.send_status()
                self.log_event("Relay: Locked")

        elif self.billing_partner == "DFACS":
            # DFACS mode: Advanced bidirectional commands
            if (cmd.lower() == "open sesame!" or cmd == "0") and self.lock_state == 0:
                self.unlock_door(duration)
            elif cmd.lower() == "a" and self.lock_state == 0:
                self.lock_state = 2  # Permanently unlocked
                self.root.after(0, self.update_ui)
                self.send_status()
                self.log_event("Relay: Permanently Unlocked")
            elif cmd.lower() == "z":
                self.lock_state = 0  # Locked
                self.root.after(0, self.update_ui)
                self.send_status()
                self.log_event("Relay: Locked")
            elif cmd.lower() == "ack":
                # Acknowledge RTE counter (only if counting is enabled)
                if self.rte_count_enabled:
                    self.rte_count = 0
                self.root.after(0, self.update_ui)
                self.send_status()
                self.log_event("RTE count acknowledged and reset")
            elif cmd.lower() == "status":
                # Send immediate status
                self.send_status()
                self.log_event("Status requested and sent")

    def activate_rte_override(self):
        """Activate RTE priority override."""
        debug_log("Activating RTE override")

        # Set RTE override flags
        self.rte_override_active = True
        self.rte_override_start_time = time.time() * 1000  # Current time in ms
        self.rte_override_duration = 5000  # Default 5 seconds for RTE

        # Force unlock state
        self.lock_state = 1
        self.unlock_start_time = self.rte_override_start_time
        self.unlock_duration = self.rte_override_duration

        # Increment RTE counter only if counting is enabled
        if self.rte_count_enabled:
            self.rte_count += 1

        self.root.after(0, self.update_ui)
        self.send_status()

        # Send RTE override notification for DFACS mode
        if self.billing_partner_var.get().upper() == "DFACS" and self.ser:
            try:
                self.ser.write(f"RTE_OVERRIDE,ACTIVATED,{self.rte_override_duration // 1000}\n".encode())
                self.log_event(f"RTE override activated for {self.rte_override_duration // 1000}s")
            except Exception as e:
                debug_log(f"Error sending RTE override notification: {e}")

    def deactivate_rte_override(self):
        """Deactivate RTE priority override."""
        debug_log("Deactivating RTE override")

        # Clear RTE override
        self.rte_override_active = False

        # Return to locked state
        self.lock_state = 0

        # Reset unlock duration to default
        self.unlock_duration = 5000

        self.root.after(0, self.update_ui)
        self.send_status()

        # Send RTE override notification for DFACS mode
        if self.billing_partner_var.get().upper() == "DFACS" and self.ser:
            try:
                self.ser.write("RTE_OVERRIDE,DEACTIVATED\n".encode())
                self.log_event("RTE override deactivated")
            except Exception as e:
                debug_log(f"Error sending RTE override notification: {e}")

    def send_status(self):
        """Send status message back to DFACS if serial port is open."""
        debug_log("Sending status")
        if not self.ser:
            debug_log("Serial port not open, can't send status")
            return

        # Only send status in DFACS mode
        if self.billing_partner_var.get().upper() != "DFACS":
            return

        # Format: STATUS,<lock_state>,<rte_count>,<door_state>,<lock_time_remaining>,<rte_override>
        status = "STATUS,"

        # Lock state: 0=locked, 1=unlocking, 2=unlocked
        status += str(self.lock_state)
        status += ","

        # RTE count
        status += str(self.rte_count)
        status += ","

        # Door state (only relevant for DPS/BOND)
        if self.aux_type_var.get().upper() in ["DPS", "BOND"]:
            status += self.door_state
        else:
            status += "NA"
        status += ","

        # Time remaining for temporary unlock (in seconds)
        time_remaining = 0
        if self.rte_override_active:
            # Show RTE override time remaining
            current_time = time.time() * 1000
            elapsed = current_time - self.rte_override_start_time
            if elapsed < self.rte_override_duration:
                time_remaining = int((self.rte_override_duration - elapsed) / 1000)
        elif self.lock_state == 1:
            # Show normal unlock time remaining
            current_time = time.time() * 1000
            elapsed = current_time - self.unlock_start_time
            if elapsed < self.unlock_duration:
                time_remaining = int((self.unlock_duration - elapsed) / 1000)

        status += str(time_remaining)
        status += ","

        # RTE override status
        status += "RTE_ACTIVE" if self.rte_override_active else "NORMAL"

        try:
            self.ser.write(f"{status}\n".encode())
            # Only log status sends occasionally to avoid log flood
            if time.time() % 10 < 1:  # Log roughly every 10 seconds
                self.log_event(f"Status sent: {status}")
        except Exception as e:
            debug_log(f"Error sending status: {traceback.format_exc()}")
            self.log_event(f"Error sending status: {e}")

    def unlock_door(self, duration=5):
        """Temporarily unlock the door for the specified duration."""
        # Prevent normal unlock if RTE override is active
        if self.rte_override_active:
            if self.billing_partner_var.get().upper() == "DFACS" and self.ser:
                try:
                    self.ser.write("REJECTED,RTE_OVERRIDE_ACTIVE\n".encode())
                    self.log_event("Unlock command rejected during RTE override")
                except Exception as e:
                    debug_log(f"Error sending rejection: {e}")
            return

        debug_log(f"Unlocking door for {duration}s")
        self.lock_state = 1  # Temporarily unlocked
        self.unlock_duration = duration * 1000  # Convert to milliseconds
        self.unlock_start_time = time.time() * 1000  # Current time in ms
        self.root.after(0, self.update_ui)
        self.send_status()
        self.log_event(f"Relay: Temporarily Unlocked for {duration}s")

    def trigger_rte(self):
        """Simulate a Request to Exit event with priority override."""
        debug_log("Triggering RTE")
        aux_type = self.aux_type_var.get().upper()

        if aux_type in ["RTE", "REX"]:
            # For RTE/REX, activate override if locked
            if self.lock_state == 0:  # Only if locked
                self.activate_rte_override()
        else:
            self.log_event("RTE button ignored - AUX input not set to RTE/REX")

    def toggle_door_state(self):
        """Toggle the door state between OPEN and CLOSED."""
        debug_log("Toggling door state")
        aux_type = self.aux_type_var.get().upper()

        if aux_type in ["DPS", "BOND"]:
            # Toggle door state
            if self.door_state == "CLOSED":
                self.door_state = "OPEN"
            else:
                self.door_state = "CLOSED"

            self.root.after(0, self.update_ui)
            self.send_status()
            self.log_event(f"Door state toggled to {self.door_state}")
        else:
            self.log_event("Door toggle ignored - AUX input not set to DPS/BOND")

    def toggle_lock_state(self):
        """Toggle between locked and permanently unlocked states."""
        debug_log("Toggling lock state")
        if self.lock_state == 0:  # Locked
            self.lock_state = 2  # Permanently unlocked
        else:  # Unlocked or temporarily unlocked
            self.lock_state = 0  # Locked

        self.root.after(0, self.update_ui)
        self.send_status()
        self.log_event(f"Lock state toggled to {'UNLOCKED' if self.lock_state > 0 else 'LOCKED'}")

    def manual_unlock(self):
        """Manually unlock the door from the UI."""
        try:
            duration = int(self.unlock_duration_var.get())
            duration = max(1, min(3600, duration))  # Limit between 1s and 1 hour
            self.unlock_door(duration)
        except ValueError:
            self.log_event("Error: Invalid unlock duration")

    def update_ui(self):
        """Update the UI to reflect current state."""
        # Lock state
        if self.lock_state == 0:
            self.lock_state_label.config(text="LOCKED", foreground="red")
            self.led_canvas.itemconfig(self.led_indicator, fill="red")
        elif self.lock_state == 1:
            self.lock_state_label.config(text="TEMP UNLOCKED", foreground="orange")
            self.led_canvas.itemconfig(self.led_indicator, fill="orange")
        else:  # state == 2
            self.lock_state_label.config(text="UNLOCKED", foreground="green")
            self.led_canvas.itemconfig(self.led_indicator, fill="green")

        # Door state
        if self.door_state == "OPEN":
            self.door_state_label.config(text="OPEN", foreground="green")
        else:
            self.door_state_label.config(text="CLOSED", foreground="red")

        # RTE count
        self.rte_count_label.config(text=str(self.rte_count))

        # RTE override status
        if self.rte_override_active:
            self.rte_override_label.config(text="RTE_ACTIVE", foreground="orange")
        else:
            self.rte_override_label.config(text="NORMAL", foreground="green")

    def update_display(self):
        """Periodic display update."""
        try:
            # Update unlock timer display
            if self.rte_override_active:
                current_time = time.time() * 1000
                elapsed = current_time - self.rte_override_start_time
                if elapsed < self.rte_override_duration:
                    remaining = int((self.rte_override_duration - elapsed) / 1000)
                    self.unlock_timer_label.config(text=f"{remaining}s (RTE)")
                else:
                    self.unlock_timer_label.config(text="0s")
            elif self.lock_state == 1:
                current_time = time.time() * 1000
                elapsed = current_time - self.unlock_start_time
                if elapsed < self.unlock_duration:
                    remaining = int((self.unlock_duration - elapsed) / 1000)
                    self.unlock_timer_label.config(text=f"{remaining}s")
                else:
                    self.unlock_timer_label.config(text="0s")
            else:
                self.unlock_timer_label.config(text="0s")

        except Exception as e:
            debug_log(f"Error in update_display: {e}")

        # Schedule next update
        self.root.after(100, self.update_display)

    def log_event(self, message):
        """Add an event to the log."""
        timestamp = time.strftime("%H:%M:%S")
        log_message = f"[{timestamp}] {message}\n"

        # Insert at the end and auto-scroll
        self.log_text.insert(tk.END, log_message)
        self.log_text.see(tk.END)

    def clear_log(self):
        """Clear the event log."""
        self.log_text.delete(1.0, tk.END)

    def load_settings(self):
        """Load settings from file."""
        try:
            if os.path.exists("relay_emulator_settings.json"):
                with open("relay_emulator_settings.json", "r") as f:
                    settings = json.load(f)

                if "com_port" in settings:
                    self.com_port_var.set(settings["com_port"])
                if "billing_partner" in settings:
                    self.billing_partner_var.set(settings["billing_partner"])
                if "aux_type" in settings:
                    self.aux_type_var.set(settings["aux_type"])
                if "aux_normally_open" in settings:
                    self.aux_normally_open_var.set(settings["aux_normally_open"])
                if "rte_count_enabled" in settings:
                    self.rte_count_enabled_var.set(settings["rte_count_enabled"])

                debug_log("Settings loaded successfully")
        except Exception as e:
            debug_log(f"Error loading settings: {e}")

    def save_settings(self):
        """Save settings to file."""
        try:
            settings = {
                "com_port": self.com_port_var.get(),
                "billing_partner": self.billing_partner_var.get(),
                "aux_type": self.aux_type_var.get(),
                "aux_normally_open": self.aux_normally_open_var.get(),
                "rte_count_enabled": self.rte_count_enabled_var.get()
            }

            with open("relay_emulator_settings.json", "w") as f:
                json.dump(settings, f, indent=2)

            debug_log("Settings saved successfully")
        except Exception as e:
            debug_log(f"Error saving settings: {e}")

    def on_closing(self):
        """Handle application closing."""
        debug_log("Application closing")
        self.save_settings()
        self.disconnect_serial()
        self.root.destroy()


def main():
    debug_log("Starting Relay Emulator Application")
    root = tk.Tk()
    app = RelayEmulatorApp(root)

    # Handle window closing
    root.protocol("WM_DELETE_WINDOW", app.on_closing)

    # Start the application
    root.mainloop()


if __name__ == "__main__":
    main()