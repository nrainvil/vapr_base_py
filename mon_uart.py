#!/usr/bin/python
#
#mon_uart.py
#Montior the UART port, parse and forward XBEE frames
#
###############################################################################

import serial
import signal
import sys
import struct
import subprocess
import os
import datetime

#Globals
MAX_FRAME_LEN = 1024
PRINT_ASCII = False
VSITE = os.environ["VSITE"]
LOG_PATH = "/home/vapr/logs/"

#Handle CTRL-C
def signal_handler(signal, frame):
	print("\r\nmon_uart killed")
	ser.close()
	sys.exit(0)

#Write frame data to file and server
def write_frame_data(frame_data):
	frame_data_ba = bytearray(frame_data)

	#Open Server SSH connection
	ssh_pipe = subprocess.Popen(['ssh', '-e','none','data-log',VSITE], 
					stdin=subprocess.PIPE)

	#Open log file
	doy = datetime.datetime.now().timetuple().tm_yday
	year = datetime.datetime.now().timetuple().tm_year
	fname_out = str(doy) + "_" + str(year) + "_" + str(VSITE) + ".bin"
	fout = open(LOG_PATH + fname_out, 'ab')

	if(PRINT_ASCII):
		for c in frame_data:
			sys.stdout.write("%02X" % c)
		sys.stdout.write("\r\n")
		sys.stdout.flush()
	else:
		fout.write(frame_data_ba)
		ssh_pipe.communicate(input=frame_data_ba)

	fout.flush()
	fout.close()

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

#Watch Serial Port
in_frame = False
frame_len = -1
frame_type = -1
source_addr = -1
source_16 = -1
options = -1
i = 0
in_data = False
frame_data = []
frame_cksum = 0

while(True):

	#Read Input
	in_byte = ser.read()
	in_hex = ord(in_byte)
	if(ord(in_byte) == 0x7E and not in_frame):
		i = 0
		in_frame = True
		#sys.stdout.write("\r\nNew Frame\r\n")
	if(in_frame):
		if(i==1):
			len_upper = in_hex
		if(i==2):
			len_lower = in_hex
			frame_len = len_upper*0x100 + len_lower
			if(frame_len > MAX_FRAME_LEN): in_frame = False
		if(i==3):
			#sys.stdout.write("LEN:%d\r\n" % frame_len)
			frame_type = in_hex
			frame_cksum = in_hex
		if(i==4):
			#sys.stdout.write("Frame Type:%02X\r\n" % frame_type)
			source_addr = in_hex << 8*7
		if(i>4 and i<=11):
			source_addr += in_hex << 8*(7-(i-4))
		if(i==12):
			#sys.stdout.write("Source Addr:%016X\r\n" % source_addr)
			source_16 = in_hex << 8
		if(i==13):
			source_16 += in_hex
		if(i==14):
			#sys.stdout.write("Source 16:%04X\r\n" % source_16)
			options = in_hex
		if(i==15):
			#sys.stdout.write("Options: %02X\r\n" % options)
			frame_data = [in_hex]
			in_data = True
		if(i==frame_len+3):
			#sys.stdout.write("Data: ")
			#print '[{}]'.format(', '.join(hex(x) for x in frame_data))
			#Reset Counter
			i = 0
			in_frame = False
			in_data = False
			#CKSUM
			frame_cksum = frame_cksum & 0xFF
			frame_cksum = 0xFF - frame_cksum
			#sys.stdout.write("CKSUM1:%X " % frame_cksum)
			#sys.stdout.write("CKSUM2:%X\r\n" % in_hex)
			if(frame_cksum == in_hex): 
				write_frame_data(frame_data)
				#sys.stdout.write("CKSUM Matches!\r\n")
		elif(i>3):
			frame_cksum += in_hex
		if(i>15 and in_data):
			frame_data.append(in_hex)


	#sys.stdout.write("%d" % i)
	#sys.stdout.write(":%02X " % in_hex)
	#sys.stdout.flush()
	i += 1

