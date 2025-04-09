# V1.2:
#   Changed the whatsapp message system to twitter because of whatsapp bullshit

# V1.3:
#   Added code to check incoming private message from twitter

# V1.4:
#   Added the save to file for record feature

# V1.5:
#   Added the code to check if ICP2 controller is faulty or not, Raises the alarm if "Try 0" is found in door entry field

#!/usr/bin/env python3

from tkinter import *
import threading
import requests
import serial
import socket
import tweepy
import time
import tkinter as tk

from tkinter import ttk
from datetime import datetime
from paho.mqtt import client as mqtt_client

usbport = 'COM6'
HOST = '10.58.22.230'   # The server's hostname or IP address
PORT = 4080             # The port used by the server

# Authenticate to flespi server
mqtt_broker = 'mqtt.flespi.io'
mqtt_port = 1883
mqtt_client_id = f'python-mqtt-DCP2'
mqtt_username = 'pM3sGumzNY7IbALd9knwPvXkSpJb0GGfizwPSGcvva1uyBwyJJSp3FzJU7KJDeOL'
mqtt_password = ''

iftttSendCounter = 0

# Authenticate to Twitter
auth = tweepy.OAuthHandler("zKQDhEMn6j9xTdoqPR01Sl6Lj", "maUDlyJjdyHjhhWYv6qCNG4JSLp4rUJeFehgS2PXwP6mS5eeqr")
auth.set_access_token("819121515048353792-YIezcdnLZGYHzrQ1JYRKNNYWeKddemO", "VcA45oLXJIdoTYouQtsFEZvLGUfbMya3kS44fdFvBHw6L")

api = tweepy.API(auth, wait_on_rate_limit=False)

try:
    ser = serial.Serial(usbport, 9600, timeout = 5, writeTimeout = 0)
    print("Serial port opened Okay...")
    # ser.setDTR(True)
except:
    print("Serial Port Not Available")

sleepTime = 1
repeatPeriod = 5.0
DMcheckCounter = 0

root = Tk()

redVoltageVar = StringVar()
yelVoltageVar = StringVar()
bluVoltageVar = StringVar()
redCalibrationVar = StringVar()
yelCalibrationVar = StringVar()
bluCalibrationVar = StringVar()
breakerStateVar = StringVar()
resetStateVar = StringVar()
doorOpenedVar = StringVar()
redFaultVar = StringVar()
yelFaultVar = StringVar()
bluFaultVar = StringVar()

breakerWhatsAppFlag = False
voltageWhatsAppFlag = False
doorOpenedWhatsAppFlag = False
sendScheduledMsg = True
DMSentFlag = False
stopThreading = False

queryNodesCounter = 0

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

#===================================================================================================

class PeriodicThread(object):
    """
    Python periodic Thread using Timer with instant cancellation
    """

    def __init__(self, callback=None, period= repeatPeriod, name=None, *args, **kwargs):
        self.name = name
        self.args = args
        self.kwargs = kwargs
        self.callback = callback
        self.period = period
        self.stop = False
        self.current_timer = None
        self.schedule_lock = threading.Lock()

    def start(self):
        """
        Mimics Thread standard start method
        """
        self.schedule_timer()

    def run(self):
        """
        By default run callback. Override it if you want to use inheritance
        """

        query_nodes()
        
        if self.callback is not None:
            self.callback()

    def _run(self):
        """
        Run desired callback and then reschedule Timer (if thread is not stopped)
        """        
        try:
            self.run()
        except Exception:
            logging.exception("Exception in running periodic thread")
        finally:
            with self.schedule_lock:
                if not self.stop:
                    self.schedule_timer()

    def schedule_timer(self):
        """
        Schedules next Timer run
        """
        self.current_timer = threading.Timer(self.period, self._run, *self.args, **self.kwargs)
        if self.name:
            self.current_timer.name = self.name
        self.current_timer.start()

    def cancel(self):
        """
        Mimics Timer standard cancel method
        """
        with self.schedule_lock:
            self.stop = True
            if self.current_timer is not None:
                self.current_timer.cancel()

    def join(self):
        """
        Mimics Thread standard join method
        """
        self.current_timer.join()

