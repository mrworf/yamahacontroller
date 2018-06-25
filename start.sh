#!/bin/bash

while true; do
	# Locate the correct ttyACM for IR Deluxe
	TTY=$(dmesg | grep "FTDI" | grep attached | tail -n 1 | egrep -oe 'ttyUSB[0-9]')
	if [ $? -eq 0 -a -e /dev/${TTY} ]; then
		./server.py --tty /dev/${TTY}
		echo "Server terminated"
	fi
	echo "No USB-2-Serial device detected!"
	echo "Sleeping 1s and trying again"
	sleep 1s
done

