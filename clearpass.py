#!/usr/bin/env python3
from bluepy.btle import Peripheral, DefaultDelegate, BTLEException
import struct
import argparse
import sys
import time
import binascii
import atexit



class delegate(DefaultDelegate):

	def __init__(self):
		DefaultDelegate.__init__(self)

	def handleNotification(self, cHandle, data):
		hex_data = binascii.hexlify(data)
		hex_string = hex_data.decode('utf-8')
		print(hex_string)


def main():


	if len(sys.argv) > 1:
		address = str(sys.argv[1])
	else:
		print("Need address arg")
		exit()


	try:
		print('Connecting to BMS ' + address)
		bt = Peripheral(address, addrType="public")
	except BTLEException as ex:
		time.sleep(10)
		bt = Peripheral(address, addrType="public")
	except BTLEException as ex:
		print('Connection failed')
		exit()
	else:
		print('Connected ', address)


	d = delegate()
	bt.setDelegate(d)

	bt.writeCharacteristic(0x15, b'\xdd\x5a\x09\x06\x4a\x31\x42\x32\x44\x34\xfe\x8a\x77', True)

	bt.waitForNotifications(10.0)
	


if __name__ == "__main__":
        main()