#===================================================================================================


queryNodesTmr = PeriodicThread()


def query_nodes():
    
    global queryNodesCounter

    try:
        ser.write(bytes(("%"), 'UTF-8'))
        ser.close
    except:
        print("Serial Port fault!")

    check_door_query()

    if (queryNodesCounter % 2 == 0):
        check_RMS_Voltages()

    queryNodesCounter += 1
    if (queryNodesCounter >= 255):
        queryNodesCounter = 0

    pass


def send_TCP_command(command, variable, register, tries, disableButtons):

    root.attributes('-topmost', 'true')

    if(disableButtons):
        breakerONbutton["state"] = "disable"
        breakerOFFbutton["state"] = "disable"
        lowerFlagButton["state"] = "disable"
        checkCalButton["state"] = "disable"
        resetDoorOpenedButton["state"] = "disable"
        onDemandMsgButton["state"] = "disable"
        checkFaultVoltageButton["state"] = "disable"

        root.update()


    registerCheck = True
    registerCheckCounter = tries
    while(registerCheck and registerCheckCounter > 0):
        
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((HOST, PORT))
        except:
            print("Connection Error...")
        s.settimeout(4)
        s.sendall(command)
        # print(command.decode('UTF-8'))
        time.sleep(sleepTime)
        s.sendall(b'!')
        data = s.recv(1024)
        str = data.decode('UTF-8')
        print(str.split(","))
        temp = str.split(",")
        if (len(temp) == 4):
            if(int(temp[1]) == register):                # If 4 arguments are received from node then data is okay
                variable.set(temp[3])
                registerCheck = False
        else:
            registerCheckCounter -= 1
            errStr = 'Try %d' % registerCheckCounter
            variable.set(errStr)
        s.shutdown(socket.SHUT_RDWR)
        s.close()

    if(disableButtons):
        breakerONbutton["state"] = "normal"
        breakerOFFbutton["state"] = "normal"
        lowerFlagButton["state"] = "normal"
        checkCalButton["state"] = "normal"
        resetDoorOpenedButton["state"] = "normal"
        onDemandMsgButton["state"] = "normal"
        checkFaultVoltageButton["state"] = "normal"

        root.update()
    pass
    

def send_tweet(msgString):

    t = datetime.now()                          # Get date and time in raw
    now = t.strftime('%d/%m/%Y %H:%M:%S')       # convert Raw time in readable format

    day = t.strftime('%d')                      # Current date
    month = t.strftime('%m')                    # Current month
    year = t.strftime('%Y')                     # Current year
    hour = t.strftime('%H')                     # Current hour
    minute = t.strftime('%M')                   # Current minute
    second = t.strftime('%S')                   # Current second

    tweetString = day + "/" +  month + "/" + year + " " + hour + ":" + minute + ":" + second + "\n"

    tweetString +=   "RED : " + redVoltageVar.get() + "\n" +\
                        "YEL : " + yelVoltageVar.get() + "\n" +\
                        "BLU : " + bluVoltageVar.get() + "\n"

    
    try:
        if (int(breakerStateVar.get()) == 0):
            tweetString += "Breaker : OFF\t<-----\n"
        if (int(breakerStateVar.get()) == 1):
            tweetString += "Breaker : ON\n"

        if (int(resetStateVar.get()) == 0):
            tweetString += "Reset : Okay\n"
        if (int(resetStateVar.get()) == 1):
            tweetString += "Reset : Not Okay\t<-----\n"

        if (int(doorOpenedVar.get()) == 0):
            tweetString += "Door : Okay\n"
        if (int(doorOpenedVar.get()) == 1):
            tweetString += "Door : Open!!\t<-----\n"

        tweetString += "RED_Fault : "
        tweetString += redFaultVar.get()
        tweetString += "\nYEL_Fault : "
        tweetString += yelFaultVar.get()
        tweetString += "\nBLU_Fault : "
        tweetString += bluFaultVar.get()
        tweetString += "\n"

    except:
        print("Breaker / reset / door / fault fields empty")

    tweetString += "\n" + msgString
    tweetString += "\n"

    print(tweetString)

    try:
        api.send_direct_message(819240440818003968, tweetString)
    except:
        print("\tSend Tweet error...")

    pass


