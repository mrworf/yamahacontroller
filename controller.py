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

class YamahaController:
  def drain(self):
    c = 0
    l = "";
    while True:
      a = self.port.read(99)
      if len(a) > 0:
        c += len(a)
        l += repr(a)
      else:
        break
  
    print "Drained " + str(c) + " bytes"
    print "Contents: " + l
  
  def is_end(self):
    a = self.port.read(1)
    if a != "\x03":
      return False
    return True
  
  def read_config(self):
    self.model = self.port.read(5)
    self.version = self.port.read(1)
    llen = self.port.read(1)
    hlen = self.port.read(1)
    config_len = int(llen + hlen, 16)
    config = self.port.read(config_len)
    lsum = self.port.read(1)
    hsum = self.port.read(1)
    if not self.is_end():
      print "Error! No end in sight"
      self.drain()
    else:
      print "   Model ID: " + self.model
      print " SW Version: " + self.version
      print "Config data: " + str(config_len) + " bytes"
      if config[7] == "0":
        print "System is ready"
        self.state = "ready"
      elif config[7] == "1":
        print "System is busy"
        self.state = "busy"
      elif config[7] == "2":
        print "System is in standby"
        self.state = "standby"
      else:
        print "System is in unknown state"
        self.state = "unknown"
      if config_len > 144 and config[144] == "0":
        print "WARNING! RS-232 cannot wake system"
        self.state = "error"
      return True
  
  def init_comms(self):
    self.drain()
    self.port.write("\x11000\x03")
    return self.handleResults()

  # Sends a Operation Command to the receiver
  # (see 3.2 in RX-V1900 RS-232C Protocol)
  def send_op(self, cmd):
    print "Sending " + cmd + " to receiver"
    self.port.write("\x02" + "07" + cmd + "\x03")
    
  # Sends a System Command to the receiver
  # (see 3.1 in RX-V1900 RS-232C Protocol)
  def send_sys(self, cmd):
    print "Sending " + cmd + " to receiver"
    self.port.write("\x02" + "2" + cmd + "\x03")
  
  def read_result(self):
    type = self.port.read(1)
    guard = self.port.read(1)
    cmd = self.port.read(2)
    result = self.port.read(2)
    a = self.port.read(1)
    valid = True
    if a != "\x03":
      print "Error: Not a supported report command"
      valid = False
    return {"type": type, "guard": guard, "command": cmd, "result": result, "valid": valid}
  
  def send_system(self, cmd):
    self.port.write("\x022" + cmd + "\x03")
    res = self.read_result()
    print "Result: " + repr(res)

  # Reads until all results have been parsed
  #
  def handleResults(self):
    results = []
    
    while True:
      data = self.handleResult()
      if data is None:
        break
      results.append(data)

      # Fast exit, usually more than one result is sent at once
      # so we can rely on the serial driver. But when executing
      # a new command, we need to be a bit more patient
      if not self.port.inWaiting():
        break
    return results

  # Reads one result from the buffer
  #
  def handleResult(self):
    # Determine the incoming data
    d = self.port.read(1)
    if len(d) == 0:
      return None
    elif d == '\x12': # DC2
      print "Found config"
      return {"input": "config", "data": self.read_config()}
    elif d == '\x02': # STX
      print "Found result"
      return {"input": "result", "data": self.read_result()}
    else:
      print "Unexpected data, starts with " + repr(d)
      self.drain()
    return {"input":"error"}
  
  # Constructor, we don't do much here
  #
  def __init__(self, serialport):
    self.serialport = serialport
    self.port = serial.Serial(serialport, baudrate=9600, timeout=2, rtscts=True)
    self.state = "unknown"

  # Actual init call
  #
  def init(self):
    print "Yamaha RX-V - Serial Commander"
    print "Intializing communication on " + self.serialport
    for i in range(1, 5):
      self.init_comms()
      if self.state != "ready" and self.state != "standby" :
        print "Failed to initialize communication with device, state = " + self.state + " (attempt #" + str(i) + ")"
        if i == 5:
          return False
      else:
        print "OK"
        return True
