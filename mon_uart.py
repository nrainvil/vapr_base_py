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
import math

#Globals
MAX_FRAME_LEN = 1024
PRINT_ASCII = False
WRITE_FILE = False
#VSITE = os.environ["VSITE"]
VSITE = "VB004"
LOG_PATH = "/home/vapr/logs/"
cmd_addr = 12

#Handle CTRL-C
def signal_handler(signal, frame):
	print("\r\nmon_uart killed")
	ser.close()
	sys.exit(0)

#Write frame data to file and server
def write_frame_data(frame_data, ssh_pipe):
	frame_data_ba = bytearray(frame_data)


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
		if(WRITE_FILE):
			for c in frame_data:
				fout.write("%02X" % c)
		#ssh_pipe.communicate(input=frame_data_ba)
		try:
			ssh_pipe.stdin.write(frame_data_ba)
		except:
			print "Unexpected Error:",sys.exc_info()[0]
			ssh_pipe.terminate()
	if(WRITE_FILE):
		fout.write("\n")
	fout.flush()
	fout.close()

##Main

#Exit handler
signal.signal(signal.SIGINT, signal_handler)

#Configure serial port
ser = serial.Serial(
	port='/dev/ttyO5',
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

#Open Server SSH connection
#ssh_pipe = subprocess.Popen(['ssh', '-e','none','data-log',VSITE], 
#				stdin=subprocess.PIPE)
ssh_pipe = subprocess.Popen(['ssh','-o','StrictHostKeyChecking=no','-e','none','data-log',VSITE],
				stdin=subprocess.PIPE)

out_header=b"\x7E"

out_dest_opts="\x10\x01"
out_dest_opts2 = "\xFF\xFE\x00\x00"
out_addr = "\x00\x13\xA2\x00\x41\x25\xD5\x13"
out_cksum = 1041 #Sum of Dest and Opts 


while(True):
	#Reset Watchdog
	#os.system("sudo touch /dev/watchdog")

	#Check ssh process
	if(ssh_pipe.poll() != None):
		print "SSH process died, restarting"
		ssh_pipe = subprocess.Popen(
				['ssh', '-e','none','data-log',VSITE], 
				stdin=subprocess.PIPE)
	else:
		#Check for command
		fcmd = open(LOG_PATH + "cmd_buff.txt", "rw+")
		cmd_line = fcmd.readline()
		if cmd_line != "" :
			cmd_parts = cmd_line.split(";");
			cmd_addr = int(cmd_parts[0])
			cmd_line = cmd_parts[1]

			#Choose Dest Radio
			if(cmd_addr==11):
				out_addr = "\x00\x13\xA2\x00\x41\x25\xD5\x13"
				out_cksum = 1041 #Sum of Dest and Opts 
			elif(cmd_addr==12):
				out_addr = "\x00\x13\xA2\x00\x41\x72\x9F\xD3"
				out_cksum = 526 + 730 #Sum of Dest and Opts 
			elif(cmd_addr==13):
				out_addr = "\x00\x13\xA2\x00\x41\x72\x9F\xCD"
				out_cksum = 526 + 724 #Sum of Dest and Opts 
			elif(cmd_addr==14):
				out_addr = "\x00\x13\xA2\x00\x41\x72\x9F\xBB"
				out_cksum = 526 + 706 #Sum of Dest and Opts 

			#Calc Checksum
			ser.write(out_header)
			ser.write(chr((len(cmd_line)+13)/255))
			ser.write(chr((len(cmd_line)+13)%255))
			ser.write(out_dest_opts)
			ser.write(out_addr)
			ser.write(out_dest_opts2)

			for c in cmd_line:
				if ord(c) != 10:
					ser.write(c)
					out_cksum += ord(c)
			out_cksum %= 0x100
			out_cksum = 0xFF - out_cksum
			ser.write(chr(out_cksum))
		fcmd.truncate(0)
		fcmd.close()

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
					write_frame_data(frame_data,ssh_pipe)
					#sys.stdout.write("CKSUM Matches!\r\n")
			elif(i>3):
				frame_cksum += in_hex
			if(i>15 and in_data):
				frame_data.append(in_hex)


		#sys.stdout.write("%d" % i)
		#sys.stdout.write(":%02X " % in_hex)
		#sys.stdout.flush()
		i += 1

