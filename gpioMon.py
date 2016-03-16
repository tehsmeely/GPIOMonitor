import sys, socket, random, os, json, logging, logging.config, threading, time

#HOST = 'localhost'   # Local Only
#PORT = 8282
#Loaded from config.yaml

#Import Daemon module
sys.path.append("/home/pi/python/python-daemon")
from daemon2 import Daemon

#Import wiringpi2, requires root!
import wiringpi2 as wp

#Import MCP9808 I2C control script
sys.path.append("/home/pi/python/")
from MCP9808_i2c.MCP9808 import MCP9808

#Load config from YAML
import yaml
try:
    CONFIG = yaml.load(open("gpioMon.config.yaml"))
except:
    print "Failed to load config file. Exiting"
    sys.exit()

#Logging config
loggingConfig = {
    "version":1,
    "handlers":{
        "operationLogHandler":{
            "class":"logging.FileHandler",
            "formatter":"normalFormat",
            "filename":CONFIG["daemon"]["logFile"]
            },
        "doorLogHandler":{
            "class":"logging.FileHandler",
            "formatter":"dataFormat",
            "filename":CONFIG["doorMonitor"]["logFile"]
            },
        "temperatureLogHandler":{
            "class":"logging.FileHandler",
            "formatter":"dataFormat",
            "filename":CONFIG["temperatureMonitor"]["logFile"]
            }
        },        
    "loggers":{
        "operationLogging":{
            "handlers":["operationLogHandler"],
            "level":"DEBUG",
            },
        "doorLogging":{
            "handlers":["doorLogHandler"],
            "level":"INFO",
            },
        "temperatureLogging":{
            "handlers":["temperatureLogHandler"],
            "level":"INFO",
            }
        },
    "formatters":{
        "normalFormat":{
            "format":"%(asctime)s - %(name)s - %(levelname)s - %(message)s"
            },
        "dataFormat":{
            "format":"%(asctime)s@%(message)s"
            }
        }
}


    

#Map the GPIO values to the actual human reable state
DOORMAP = {'1': 'Closed', '0': 'Open'}

#Read interval between checking door, and temp
#- this could need some tweaking for performance vs precision
DOOR_READ_INTERVAL = CONFIG["readIntervals"]["door"]
TEMP_READ_INTERVAL = CONFIG["readIntervals"]["temperature"]

class SocketServer(Daemon):
    def run(self):
        #Check for root, needed for wiringPi
        try:
            os.rename('/etc/rootTester', '/etc/rootTestSuccess')
        except IOError as e:
            if (e[0] == errno.EPERM):
               print "You need root permissions to do this"
               sys.exit(1)
        else:
            os.rename('/etc/rootTestSuccess', '/etc/rootTester')

        #Logging initialise
        logging.config.dictConfig(loggingConfig)

        self.opsLog = logging.getLogger("operationLogging")
        self.doorLog = logging.getLogger("doorLogging")
        self.tempLog = logging.getLogger("temperatureLogging")
        self.opsLog.info("Starting Daemon")

        #Init setup
        random.seed()
        wp.wiringPiSetup() #us wiringPi numbers
        wp.pinMode(CONFIG["doorMonitor"]["gpioPin"], 0)

        self.tempSensor = MCP9808()
        self.tempSensor.begin()

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
        try:
            self.sock.bind((CONFIG["daemon"]["host"], CONFIG["daemon"]["port"]))
        except socket.error as msg:
            print 'Bind failed. Error Code : ' + str(msg[0]) + ' Message ' + msg[1]
            sys.exit()

        self.sock.listen(10)

        ##Now start monitoring threads
        doorMonitorThread = threading.Thread(target=self.doorMonitor_thread)
        doorMonitorThread.start()
        tempMonitorThread = threading.Thread(target=self.roomTemp_thread)
        tempMonitorThread.start()

        
        while True:
            #keep alive between connections


            conn, addr = self.sock.accept()
            self.opsLog.info("New Connection: {} : {}".format(*addr))

            #conn.send ("Connected\n")

            #Loop on connection - single connection only
            while True:
                data = conn.recv(1024)
                if not data:
                    conn.close()
                    break
                resp = self.getStatusSnapshot()
                conn.sendall(resp)

            self.opsLog.info("Connection Closed")
        self.sock.close()
    def doorMonitor_thread(self):
        doorStatus = self.getDoorStatus()
        while True:
            newDoorStatus = self.getDoorStatus()
            if newDoorStatus != doorStatus:
                doorStatus = newDoorStatus
                self.doorLog.info("Door State Change: {}".format(DOORMAP[doorStatus]))

            time.sleep(CONFIG["readIntervals"]["door"])
    def getDoorStatus(self):
        try:
            pinStatus = str(wp.digitalRead(CONFIG["doorMonitor"]["gpioPin"]))
        except Exception as e:
            pinStatus = "ERR {}".format(e)
        return pinStatus

    def roomTemp_thread(self):
        while True:
            roomTemp = self.getRoomTemp()
            self.tempLog.info(roomTemp)
            time.sleep(CONFIG["readIntervals"]["temperature"])

    def getRoomTemp(self):
        #round the output of the MCP9808 output to
        # correct accuracy, none of this 3d.p. bullshit
        #MCP9808 is accurate +- 0.5 C
        return round(self.tempSensor.readTempC(), 1)

    def getStatusSnapshot(self):
        responseDict = {}
        
        responseDict["DOOR"] = self.getDoorStatus()
        responseDict["TEMPERATURE"] = self.getRoomTemp()
        ##And any other data captures

        return json.dumps(responseDict)


validBasicFunctions = ["start", "stop", "restart"]

if __name__ == "__main__":
    pidFile = os.path.join(CONFIG["daemon"]["pidPath"], CONFIG["daemon"]["processName"] + ".pid")
    socketServer = SocketServer(pidFile)
#    socketServer.start()
    if len(sys.argv) > 1:
        if sys.argv[1] in validBasicFunctions:
            #Call function passed
            getattr(socketServer, sys.argv[1])()
    else:
        print "Please add a command"