def mqtt_send_status(pub_topic, pub_msg, pub_retain):

    try:

        result = client.publish(pub_topic, pub_msg, 1, pub_retain)
        status = result[0]

        if status == 0:
            print(f"Send `{pub_msg}` to topic `{pub_topic}` retain : '{pub_retain}'")
        else:
            print(f"Failed to send message to topic `{pub_topic}`")

    except:
##        print("\n\tmqtt_send_status Error")

        pass


def ifttt_send_status(val1, val2, val3):
    try:
        r = requests.post('https://maker.ifttt.com/trigger/dcp2_status/with/key/me5kjfDEXr5bJQMVvtoC6XixxYy0yhycBoRbnChqb9F',\
                  params={"value1":str(val1), "value2":str(val2),"value3":str(val3)})
        print('\t' + str(r))
    except:
        print("\tError in IFTTT")


def on_mqtt_sub_message(client, userdata, message):
    print("message received " ,str(message.payload.decode("utf-8")))
    print("message topic=",message.topic)
    print("message qos=",message.qos)
    print("message retain flag=",message.retain)

    if (message.topic == "dcp2/door/substate" and str(message.payload.decode("utf-8")) == '0' and message.retain == 0 and int(doorOpenedVar.get()) == 1):
        if (resetDoorOpenedButton["state"] == "normal"):
            reset_door_opened()
            print("======================================================================")
            print("\tdoor reset...")
            print("======================================================================")

    if (message.topic == "dcp2/breaker/substate" and str(message.payload.decode("utf-8")) == '1' and message.retain == 0 and int(breakerStateVar.get()) == 0):
        if (breakerONbutton["state"] == "normal"):
            turn_breaker_ON()
            print("======================================================================")
            print("\tBreaker turned on...")
            print("======================================================================")


def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)

    client = mqtt_client.Client(mqtt_client_id, clean_session = False)
    client.username_pw_set(mqtt_username, mqtt_password)
    client.will_set("dcp2/will", "0", retain = True)
    client.on_connect = on_connect
    client.connect(mqtt_broker, mqtt_port)

    client.subscribe("dcp2/door/substate", 0)
    client.subscribe("dcp2/breaker/substate", 0)
    # client.unsubscribe("dcp2/door/pubstate")
    client.on_message = on_mqtt_sub_message        #attach function to callback

    client.publish("dcp2/will", "1", 1, True)

    return client



root.title("ICP2 Control")

voltageFrame0 = Frame(root)
voltageFrame0.grid(row = 1, column = 1)
label0 = Label(voltageFrame0, text = "RED").grid(row = 0, column = 0)
label0 = Label(voltageFrame0, text = "YEL").grid(row = 0, column = 1)
label0 = Label(voltageFrame0, text = "BLU").grid(row = 0, column = 2)

redVoltageLabel = Label(voltageFrame0, width = 10, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = redVoltageVar, relief = SUNKEN)
redVoltageLabel.grid(row = 1, column = 0, padx = (5, 5))
yelVoltageLabel = Label(voltageFrame0, width = 10, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = yelVoltageVar, relief = SUNKEN)
yelVoltageLabel.grid(row = 1, column = 1, padx = (5, 5))
bluVoltageLabel = Label(voltageFrame0, width = 10, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = bluVoltageVar, relief = SUNKEN)
bluVoltageLabel.grid(row = 1, column = 2, padx = (5, 5))


breakerStateFrame0 = Frame(root)
breakerStateFrame0.grid(row = 2, column = 1)
breakerStateFrame1 = Frame(breakerStateFrame0)
breakerStateFrame1.grid(row = 0, column = 0)
label0 = Label(breakerStateFrame1, text = "Breaker State").grid(row = 0, column = 0)

