# Yamaha Recevier Serial Controller
#
# This module will handle simple communication with a Yamaha
# receiver using the serial port protocol. It's by no means
# complete and does not actually care about the commands sent,
# it simply tries its best to encode/decode the data.
#
# Some resources:
# http://en.wikipedia.org/wiki/Control_character (for STX, DC3, etc)
# http://download.yamaha.com/api/asset/file/?language=en&site=au.yamaha.com&asset_id=54852
#
import serial
import threading
import time
import Queue
import logging

class YamahaController (threading.Thread):
  serialbuffer = bytes()
  serialpos = 0
  ready = False
  reports = {}
  config = None
  model = ""
  version = ""
  state = "unknown"
  powersave = False
  parsehint = False
  inwait = False

  pending_commands = Queue.Queue()
  resultListeners = []

  def parseConfig(self):
    result = None
    try:
      self.model = self.read(5)
      self.version = self.read(1)
      llen = self.read(1)
      hlen = self.read(1)
      config_len = int(llen + hlen, 16)
      self.config = self.read(config_len)
      lsum = self.read(1)
      hsum = self.read(1)
      end = self.read(1)
      if end != '\x03':
        #print "DEBUG: No end in sight, found " + repr(end) + " as end marker"
        # We need to discard this in a good way,
        # meaning to get rid of the start marker
        self.reset()
        self.read()
      else:
        if self.config[7] == "0":
          self.state = "ready"
        elif self.config[7] == "1":
          self.state = "busy"
        elif self.config[7] == "2":
          self.state = "standby"
        else:
          self.state = "unknown"
        if config_len > 144 and self.config[144] == "0":
          logging.warning("RS-232 cannot wake system")
          self.state = "error"
        result = True
    except YamahaException:
      self.reset()
    finally:
      self.flush()

    return result

  def parseReport(self):
    result = None
    try:
      category = self.read(1)
      guard = self.read(1)
      cmd = self.read(2)
      data = self.read(2)
      a = self.read(1)
      valid = True
      if a != "\x03":
        logging.error("Not a supported report command (" + repr(a) + ")")
        valid = False
      result = {"type": category, "guard": guard, "command": cmd, "data": data, "valid": valid}
    except:
      self.reset()
    finally:
      self.flush()
    return result

  def sendInit(self):
    #print "DEBUG: Init comms"
    self.port.write(bytearray([0x11, '0', '0', '0', 0x03]))

  # Sends a Operation Command to the receiver
  # (see 3.2 in RX-V1900 RS-232C Protocol)
  def sendOperation(self, cmd):
    logging.info("Sending " + cmd + " to receiver")
    self.port.write("\x0207" + cmd + "\x03")
    logging.info("Sent")
    if self.powersave:
      logging.info("Powersave, send again")
      self.port.write("\x0207" + cmd + "\x03")
      logging.info("Sent")

  # Sends a System Command to the receiver
  # (see 3.1 in RX-V1900 RS-232C Protocol)
  def sendSystem(self, cmd):
    logging.info("Sending " + cmd + " to receiver")
    self.port.write("\x022" + cmd + "\x03")
    logging.info("Sent")
    if self.powersave:
      logging.info("Powersave, send again")
      self.port.write("\x022" + cmd + "\x03")
      logging.info("Sent")

  # Reads until all results have been parsed
  #
  def processResults(self):
    while True:
      r = self.parseResult()
      if r is None:
        break
      elif r["input"] == "powersave":
        print "Data from receiver indicate powersave mode"
        self.powersave = True
        if len(self.resultListeners):
          print "WARNING! Powersave received when we waited for results, did we spam it?"
        continue
      elif r["input"] == "error":
        continue;
      elif r["input"] == "config":
        self.config = r["data"]
      elif r["input"] == "result":
        print "Incoming result: " + repr(r["data"])
        # Store this in a set since only the latest item is of interest
        self.reports[r["data"]["command"]] = r["data"]
        self.processResultListeners(r["data"])

      # If we get here, then powersave state is over-and-done with
      #self.powersave = False

    # We now need to take correct action, depending on state
    if not self.ready:
      if self.state == "ready" or self.state == "standby" :
        logging.info("Communication established")
        self.ready = True

  def getResult(self, result):
    """
    Get a reported result from the receiver, returns None
    if the result isn't available.
    """
    if result not in self.reports:
      return None

    return self.reports[result]

  def getAllResults(self):
    result = []
    for report in self.reports:
      result.append(self.reports[report])
    return result

  # Removes a result
  #
  def clearResult(self, result):
    if result in self.reports:
      self.reports.pop(result)


  # Reads one result from the buffer
  #
  def parseResult(self):
    try:
      category = ""
      d = self.read(1)
      if d == '\x12': # DC2
        self.parsehint = True
        category = "config"
        data = self.parseConfig()
      elif d == '\x02': # STX
        self.parsehint = True
        category = "result"
        data = self.parseReport()
      elif d == '\x00': # This happens when receiver is OFF and it times out
        category = "powersave"
        data = "Powersave, send next command TWICE"
        self.flush()
      else:
        category = "error"
        data = "Unexpected data"
        self.flush()

      # Only return data if we have some!
      if data is None:
        return None

      # Success! Clear parse hint and carry on
      self.parsehint = False
      return {"input" : category, "data" : data}
    except:
      # No data available
      return None

  def processCommand(self):
    """
    Grab the next available command to issue and execute it.
    Depending on if it want results, we may not signal immediately.
    """
    if self.pending_commands.empty():
      return
    cmd = self.pending_commands.get(False)

    if len(cmd["cmd"]) == 4: # system command
      self.sendSystem(cmd["cmd"])
    elif len(cmd["cmd"]) == 3: # operation command
      self.sendOperation(cmd["cmd"])
    else:
      logging.error("Unknown command " + repr(cmd["cmd"]))
      return

  def processResultListeners(self, result):
    """
    Checks if there is an ongoing command waiting for result and if so,
    delivers it if available. It's on a first come, first serve basis
    """
    print "process: "  + repr(result)
    print "Listeners: " + repr(self.resultListeners)
    for i in self.resultListeners:
      if i["ret"] == result["command"]:
        i["result"] = result
        i["signal"].set()
        self.resultListeners.remove(i)
        print "Removed listener, remaining: "
        print repr(self.resultListeners)
        break

  def issueCommand(self, command, resultCode):
    """
    Queue a command for execution and wait for it to return
    """
    print "----> Processing WEB command = %s" % command
    cmd = {"cmd" : command}
    res = {"result" : None}
    if resultCode is not None:
      evt = threading.Event()
      res = {"ret" : resultCode, "signal" : evt, "result" : None}
      self.resultListeners.append(res)
    self.pending_commands.put(cmd)
    if resultCode is not None:
      evt.wait()
    print "<---- Processing WEB command = %s" % command
    return res["result"]

  def __init__(self, serialport):
    """
    Initialize serial port but don't do anything else
    """
    threading.Thread.__init__(self)

    self.serialport = serialport
    # Timeout of 0.2s is KEY! Because we must NEVER interrupt the receiver if it's saying something
    self.port = serial.Serial(serialport, baudrate=9600, timeout=0.200, rtscts=True, xonxoff=False, dsrdtr=False, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE)
    self.state = "unknown"
    self.port.flushInput()
    self.port.flushOutput()

  def init(self):
    """
    Kicks off the whole thing. Starts the thread and sends init command
    to the receiver
    """
    self.daemon = True

    logging.info("Yamaha-2-REST Gateway")
    logging.info("Intializing communication on " + self.serialport)
    self.active_cmd = None
    self.flush()
    self.sendInit()
    self.start()

  def run(self):
    """
    Serial buffer management, continously read data from serial port
    and buffer locally for some more intelligent parsing
    """
    while True:
      """
      if self.inwait == True:
        logging.debug("Pre-read")
      data = self.port.read(5)
      if self.inwait == True:
        logging.debug("Post-read")
      """
      #logging.debug("Pre-read")
      data = self.port.read(1024)
      #logging.debug("Post-read")
      self.serialbuffer += data
      if len(data) > 0:
        #print "DEBUG: %d bytes in buffer (added %d bytes)" % (len(self.serialbuffer), len(data))
        self.processResults()
        #print "DEBUG: %d bytes left in buffer after processing" % (len(self.serialbuffer))
      else:
        # If we're not ready, re-issue the init command.
        # HOWEVER! Make sure NOT to reissue it if we have a good idea of
        #          what's going on, since it will abort any ongoing
        #          transmission from the receiver
        if self.ready == False and self.parsehint == False:
          time.sleep(0.4)
          logging.debug("Issuing init command")
          self.sendInit()
        elif len(self.resultListeners):
          # This must ONLY happen if we're not listening for results
          # since results indicate commands in-flight
          print "No data, process commands..."
          self.processCommand()


  # Reads X bytes from buffer
  def read(self, bytes):
    remain = self.avail()
    #print "DEBUG: read() requested %d bytes and we have %d" % (bytes, remain)
    if bytes > remain:
      raise YamahaException("Not enough bytes in buffer, wanted %d had %d" % (bytes, remain))

    result = self.serialbuffer[self.serialpos:self.serialpos+bytes]
    self.serialpos += bytes
    return result

  # Removes the read bytes from the buffer
  def flush(self):
    self.serialbuffer = self.serialbuffer[self.serialpos:]
    self.serialpos = 0

  # Returns bytes in buffer
  def avail(self):
    return len(self.serialbuffer) - self.serialpos

  # Resets the read pointer, useful when not all data is available
  def reset(self):
    self.serialpos = 0

class YamahaException(Exception):
  pass
