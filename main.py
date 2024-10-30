# relay_emulator.py - Standalone script to emulate the relay hardware.
import tkinter as tk
from tkinter import ttk
import serial.tools.list_ports
import json
import os
import threading
from pygame import mixer
import serial
import time


class RelayEmulatorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Relay Emulator")

        # COM Port Selection UI
        self.com_ports = self.get_com_ports()

        # COM Port Label
        self.com_port_label = ttk.Label(root, text="Select COM Port to Emulate Relay:")
        self.com_port_label.grid(row=0, column=0, padx=10, pady=10)
        self.com_port_combobox = ttk.Combobox(root, values=self.com_ports)
        self.com_port_combobox.grid(row=0, column=1, padx=10, pady=10)

        # Load saved settings if available
        self.load_settings()

        # Open COM Port Button
        self.open_com_button = ttk.Button(root, text="Open COM Port", command=self.open_com_port)
        self.open_com_button.grid(row=1, column=0, pady=20)

        # Close COM Port Button
        self.close_com_button = ttk.Button(root, text="Close COM Port", command=self.close_com_port)
        self.close_com_button.grid(row=1, column=1, pady=20)

        # Status Label
        self.status_label = ttk.Label(root, text="Status: COM Port Closed", foreground="red")
        self.status_label.grid(row=2, column=0, columnspan=2, pady=10)

        # LED State Indicator
        self.led_canvas = tk.Canvas(root, width=50, height=50)
        self.led_indicator = self.led_canvas.create_oval(10, 10, 40, 40, fill="red")
        self.led_canvas.grid(row=3, column=0, columnspan=2, pady=10)

        self.running = False
        self.state = 0  # 0: Locked, 1: Unlocking, 2: Unlocked
        mixer.init()  # Initialize the mixer for sound playback

    def get_com_ports(self):
        """Retrieve available COM ports from the system."""
        return [port.device for port in serial.tools.list_ports.comports()]

    def load_settings(self):
        """Load saved COM port settings from settings.conf."""
        if os.path.exists("emulator_settings.conf"):
            with open("emulator_settings.conf", "r") as f:
                settings = json.load(f)
                com_port = settings.get("COM_PORT", "")
                if com_port in self.com_ports:
                    self.com_port_combobox.set(com_port)

    def save_settings(self):
        """Save COM port settings to settings.conf."""
        settings = {
            "COM_PORT": self.com_port_combobox.get()
        }
        with open("emulator_settings.conf", "w") as f:
            json.dump(settings, f)

    def open_com_port(self):
        """Open the selected COM port and start listening."""
        com_port = self.com_port_combobox.get()

        if not com_port:
            print("Please select a COM port.")
            return

        # Save settings for future use
        self.save_settings()

        # Start listening to the selected COM port
        self.running = True
        self.status_label.config(text="Status: COM Port Open", foreground="green")
        threading.Thread(target=self.listen_to_serial, args=(com_port,), daemon=True).start()

    def close_com_port(self):
        """Close the COM port and stop listening."""
        self.running = False
        self.status_label.config(text="Status: COM Port Closed", foreground="red")

    def listen_to_serial(self, com_port):
        """Listen to the selected COM port and update the relay state accordingly."""
        try:
            with serial.Serial(com_port, 9600, timeout=1) as ser:
                while self.running:
                    if ser.in_waiting > 0:
                        command = ser.readline().decode('utf-8').strip()
                        if command in ["Open Sesame!", "0"] and self.state == 0:
                            self.state = 1  # Transition to unlocking state
                            self.update_led_state("unlocked")
                            # Start a timer to lock after 5 seconds
                            threading.Timer(5, self.lock_relay).start()
                        elif command == "a" and self.state == 0:
                            self.state = 2  # Transition to unlocked state
                            self.update_led_state("unlocked")
                        elif command == "z":
                            self.state = 0  # Transition back to locked state
                            self.update_led_state("locked")
        except serial.SerialException as e:
            print(f"Error opening COM port: {e}")

    def lock_relay(self):
        """Lock the relay and update state."""
        if self.state == 1:  # Only lock if in unlocking state
            self.state = 0
            self.update_led_state("locked")

    def update_led_state(self, state):
        """Update the GUI to reflect the relay state and play a sound."""
        if state == "unlocked":
            self.led_canvas.itemconfig(self.led_indicator, fill="green")
            mixer.Sound("unlock_click.mp3").play()  # Play the sound for unlocking
        elif state == "locked":
            self.led_canvas.itemconfig(self.led_indicator, fill="red")
            mixer.Sound("lock_click.mp3").play()  # Play the sound for locking


if __name__ == "__main__":
    root = tk.Tk()
    app = RelayEmulatorApp(root)
    root.mainloop()
