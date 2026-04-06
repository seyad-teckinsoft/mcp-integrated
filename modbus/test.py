import sys
import socket
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QLabel, QVBoxLayout
from PyQt5.QtCore import QTimer

class App(QWidget):
    def __init__(self):
        super().__init__()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(("127.0.0.1", 1500))

        self.label = QLabel("Value: 0")
        self.button = QPushButton("Increment")

        self.button.clicked.connect(self.send_increment)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        self.setLayout(layout)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_data)
        self.timer.start(500)

    def send_increment(self):
        self.sock.send(b"INC")

    def update_data(self):
        try:
            data = self.sock.recv(1024).decode()
            counter, write_val = data.strip().split(",")
            self.label.setText(f"DWORD Value: {int(write_val)}")
        except:
            pass

app = QApplication(sys.argv)
window = App()
window.show()
sys.exit(app.exec_())