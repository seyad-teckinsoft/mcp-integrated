import sys
import threading
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout, QLabel
from pymodbus.server.sync import StartTcpServer
from pymodbus.datastore import ModbusSequentialDataBlock
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext

CO = 1 # Coils
DI = 2 # Discrete Inputs
HR = 3 # Holding Registers
IR = 4 # Input Registers

# -------------------------------
# Shared Modbus Data Store
# -------------------------------
store = ModbusSlaveContext(
    co=ModbusSequentialDataBlock(0, [0]*10),
    di=ModbusSequentialDataBlock(0, [0]*10),
    hr=ModbusSequentialDataBlock(0, [0]*10),
    ir=ModbusSequentialDataBlock(0, [0]*10)
)

context = ModbusServerContext(slaves=store, single=True)

# -------------------------------
# Start Modbus Server in Thread
# -------------------------------
def run_server():
    StartTcpServer(context, address=("0.0.0.0", 1502))

server_thread = threading.Thread(target=run_server, daemon=True)
server_thread.start()


# -------------------------------
# PyQt GUI
# -------------------------------
class App(QWidget):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("HMI Modbus Panel")

        self.label = QLabel("HR0: 0000000000000000")

        layout = QVBoxLayout()
        layout.addWidget(self.label)

        self.value = 0

        self.buttons = []

        for i in range(5):
            btn = QPushButton(f"Button {i}")
            btn.setCheckable(True)

            btn.pressed.connect(lambda x=i: self.set_bit(x))
            btn.released.connect(lambda x=i: self.clear_bit(x))

            layout.addWidget(btn)
            self.buttons.append(btn)

        self.setLayout(layout)

        # Timer to refresh from PLC writes
        self.timer = self.startTimer(500)

    # ---------------------------
    # Button → Update Register
    # ---------------------------
    def set_bit(self, bit):
        self.value |= (1 << bit)
        self.update_register()

    def clear_bit(self, bit):
        self.value &= ~(1 << bit)
        self.update_register()

    def update_register(self):
        context[0].setValues(IR, 0, [self.value])  
        self.label.setText(f"HR0: {self.value:016b}")

    # ---------------------------
    # Read from PLC (if PLC writes)
    # ---------------------------
    def timerEvent(self, event):
        val = context[0].getValues(HR, 0, count=1)[0]
        self.value = val
        self.label.setText(f"HR0: {self.value:016b}")


# -------------------------------
# Run App
# -------------------------------
app = QApplication(sys.argv)
window = App()
window.show()
sys.exit(app.exec_())