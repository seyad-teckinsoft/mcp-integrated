import logging
from pymodbus.server import StartTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore import ModbusSequentialDataBlock

logging.basicConfig()
log = logging.getLogger()
log.setLevel(logging.WARNING)

# -------------------------------
# Custom DataBlock with change detection
# -------------------------------
class ChangeDetectDataBlock(ModbusSequentialDataBlock):
    def __init__(self, address, values, name):
        super().__init__(address, values)
        self.last_values = list(values)
        self.name = name

    def setValues(self, address, values):
        super().setValues(address, values)

        for i, val in enumerate(values):
            idx = address + i

            if self.last_values[idx] != val:
                print(f"[{self.name} CHANGE] Addr: {idx} | Old: {self.last_values[idx]} -> New: {val}")

                self.last_values[idx] = val

# -------------------------------
# Create datastore
# -------------------------------
store = ModbusSlaveContext(
    di=ModbusSequentialDataBlock(0, [0]*100),
    co=ChangeDetectDataBlock(0, [0]*100, "CO"),
    hr=ChangeDetectDataBlock(0, [0]*100, "HR"),
    ir=ModbusSequentialDataBlock(0, [0]*100)
)

context = ModbusServerContext(slaves=store, single=True)

# -------------------------------
# Background update (simulate sending)
# -------------------------------
import threading
import time

def update_values():
    i = 0
    while True:
        context[0].setValues(3, 0, [i])       # HR[0]
        context[0].setValues(1, 0, [i % 2])   # CO[0]

        i += 1
        time.sleep(0.01)  # Update every 10ms

# -------------------------------
# Main
# -------------------------------
if __name__ == "__main__":
    print("Modbus TCP Server running on port 502...\n")

    t = threading.Thread(target=update_values)
    t.daemon = True
    t.start()

    StartTcpServer(context=context, address=("0.0.0.0", 502))