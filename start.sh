#!/bin/bash

UUID='ftE13S1G'
FILTER='ttyUSB*'

while true; do
	# Locate the correct ttyUSB for the projector
	for DEV in $(find /dev -name ${FILTER}); do
		if udevadm info -a --name $DEV | grep -q "$UUID"; then
			echo "Found it: $DEV"
			./server.py --tty $DEV
			echo "Server terminated"
		fi
	done

	echo "Sleeping 1s and trying again"
	sleep 1s
done