breakerStateLabel = Label(breakerStateFrame1, width = 22, height = 2, bd = 2,
                        font = "Calibri 12", textvariable = breakerStateVar, relief = SUNKEN)
breakerStateLabel.grid(row = 1, column = 0, padx = (0, 0))


def turn_breaker_ON():

    global breakerWhatsAppFlag

    if (stopThreading == False):
        global queryNodesTmr
        queryNodesTmr.cancel()
        queryNodesTmr = PeriodicThread()

    send_TCP_command(b'<ICP2,5,W,1?>', breakerStateVar, 5, 1, True)

    breakerWhatsAppFlag = False

    if (stopThreading == False):
        queryNodesTmr.start()

    print("===================")
    
    pass

def turn_breaker_OFF():
    
    pass

breakerStateFrame2 = Frame(breakerStateFrame0)
breakerStateFrame2.grid(row = 0, column = 1)
global breakerONbutton
breakerONbutton = Button(breakerStateFrame2, text = "ON", width = 11, command = turn_breaker_ON)        #, bg = "light green"
breakerONbutton.grid(row = 0, column = 0, padx = (7, 0), pady = (7, 3))
global breakerOFFbutton
breakerOFFbutton = Button(breakerStateFrame2, text = "OFF", width = 11, command = turn_breaker_OFF)     #, bg = "#F0675D"
breakerOFFbutton.grid(row = 1, column = 0, padx = (7, 0), pady = (3, 5))



resetCycleFrame0 = Frame(root)
resetCycleFrame0.grid(row = 3, column = 1)
resetCycleFrame1 = Frame(resetCycleFrame0)
resetCycleFrame1.grid(row = 0, column = 0)
label0 = Label(resetCycleFrame1, text = "Reset Cycle").grid(row = 0, column = 0)

resetCycleLabel = Label(resetCycleFrame1, width = 22, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = resetStateVar, relief = SUNKEN)
resetCycleLabel.grid(row = 1, column = 0, padx = (0, 0), pady = (0, 6))



def lower_reset_flag():

    if (stopThreading == False):
        global queryNodesTmr
        queryNodesTmr.cancel()
        queryNodesTmr = PeriodicThread()

    resetStateVar.set("")

    send_TCP_command(b'<ICP2,13,W,0?>', resetStateVar, 13, 1, True)

    if (stopThreading == False):
        queryNodesTmr.start()

    print("===================")
    
    pass

resetCycleFrame2 = Frame(resetCycleFrame0)
resetCycleFrame2.grid(row = 0, column = 1)
global lowerFlagButton
lowerFlagButton = Button(resetCycleFrame2, text = "Lower Flag", width = 11, command = lower_reset_flag)
lowerFlagButton.grid(row = 1, column = 0, padx = (7, 0), pady = (5, 8), ipady = 8)


calibrationFrame0 = Frame(root)
calibrationFrame0.grid(row = 4, column = 1)
label0 = Label(calibrationFrame0, text = "RED_Cal").grid(row = 0, column = 0)
label0 = Label(calibrationFrame0, text = "YEL_Cal").grid(row = 0, column = 1)
label0 = Label(calibrationFrame0, text = "BLU_Cal").grid(row = 0, column = 2)
redCalibrationLabel = Label(calibrationFrame0, width = 10, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = redCalibrationVar, relief = SUNKEN)
redCalibrationLabel.grid(row = 1, column = 0, padx = (5, 5))
yelCalibrationLabel = Label(calibrationFrame0, width = 10, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = yelCalibrationVar, relief = SUNKEN)
yelCalibrationLabel.grid(row = 1, column = 1, padx = (5, 5))
bluCalibrationLabel = Label(calibrationFrame0, width = 10, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = bluCalibrationVar, relief = SUNKEN)
bluCalibrationLabel.grid(row = 1, column = 2, padx = (5, 5))

