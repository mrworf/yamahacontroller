#!/usr/bin/env python
#
# REST api for controlling a Yamaha Receiver
#
from controller import YamahaController
from flask import Flask
from flask import jsonify
from flask.ext.socketio import SocketIO
import time

cfg_YamahaPort = "/dev/ttyUSB0"
cfg_ServerAddr = "0.0.0.0"

app = Flask(__name__)
yamaha = YamahaController(cfg_YamahaPort)

@app.route("/")
def api_root():
  msg = {
    "model": yamaha.model,
    "software": yamaha.version,
    "port": yamaha.serialport,
    "state": yamaha.state
  }
  result = jsonify(msg)
  result.status_code = 200
    
  return result


""" Sends operation commands to the receiver and optionally waits for the result
"""
@app.route("/operation/<data>", methods = ["GET"], defaults={'resultcode': None})
@app.route("/operation/<data>/<resultcode>", methods = ["GET"])
def api_operation(data, resultcode):
  if len(data) != 3:
    result = jsonify({"status":500,"message":"Command must be exactly 3 bytes"})
    result.status_code = 500
    return result

  result = {
    'status': 200,
    'message': "Command sent"
  }
  
  result["result"] = yamaha.issueCommand(data, resultcode)

  result = jsonify(result)
  result.status_code = 200
  return result

""" Sends system commands to the receiver and optionally waits for the result
"""
@app.route("/system/<data>", methods = ["GET"], defaults = {'resultcode': None})
@app.route("/system/<data>/<resultcode>", methods = ["GET"])
def api_system(data, resultcode):
  if len(data) != 4:
    result = jsonify({"status":500,"message":"Command must be exactly 4 bytes"})
    result.status_code = 500
    return result

  result = {
    'status': 200,
    'message': "Command sent"
  }

  result["result"] = yamaha.issueCommand(data, resultcode)

  result = jsonify(result)
  result.status_code = 200
  return result

""" Obtains all or one specific report from the receiver
""" 
@app.route("/report", methods = ["GET"], defaults={"id": None})
@app.route("/report/<id>", methods = ["GET"])
def api_report(id):
  result = {"status": 200}
  
  if id is None:
    # Dump ALL available
    result["message"] = "Results retreived"  
    result["result"] = yamaha.getAllResults();
  else:  
    data = yamaha.getResult(id)
    if data is None:
      result["status"] = 404
      result["message"] = "No such report available"  
    else:
      result["message"] = "Result retreived"  
      result["result"] = data;
    
  result = jsonify(result)
  result.status_code = 200

  return result

if __name__ == "__main__":
  yamaha.init()
  app.debug = True
  app.run(host=cfg_ServerAddr, use_debugger=False, use_reloader=False)
  #while True:
  #  time.sleep(5)