#!/bin/bash

# Locate the correct ttyACM for IR Deluxe
TTY=$(dmesg | grep "FTDI" | grep attached | tail -n 1 | egrep -oe 'ttyUSB[0-9]')
if [ $? -eq 0 -a -e /dev/${TTY} ]; then
	./server.py --tty /dev/${TTY}
	exit $?
fi
echo "No USB-2-Serial device detected!"
exit 255