def check_calibration():

    if (stopThreading == False):
        global queryNodesTmr
        queryNodesTmr.cancel()
        queryNodesTmr = PeriodicThread()

    redCalibrationVar.set("")
    yelCalibrationVar.set("")
    bluCalibrationVar.set("")

    send_TCP_command(b'<ICP2,6,R,0?>', redCalibrationVar, 6, 2, True)
    send_TCP_command(b'<ICP2,7,R,0?>', yelCalibrationVar, 7, 2, True)
    send_TCP_command(b'<ICP2,8,R,0?>', bluCalibrationVar, 8, 2, True)

    if (stopThreading == False):
        queryNodesTmr.start()

    print("===============================================================")
    pass


def reset_door_opened():

    if (stopThreading == False):
        global queryNodesTmr
        queryNodesTmr.cancel()
        queryNodesTmr = PeriodicThread()
    
    send_TCP_command(b'<ICP2,19,W,0?>', doorOpenedVar, 19, 5, True)
    doorOpenedWhatsAppFlag = False

    print(doorOpenedWhatsAppFlag)
    try:
        ser.write(bytes(("@"), 'UTF-8'))
        ser.close
    except:
        print("Serial Port fault!")

    if (stopThreading == False):
        queryNodesTmr.start()

    print("===================")
    pass


def check_fault_voltages():

    redFaultVar.set("")
    yelFaultVar.set("")
    bluFaultVar.set("")

    if (stopThreading == False):
        global queryNodesTmr
        queryNodesTmr.cancel()
        queryNodesTmr = PeriodicThread()

    send_TCP_command(b'<ICP2,14,R,0?>', redFaultVar, 14, 2, True)
    send_TCP_command(b'<ICP2,15,R,0?>', yelFaultVar, 15, 2, True)
    send_TCP_command(b'<ICP2,16,R,0?>', bluFaultVar, 16, 2, True)

    if (stopThreading == False):
        queryNodesTmr.start()

    print("===================")

    pass


def on_demand_msg():

    if (stopThreading == False):
        global queryNodesTmr
        queryNodesTmr.cancel()
        queryNodesTmr = PeriodicThread()

    send_tweet("On Demand Message")

    if (stopThreading == False):
        queryNodesTmr.start()

    print("===================")
    pass


def start_queries():

    global queryNodesTmr
    global stopThreading

    queryNodesTmr.start()

    startQueriesButton["state"] = "disabled"
    stopQueriesButton["state"] = "normal"

    stopThreading = False

    print("Queries Started...")
    print("===================")

    pass


def stop_queries():

    global queryNodesTmr
    global stopThreading

    queryNodesTmr.cancel()
    queryNodesTmr = PeriodicThread()

    startQueriesButton["state"] = "normal"
    stopQueriesButton["state"] = "disabled"

    stopThreading = True

    print("Queries Stopped...")
    print("===================")

    pass


def buzzer_check():

    try:
        ser.write(bytes(("!"), 'UTF-8'))
        ser.close
    except:
        print("Serial Port fault!")

    time.sleep(3)

    try:
        ser.write(bytes(("@"), 'UTF-8'))
        ser.close
    except:
        print("Serial Port fault!")

    pass




calibrationFrame1 = Frame(root)
calibrationFrame1.grid(row = 5, column = 1)
checkCalButton = Button(calibrationFrame1, text = "Check Calibration", width = 38, command = check_calibration)
checkCalButton.grid(row = 0, column = 0, padx = (0, 0), pady = (5, 8), ipady = 8)

doorFrame0 = Frame(root)
doorFrame0.grid(row = 6, column = 1)
label0 = Label(doorFrame0, text = "Door State").grid(row = 0, column = 0)
doorOpenedLabel = Label(doorFrame0, width = 34, height = 3, bd = 2,
                        font = "Calibri 12", textvariable = doorOpenedVar, relief = SUNKEN)
