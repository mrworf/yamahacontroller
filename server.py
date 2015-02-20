# REST api for controlling a Yamaha Receiver
#
from controller import YamahaController
from flask import Flask
from flask import jsonify

cfg_YamahaPort = "/dev/ttyUSB0"
cfg_ServerAddr = "0.0.0.0"

app = Flask(__name__)
yamaha = YamahaController(cfg_YamahaPort)

@app.route("/")
def api_root():
  # Call the handler just incase we have pending data
  yamaha.handleResults()
  msg = {
    "model": yamaha.model,
    "software": yamaha.version,
    "port": yamaha.serialport,
    "state": yamaha.state
  }
  result = jsonify(msg)
  result.status_code = 200
    
  return result

@app.route("/operation/<data>", methods = ["GET"])
def api_operation(data):
  # Make sure we don't get unneeded data
  if len(data) != 3:
    result = jsonify({"status":500,"message":"Command must be exactly 3 bytes"})
    result.status_code = 500
    return result
  
  yamaha.send_op(data)
  
  result = {
    'status': 200,
    'result': yamaha.handleResults()
  }
  result = jsonify(result)
  result.status_code = 200
  return result

if __name__ == "__main__":
  yamaha.init()
  app.debug = True
  app.run(host=cfg_ServerAddr)

