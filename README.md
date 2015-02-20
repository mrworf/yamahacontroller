A simple REST api for sending Operation Commands to a Yamaha Receiver.
It does not contain much "internal" logic since it's meant to be
implemented by the user of the REST service. Think of this as a serial
to REST interface (with some simplifications put in, such has result
code handling and config handling)

This project relies on pySerial and Flask and is in-use on a Raspberry Pi
which is hooked up to a RX-V1900 using a USB<->Serial interface.

To run it, edit the server.py to match the correct settings and then
execute it like so:

  python ./server.py

Once running, you can access the server on port 5000.

The base URL will return the state of the receiver (not much details)
Using /operation/<3 character hex code> it possible to issue 
operation commands, such as E7E (which is "Main On" for RX-V1900)
The returned values are in the form of json and needs to be handled
by the caller.