doorOpenedLabel.grid(row = 1, column = 0, padx = (5, 5), pady = (0, 5))
resetDoorOpenedButton = Button(doorFrame0, text = "Reset Door", width = 38, command = reset_door_opened)
resetDoorOpenedButton.grid(row = 2, column = 0, padx = (0, 0), pady = (5, 8), ipady = 8)

faultVoltageFrame0 = Frame(root)
faultVoltageFrame0.grid(row = 7, column = 1)
label0 = Label(faultVoltageFrame0, text = "RED_fault").grid(row = 0, column = 0)
label0 = Label(faultVoltageFrame0, text = "YEL_fault").grid(row = 0, column = 1)
label0 = Label(faultVoltageFrame0, text = "BLU_fault").grid(row = 0, column = 2)
redFaultVoltageLabel = Label(faultVoltageFrame0, width = 10, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = redFaultVar, relief = SUNKEN)
redFaultVoltageLabel.grid(row = 1, column = 0, padx = (5, 5))
yelFaultVoltageLabel = Label(faultVoltageFrame0, width = 10, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = yelFaultVar, relief = SUNKEN)
yelFaultVoltageLabel.grid(row = 1, column = 1, padx = (5, 5))
bluFaultVoltageLabel = Label(faultVoltageFrame0, width = 10, height = 1, bd = 2,
                        font = "Calibri 12", textvariable = bluFaultVar, relief = SUNKEN)
bluFaultVoltageLabel.grid(row = 1, column = 2, padx = (5, 5))

faultVoltageFrame1 = Frame(root)
faultVoltageFrame1.grid(row = 8, column = 1)
checkFaultVoltageButton = Button(faultVoltageFrame1, text = "Check Fault Voltages", width = 38, command = check_fault_voltages)
checkFaultVoltageButton.grid(row = 0, column = 0, padx = (0, 0), pady = (5, 8), ipady = 8)

onDemandMsgFrame0 = Frame(root)
onDemandMsgFrame0.grid(row = 9, column = 1)
onDemandMsgButton = Button(onDemandMsgFrame0, text = "On Demand Msg", width = 38, command = on_demand_msg)
onDemandMsgButton.grid(row = 0, column = 0, padx = (0, 0), pady = (5, 8), ipady = 8)

buzzerCheckFrame0 = Frame(root)
buzzerCheckFrame0.grid(row = 10, column = 1)
buzzerCheckButton = Button(buzzerCheckFrame0, text = "Buzzer Check", width = 38, command = buzzer_check)
buzzerCheckButton.grid(row = 0, column = 0, padx = (0, 0), pady = (5, 8), ipady = 1)

startStopFrame0 = Frame(root)
# startStopFrame0.grid(row = 20, column = 1)
startQueriesButton = Button(startStopFrame0, text = "Start", width = 18, command = start_queries)
startQueriesButton.grid(row = 0, column = 0, padx = (5, 5), pady = (5, 8), ipady = 3)
stopQueriesButton = Button(startStopFrame0, text = "Stop", width = 18, command = stop_queries)
stopQueriesButton.grid(row = 0, column = 1, padx = (0, 5), pady = (5, 8), ipady = 3)





queryNodesTmr.start()

def on_icp2_closing():
    print("closing icp2")
    global queryNodesTmr
    queryNodesTmr.cancel()
    queryNodesTmr = PeriodicThread()
    root.destroy()

