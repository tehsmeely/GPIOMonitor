# GPIOMonitor
Daemon. Logs specified aspects on GPIO as root. Listens on TCP port for info sharing. Basic socket sending using a "\n" delimiter which isnt ideal but works fine for this basic json not including text.


Dependencies:
https://github.com/adafruit/Adafruit_Python_MCP9808
https://github.com/serverdensity/python-daemon
https://github.com/WiringPi/WiringPi-Python
