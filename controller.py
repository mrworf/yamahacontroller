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
          print "WARN: RS-232 cannot wake system"
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
        print "Error: Not a supported report command (" + repr(a) + ")"
        valid = False
      result = {"type": category, "guard": guard, "command": cmd, "data": data, "valid": valid}
    except:
      self.reset()
    finally:
      self.flush()  
    return result

  def sendInit(self):
    #print "DEBUG: Init comms"
    self.port.write("\x11000\x03")

  # Sends a Operation Command to the receiver
  # (see 3.2 in RX-V1900 RS-232C Protocol)
  def sendOperation(self, cmd):
    print "INFO: Sending " + cmd + " to receiver"
    self.port.write("\x0207" + cmd + "\x03")
    if self.powersave:
      self.port.write("\x0207" + cmd + "\x03")
    
  # Sends a System Command to the receiver
  # (see 3.1 in RX-V1900 RS-232C Protocol)
  def sendSystem(self, cmd):
    print "INFO: Sending " + cmd + " to receiver"
    self.port.write("\x022" + cmd + "\x03")
    if self.powersave:
      self.port.write("\x022" + cmd + "\x03")

  # Reads until all results have been parsed
  #
  def processResults(self):
    while True:
      r = self.parseResult()
      if r is None:
        break
      elif r["input"] == "powersave":
        self.powersave = True
        continue
      elif r["input"] == "error":
        continue;
      elif r["input"] == "config":
        self.config = r["data"]
      elif r["input"] == "result":
        # Store this in a set since only the latest item is of interest
        #print repr(r)
        self.reports[r["data"]["command"]] = r["data"]
        self.processOngoingCommand()

      # If we get here, then powersave state is over-and-done with
      #self.powersave = False
    
    # We now need to take correct action, depending on state
    if not self.ready:
      if self.state == "ready" or self.state == "standby" :
        print "Communication established"
        self.ready = True

  # Obtains one of the results and if clear is true, will also
  # erase it from the internal list. If no result can be found,
  # None is returned (see what I did there... hehe).
  def getResult(self, result, clear=True, wait=False):
    self.inwait = True
    print "DBG: Entering loop"
    while not result in self.reports:
      if not wait:
        print "DBG: Exiting loop"
        self.inwait = False
        return None
      #print "Reports does not contain " + result
      #print repr(self.reports)
      time.sleep(0.1) # HORRIBLE!
    
    print "DBG: Exiting loop"
    self.inwait = False
    ret = self.reports[result]
    if clear:
      self.clearResult(result)
      
    return ret

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
    if self.pending_commands.empty() or self.active_cmd is not None:
      return
    self.active_cmd = self.pending_commands.get(False)

    if self.active_cmd["ret"] != None:
      self.clearResult(self.active_cmd["ret"])

    if len(self.active_cmd["cmd"]) == 2: # system command
      self.sendSystem(self.active_cmd["cmd"])
    elif len(self.active_cmd["cmd"]) == 3: # operation command
      self.sendOperation(self.active_cmd["cmd"])
    else:
      print "ERR: Unknown command " + repr(self.active_cmd["cmd"])
      self.active_cmd["signal"].set()
      self.active_cmd = None
      return

    # Return immediately if we're not waiting for anything
    if self.active_cmd["ret"] is None:
      self.active_cmd["signal"].set()
      self.active_cmd = None
      return

  def processOngoingCommand(self):
    """
    Checks if there is an ongoing command waiting for result and if so,
    delivers it if available.
    """
    if self.active_cmd is not None and self.active_cmd["ret"] in self.reports:
      self.active_cmd["result"] = self.reports[self.active_cmd["ret"]]
      self.active_cmd["signal"].set()
      self.active_cmd = None

  def issueCommand(self, data, code):
    """
    Queue a command for execution and wait for it to return
    """
    evt = threading.Event()
    cmd = {"cmd" : data, "ret" : code, "signal" : evt, "result" : None}
    self.pending_commands.put(cmd)
    evt.wait()
    return cmd["result"]

  def __init__(self, serialport):
    """
    Initialize serial port but don't do anything else
    """
    threading.Thread.__init__(self)
    
    self.serialport = serialport
    self.port = serial.Serial(serialport, baudrate=9600, timeout=0.100, rtscts=True, xonxoff=False, dsrdtr=False, stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE)
    self.state = "unknown"
    self.port.flushInput()
    self.port.flushOutput()

  def init(self):
    """
    Kicks off the whole thing. Starts the thread and sends init command
    to the receiver
    """
    self.daemon = True
    
    print "Yamaha RX-V - Serial Commander"
    print "Intializing communication on " + self.serialport
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
        print "DBG: Pre-read"
      data = self.port.read(5)
      if self.inwait == True:
        print "DBG: Post-read"
      """
      data = self.port.read(1024)
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
          print "DBG: Issuing init command"
          self.sendInit()
        else:
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