root.protocol("WM_DELETE_WINDOW", on_icp2_closing)
    
    
def check_RMS_Voltages():

    global breakerWhatsAppFlag
    global voltageWhatsAppFlag
    global doorOpenedWhatsAppFlag
    global sendScheduledMsg
    global DMSentFlag
    global DMcheckCounter
    global iftttSendCounter

    redVoltageVar.set("")
    yelVoltageVar.set("")
    bluVoltageVar.set("")
    breakerStateVar.set("")
    resetStateVar.set("")

    breakerStateLabel.config(bg = "SystemButtonFace")
    resetCycleLabel.config(bg = "SystemButtonFace")

    redVoltageLabel.config(bg = "SystemButtonFace")
    yelVoltageLabel.config(bg = "SystemButtonFace")
    bluVoltageLabel.config(bg = "SystemButtonFace")

    send_TCP_command(b'<ICP2,1,R,0?>', redVoltageVar, 1, 5, True)
    if (float(redVoltageVar.get()) < 100):
        redVoltageLabel.config(bg = "red")
    elif (float(redVoltageVar.get()) > 200):
        redVoltageLabel.config(bg = "light green")

    send_TCP_command(b'<ICP2,2,R,0?>', yelVoltageVar, 2, 5, True)
    if (float(yelVoltageVar.get()) < 100):
        yelVoltageLabel.config(bg = "red")
    elif (float(yelVoltageVar.get()) > 200):
        yelVoltageLabel.config(bg = "light green")

    send_TCP_command(b'<ICP2,3,R,0?>', bluVoltageVar, 3, 5, True)
    if (float(bluVoltageVar.get()) < 100):
        bluVoltageLabel.config(bg = "red")
    elif (float(bluVoltageVar.get()) > 200):
        bluVoltageLabel.config(bg = "light green")

    if (redVoltageVar.get() == "Try 0" or yelVoltageVar.get() == "Try 0" or bluVoltageVar.get() == "Try 0"):
        redVoltageLabel.config(bg = "red")
        yelVoltageLabel.config(bg = "red")
        bluVoltageLabel.config(bg = "red")

    elif ((float(redVoltageVar.get()) < 100 or float(yelVoltageVar.get()) < 100 or\
         float(bluVoltageVar.get()) < 100) and voltageWhatsAppFlag == False):
        send_tweet("Voltage Low Message")

        ifttt_send_status("Voltage Low", "Blue Volts :", bluVoltageVar.get())

        print("Voltage Low msg sent")
        voltageWhatsAppFlag = True

    elif(not(float(redVoltageVar.get()) < 100 or float(yelVoltageVar.get()) < 100 or\
         float(bluVoltageVar.get()) < 100) and voltageWhatsAppFlag == True):
        voltageWhatsAppFlag = False

    mqtt_send_status("dcp2/volt/red", redVoltageVar.get(), True)
    mqtt_send_status("dcp2/volt/yel", yelVoltageVar.get(), True)
    mqtt_send_status("dcp2/volt/blu", bluVoltageVar.get(), True)

    iftttSendCounter += 1
    if(iftttSendCounter > 4):
        ifttt_send_status(redVoltageVar.get(), yelVoltageVar.get(), bluVoltageVar.get())
        iftttSendCounter = 0

    send_TCP_command(b'<ICP2,4,R,0?>', breakerStateVar, 4, 5, True)
    mqtt_send_status("dcp2/breaker/pubstate", breakerStateVar.get(), True)

    if (breakerStateVar.get() == "Try 0" or int(breakerStateVar.get()) == 0):
        breakerStateLabel.config(bg = "red")

    elif (int(breakerStateVar.get()) == 0 and breakerWhatsAppFlag == False):
        breakerStateLabel.config(bg = "red")
        breakerWhatsAppFlag = True

        check_fault_voltages()

        breakerString = ""
        breakerString += "RED_Fault : "
        breakerString += redFaultVar.get()
        breakerString += "\nYEL_Fault : "
        breakerString += yelFaultVar.get()
        breakerString += "\nBLU_Fault : "
        breakerString += bluFaultVar.get()
        breakerString += "\n"
        breakerString += "Breaker Off Message"

        send_tweet(breakerString)

        ifttt_send_status("Breaker Off", breakerString, bluVoltageVar.get())

        f = open('CCR_Data.txt', 'a')

        t = datetime.now()                          # Get date and time in raw
        now = t.strftime('%d/%m/%Y %H:%M:%S')       # convert Raw time in readable format

        fileString = now + ";" + "Breaker Off" + ";" + "RED_fault : " + redFaultVar.get() 
        + "YEL_fault : " + yelFaultVar.get() + "BLU_fault : " + bluFaultVar.get() + "\n"

        f.write(fileString)
        f.flush()
        f.close()

        print("Breaker off msg sent")

    elif (int(breakerStateVar.get()) == 1):
        breakerStateLabel.config(bg = "light green")

    send_TCP_command(b'<ICP2,12,R,0?>', resetStateVar, 12, 5, True)
    if (resetStateVar.get() == "Try 0"):
        resetCycleLabel.config(bg = "red")
    elif (int(resetStateVar.get()) == 1):
        resetCycleLabel.config(bg = "red")
    elif (int(resetStateVar.get()) == 0):
        resetCycleLabel.config(bg = "light green")


    t = datetime.now()                          # Get date and time in raw
    now = t.strftime('%d/%m/%Y %H:%M:%S')       # convert Raw time in readable format

    hour = t.strftime('%H')                     # Current hour
    minute = t.strftime('%M')                   # Current minute

    if (int(minute) == 00 and sendScheduledMsg == True):    # Sends the scheduled msg at XX:00 of every hour
        sendScheduledMsg = False
        send_tweet("Scheduled Message")
        print("Scheduled msg sent")
        
    elif(int(minute) != 0 and sendScheduledMsg == False):
        sendScheduledMsg = True

    print("===================")


