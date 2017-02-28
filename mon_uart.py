#!/usr/bin/python
#
#mon_uart.py
#Montior the UART port, parse and forward XBEE frames
#
###############################################################################

import serial
import signal
import sys

#Handle CTRL-C
def signal_handler(signal, frame):
	print('mon_uart killed')
	ser.close()
	sys.exit(0)

##Main

#Exit handler
signal.signal(signal.SIGINT, signal_handler)

#Configure serial port
ser = serial.Serial(
	port='/dev/ttyO1',
	baudrate=9600,
	parity=serial.PARITY_NONE,
	stopbits=serial.STOPBITS_ONE,
	bytesize=serial.EIGHTBITS
)

ser.isOpen()

while(True):
	in_byte = ser.read()
	sys.stdout.write("%02X" % ord(in_byte))
	sys.stdout.flush()

