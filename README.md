A simple REST api for sending Operation Commands to a Yamaha Receiver.

It does not contain much "internal" logic since it's meant to be implemented by
the user of the REST service. Think of this as a serial to REST interface with 
some simplifications put in, such has result code handling and config handling.

This project relies on pySerial and Flask and is in-use on a Raspberry Pi which
is hooked up to a RX-V1900 using a USB<->Serial interface.

To run it, edit the server.py to match the correct settings and then execute it
like so:

  python ./server.py

Once running, you can access the server on port 5000.

End points:

/
Provides model, software, state and port. Useful to see if the daemon is running
properly.

/operation/<op>
Executes a Operation Command on the receiver (power for example)

/operation/<op>/<result>
Executes a Operation Command on the receiver and waits until a result has been
reported by the receiver. WARNING! There is NO TIMEOUT for how long it will
wait.

/system/<op>
Executes a System Command on the receiver (setting absolute volume for example)

/system/<op>/<result>
Executes a System Command on the receiver and waits until a result has been
reported by the receiver. WARNING! There is NO TIMEOUT for how long it will 
wait.

/report
Retrives all received reports from the receiver

/report/<result>
Retreives a specific report code. If the code doesn't exist, an error is
returned. It will NEVER wait for a code.

Note!
Calling system or operation where you want a result will cause the daemon to
flush any existing result code before executing the op. The report endpoint 
will not flush anything.

Examples:

Power On zone 1:
================================================================================
/operation/E7E  ------->  {
                            "status": 200, 
                            "message": "Command sent"
                          }

Power On zone 1 with result:
================================================================================
/operation/E7E/20  ---->  {
                            "status": 200, 
                            "message": "Command sent", 
                            "result": {
                              "command": "20", 
                              "guard": "0", 
                              "valid": true, 
                              "type": "0", 
                              "data": "02"
                            }
                          }

Obtain last known state of power
================================================================================
/report/20  ----------->  {
                            "status": 200, 
                            "message": "Result retreived", 
                            "result": {
                              "command": "20", 
                              "guard": "0", 
                              "valid": true, 
                              "type": "0", 
                              "data": "02"
                            }
                          }