def check_door_query():

    global doorOpenedWhatsAppFlag

    doorOpenedVar.set("")
    doorOpenedLabel.config(bg = "SystemButtonFace")

    send_TCP_command(b'<ICP2,18,R,0?>', doorOpenedVar, 18, 5, True)
    mqtt_send_status("dcp2/door/pubstate", doorOpenedVar.get(), True)

    t = datetime.now()                          # Get date and time in raw
    now = t.strftime('%d/%m %I:%M:%S %p')       # convert Raw time in readable format
    mqtt_send_status("dcp2/timelast", now, 1)   # Sends last date time to mqtt server

    mqtt_send_status("dcp2/will", "1", 0)   # Sends status showing that script is running okay


    if(doorOpenedVar.get() == "Try 0"):
        doorOpenedLabel.config(bg = "red")
        try:
            ser.write(bytes(("!"), 'UTF-8'))
            ser.close
        except:
            print("Serial port fault!")

        f = open('CCR_Data.txt', 'a')

        t = datetime.now()                          # Get date and time in raw
        now = t.strftime('%d/%m/%Y %H:%M:%S')       # convert Raw time in readable format

        fileString = now + ";" + "Controller Fault" + "\n"
        print(fileString)
        f.write(fileString)
        f.flush()
        f.close()
        
        if (doorOpenedWhatsAppFlag == False):
            send_tweet("Controller Fault!!")
            print("Controller Fault Msg sent...")
            doorOpenedWhatsAppFlag = True

    elif (int(doorOpenedVar.get()) == 1):
        doorOpenedLabel.config(bg = "red")
        try:
            ser.write(bytes(("!"), 'UTF-8'))
            ser.close
        except:
            print("Serial port fault!")

        f = open('CCR_Data.txt', 'a')

        t = datetime.now()                          # Get date and time in raw
        now = t.strftime('%d/%m/%Y %H:%M:%S')       # convert Raw time in readable format

        fileString = now + ";" + "Door Opened" + "\n"
        print(fileString)
        f.write(fileString)
        f.flush()
        f.close()

        print(doorOpenedWhatsAppFlag)
        
        if (doorOpenedWhatsAppFlag == False):
            print(doorOpenedWhatsAppFlag)
            send_tweet("Door_Opened_Message")
            print("Door Opened Msg Sent...")
            doorOpenedWhatsAppFlag = True

    elif (int(doorOpenedVar.get()) == 0):
        doorOpenedLabel.config(bg = "light green")    

    print("===================")

    pass

startQueriesButton["state"] = "disabled"

root.lift()

check_calibration()
check_fault_voltages()

root.geometry('+895+170')

try:
    client = connect_mqtt()
    client.loop_start()
except:
    print("\tMQTT Conenction error...")

mainloop()
