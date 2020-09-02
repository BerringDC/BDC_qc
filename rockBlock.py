import glob
import signal
import sys
import time

import serial


class rockBlockProtocol(object):

    def rockBlockConnected(self): pass
    def rockBlockDisconnected(self): pass

    # SIGNAL
    def rockBlockSignalUpdate(self, sign): pass
    def rockBlockSignalPass(self): pass
    def rockBlockSignalFail(self): pass

    # MT
    def rockBlockRxStarted(self): pass
    def rockBlockRxFailed(self): pass
    def rockBlockRxReceived(self, mtmsn, data): pass
    def rockBlockRxMessageQueue(self, count): pass

    # MO
    def rockBlockTxStarted(self): pass
    def rockBlockTxFailed(self): pass
    def rockBlockTxSuccess(self, momsn): pass


class rockBlockException(Exception):
    #print("no rockBlock connection")
    pass


class rockBlock(object):
    IRIDIUM_EPOCH = 1399818235000  # May 11, 2014, at 14:23:55 (This will be 're-epoched' every couple of years!)

    def __init__(self, portId, callback):
        self.s = None
        self.portId = portId
        self.callback = callback
        self.autoSession = True  # When True, we'll automatically initiate additional sessions if more messages to download
        self.sent = True
        
        try:
            self.s = serial.Serial(self.portId, 19200, timeout = 5)
            if (self._configurePort()):
                self.ping()  # KEEP SACRIFICIAL!
                self.s.timeout = 60
                if (self.ping()):
                    if (self.callback != None and callable(self.callback.rockBlockConnected)):
                        self.callback.rockBlockConnected()
                        return
            self.close()
            print('not working try')
            raise rockBlockException()

        except (Exception):
            print('no connection')
            raise rockBlockException

    # Ensure that the connection is still alive
    def ping(self):
        self._ensureConnectionStatus()
        command = "AT"
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command):
            if (self.s.readline().strip().decode() == "OK"):
                return True
        return False

    # Handy function to check the connection is still alive, else throw an Exception
    def pingception(self):
        self._ensureConnectionStatus()
        self.s.timeout = 5
        if (self.ping() == False):
            raise rockBlockException
        self.s.timeout = 60

    def requestSignalStrength(self):
        self._ensureConnectionStatus()
        command = "AT+CSQ"
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command):
            response = self.s.readline().strip().decode()
            if (response.find("+CSQ") >= 0):
                self.s.readline().strip().decode()  # OK
                self.s.readline().strip().decode()  # BLANK
                if (len(response) == 6):
                    return int(response[5])
        return -1

    def messageCheck(self):
        self._ensureConnectionStatus()
        if (self.callback != None and callable(self.callback.rockBlockRxStarted)):
            self.callback.rockBlockRxStarted()
        if (self._attemptConnection() and self._attemptSession()):
            return True
        else:
            if (self.callback != None and callable(self.callback.rockBlockRxFailed)):
                self.callback.rockBlockRxFailed()

    def networkTime(self):
        self._ensureConnectionStatus()
        command = "AT-MSSTM"
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command):
            response = self.s.readline().strip().decode()
            self.s.readline().strip().decode()  # BLANK
            self.s.readline().strip().decode()  # OK
            if (not "no network service" in response):
                utc = int(response[8:], 16)
                utc = int((self.IRIDIUM_EPOCH + (utc * 90)) / 1000)
                return utc
            else:
                return 0

    def sendMessage(self, msg):
        self._ensureConnectionStatus()
        if (self.callback != None and callable(self.callback.rockBlockTxStarted)):
            self.callback.rockBlockTxStarted()
        if (self._queueMessage(msg) and self._attemptConnection()):
            SESSION_DELAY = 1
            SESSION_ATTEMPTS = 6
            while (True):
                SESSION_ATTEMPTS = SESSION_ATTEMPTS - 1
                if (SESSION_ATTEMPTS == 0):
                    break
                if (self._attemptSession()):
                    return True
                else:
                    time.sleep(SESSION_DELAY)
        if (self.callback != None and callable(self.callback.rockBlockTxFailed)):
            self.callback.rockBlockTxFailed()
        return False
 
    def getSerialIdentifier(self):
        self._ensureConnectionStatus()
        command = "AT+GSN"
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command):
            response = self.s.readline().strip().decode()
            self.s.readline().strip().decode()  # BLANK
            self.s.readline().strip().decode()  # OK
            return response

    # One-time initial setup function (Disables Flow Control)
    # This only needs to be called once, as is stored in non-volitile memory

    # Make sure you DISCONNECT RockBLOCK from power for a few minutes after this command has been issued...
    def setup(self):
        self._ensureConnectionStatus()
        # Disable Flow Control
        command = "AT&K0"
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command and self.s.readline().strip().decode() == "OK"):
            # Store Configuration into Profile0
            command = "AT&W0"
            self.s.write(str.encode(command + "\r"))
            if (self.s.readline().strip().decode() == command and self.s.readline().strip().decode() == "OK"):
                # Use Profile0 as default
                command = "AT&Y0"
                self.s.write(str.encode(command + "\r"))
                if (self.s.readline().strip().decode() == command and self.s.readline().strip().decode() == "OK"):
                    # Flush Memory
                    command = "AT*F"
                    self.s.write(str.encode(command + "\r"))
                    if (self.s.readline().strip().decode() == command and self.s.readline().strip().decode() == "OK"):
                        # self.close()
                        return True
        return False

    def close(self):
        if (self.s != None):
            self.s.close()
            self.s = None

    @staticmethod
    def listPorts():
        if sys.platform.startswith('win'):
            ports = ['COM' + str(i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        result = []

        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass

        return result

    # Private Methods - Don't call these directly!
    def _queueMessage(self, msg):
        self._ensureConnectionStatus()
        if (len(msg) > 340):
            print("sendMessageWithBytes bytes should be <= 340 bytes")
            return False 
        command = "AT+SBDWB=" + str(len(msg))
        #print(command,"rockBlock\n")
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command):
            if (self.s.readline().strip().decode() == "READY"):
                checksum = 0
                for c in msg:
                    checksum = checksum + ord(c)
                #print(checksum,'\n',str.encode(str(msg)),'\n',str.encode(hex(checksum >> 8)),'\n',str.encode(chr(checksum & 0xFF)))
                self.s.write(str.encode(str(msg)))
                #print(checksum >> 8, checksum & 0xFF)
                #print(checksum)
                self.s.write(bytes([checksum >> 8]))
                self.s.write(bytes([checksum & 0xFF]))               
                #self.s.write(str.encode(chr(checksum >> 8)))
                #self.s.write(str.encode(chr(checksum & 0xFF)))
                self.s.readline().strip().decode()  # BLANK
                result = False
                transmission = self.s.readline().strip().decode()
                print("Transmission,",transmission)
                
                if (transmission == "0"):
                    result = True
                self.s.readline().strip().decode()  # BLANK
                self.s.readline().strip().decode()  # OK
                return result
        return False

    def _configurePort(self):
        if (self._enableEcho() and self._disableFlowControl and self._disableRingAlerts() and self.ping()):
            return True
        else:
            return False

    def _enableEcho(self):
        self._ensureConnectionStatus()
        command = "ATE1"
        self.s.write(str.encode(command + "\r"))
        response = self.s.readline().strip().decode()
        if (response == command or response == ""):
            if (self.s.readline().strip().decode() == "OK"):
                return True
        return False

    def _disableFlowControl(self):
        self._ensureConnectionStatus()
        command = "AT&K0"
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command):
            if (self.s.readline().strip().decode() == "OK"):
                return True
        return False

    def _disableRingAlerts(self):
        self._ensureConnectionStatus()
        command = "AT+SBDMTA=0"
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command):
            if (self.s.readline().strip().decode() == "OK"):
                return True
        return False

    def _attemptSession(self):
        self._ensureConnectionStatus()
        SESSION_ATTEMPTS = 8
        while (True):
            if (SESSION_ATTEMPTS == 0):
                return False
            SESSION_ATTEMPTS = SESSION_ATTEMPTS - 1
            command = "AT+SBDIX"
            self.s.write(str.encode(command + "\r"))
            if (self.s.readline().strip().decode() == command):
                response = self.s.readline().strip().decode()
                if (response.find("+SBDIX:") >= 0):
                    self.s.readline().decode()  # BLANK
                    self.s.readline().decode()  # OK
                    response = response.replace("+SBDIX: ",
                                                "")  # +SBDIX:<MO status>,<MOMSN>,<MT status>,<MTMSN>,<MT length>,<MTqueued>
                    parts = response.split(",")
                    moStatus = int(parts[0])
                    #print("moStatus,",moStatus)
                    moMsn = int(parts[1])
                    mtStatus = int(parts[2])
                    mtMsn = int(parts[3])
                    mtLength = int(parts[4])
                    mtQueued = int(parts[5])
                    # Mobile Originated
                    if (moStatus <= 4):
                        self._clearMoBuffer()
                        if (self.callback != None and callable(self.callback.rockBlockTxSuccess)):
                            self.callback.rockBlockTxSuccess(moMsn)
                        pass
                    else:
                        if (self.callback != None and callable(self.callback.rockBlockTxFailed)):
                            self.callback.rockBlockTxFailed()
                    if (
                            mtStatus == 1 and mtLength > 0):  # SBD message successfully received from the GSS.
                        self._processMtMessage(mtMsn)
                        # AUTOGET NEXT MESSAGE
                    if (self.callback != None and callable(self.callback.rockBlockRxMessageQueue)):
                        self.callback.rockBlockRxMessageQueue(mtQueued)
                    # There are additional MT messages to queued to download
                    if (mtQueued > 0 and self.autoSession == True):
                        self._attemptSession()
                    if (moStatus <= 4):
                        return True
        return False

    def _attemptConnection(self):
        self._ensureConnectionStatus()
        TIME_ATTEMPTS = 10
        TIME_DELAY = 1
        SIGNAL_ATTEMPTS = 10
        RESCAN_DELAY = 5
        SIGNAL_THRESHOLD = 2
        # Wait for valid Network Time
        while True:
            if (TIME_ATTEMPTS == 0):
                if (self.callback != None and callable(self.callback.rockBlockSignalFail)):
                    self.callback.rockBlockSignalFail()
                return False
            if (self._isNetworkTimeValid()):
                break
            TIME_ATTEMPTS = TIME_ATTEMPTS - 1
            time.sleep(TIME_DELAY)
        # Wait for acceptable signal strength
        while True:
            sign = self.requestSignalStrength()
            if (SIGNAL_ATTEMPTS == 0 or sign < 0):
                print("NO SIGNAL")
                self.sent = False
                if (self.callback != None and callable(self.callback.rockBlockSignalFail)):
                    self.callback.rockBlockSignalFail()
                return False
            self.callback.rockBlockSignalUpdate(sign)
            if (sign >= SIGNAL_THRESHOLD):
                if (self.callback != None and callable(self.callback.rockBlockSignalPass)):
                    self.callback.rockBlockSignalPass()
                return True
            SIGNAL_ATTEMPTS = SIGNAL_ATTEMPTS - 1
            time.sleep(RESCAN_DELAY)

    def _processMtMessage(self, mtMsn):
        self._ensureConnectionStatus()
        self.s.write(str.encode("AT+SBDRB\r"))
        response = self.s.readline().strip().decode().replace("AT+SBDRB\r", "").strip()
        if (response == "OK"):
            print("No message content.. strange!")
            if (self.callback != None and callable(self.callback.rockBlockRxReceived)):
                self.callback.rockBlockRxReceived(mtMsn, "")
        else:
            content = response[2:-2]
            if (self.callback != None and callable(self.callback.rockBlockRxReceived)):
                self.callback.rockBlockRxReceived(mtMsn, content)
            self.s.readline().decode()  # BLANK?

    def _isNetworkTimeValid(self):
        self._ensureConnectionStatus()
        command = "AT-MSSTM"
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command):  # Echo
            response = self.s.readline().strip().decode()
            if (response.startswith("-MSSTM")):  # -MSSTM: a5cb42ad / no network service
                self.s.readline().decode()  # OK
                self.s.readline().decode()  # BLANK
                if (len(response) == 16):
                    return True
        return False

    def _clearMoBuffer(self):
        self._ensureConnectionStatus()
        command = "AT+SBDD0"
        self.s.write(str.encode(command + "\r"))
        if (self.s.readline().strip().decode() == command):
            if (self.s.readline().strip().decode() == "0"):
                self.s.readline().decode() # BLANK
                if (self.s.readline().strip().decode() == "OK"):
                    return True
        return False

    def _ensureConnectionStatus(self):
        if (self.s == None or self.s.isOpen() == False):
            print ('no connection')
            raise rockBlockException()


