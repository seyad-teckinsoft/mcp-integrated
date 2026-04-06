import sys
import ctypes
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel

# Load libmodbus
lib = ctypes.CDLL("/lib/aarch64-linux-gnu/libmodbus.so")

# Function prototypes
lib.modbus_new_tcp.restype = ctypes.c_void_p
lib.modbus_connect.argtypes = [ctypes.c_void_p]
lib.modbus_read_bits.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_uint8)]
lib.modbus_write_bit.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]

class ModbusClient:
    def __init__(self, ip="127.0.0.1", port=502):
        self.ctx = lib.modbus_new_tcp(ip.encode('utf-8'), port)
        if lib.modbus_connect(self.ctx) == -1:
            raise Exception("Connection failed")

    def read_coils(self, start, count):
        arr = (ctypes.c_uint8 * count)()
        lib.modbus_read_bits(self.ctx, start, count, arr)
        return list(arr)

    def write_coil(self, addr, value):
        lib.modbus_write_bit(self.ctx, addr, int(value))


class App(QWidget):
    def __init__(self):
        super().__init__()

        self.modbus = ModbusClient()

        self.label = QLabel("States: ---")

        self.buttons = []
        layout = QVBoxLayout()

        layout.addWidget(self.label)

        for i in range(5):
            btn = QPushButton(f"Toggle Coil {i}")
            btn.clicked.connect(lambda _, x=i: self.toggle_coil(x))
            self.buttons.append(btn)
            layout.addWidget(btn)

        self.setLayout(layout)

        self.timer = self.startTimer(1000)

    def toggle_coil(self, index):
        states = self.modbus.read_coils(0, 5)
        new_val = not states[index]
        self.modbus.write_coil(index, new_val)

    def timerEvent(self, event):
        states = self.modbus.read_coils(0, 5)
        text = " | ".join([f"{i}:{'ON' if s else 'OFF'}" for i, s in enumerate(states)])
        self.label.setText(text)


app = QApplication(sys.argv)
window = App()
window.show()
sys.exit(app.exec_())