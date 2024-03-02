from bluepy.btle import Peripheral, DefaultDelegate, BTLEException, BTLEDisconnectError, AssignedNumbers
from threading import Thread, Lock
from battery import Protection, Battery, Cell
from utils import *
from struct import *
import argparse
import sys
import time
import binascii
import atexit


OUTGOING_HEADER = b'\xaa\x55\x90\xeb'
INCOMING_HEADER = b'\x55\xaa\xeb\x90'

MAX_COMMAND_TIMEOUT_SECONDS = 5
MAX_STATE_LIFE_SECCONDS = 5

COMMAND_REQ_EXTENDED_RECORD = 0x96
COMMAND_REQ_DEVICE_INFO = 0x97
COMMAND_REQ_CHARGE_SWITCH = 0x1d
COMMAND_REQ_DISCHARGE_SWITCH = 0x1e

RESPONSE_ACK = 0xc8
RESPONSE_EXTENDED_RECORD = 0x01
RESPONSE_CELL_DATA = 0x02
RESPONSE_DEVICE_INFO_RECORD = 0x03


class JkBtDev(DefaultDelegate, Thread):
	def __init__(self, address):
		DefaultDelegate.__init__(self)
		Thread.__init__(self)

		self.incomingData = bytearray()
		self.address = address

		# Bluepy stuff
		self.bt = Peripheral()
		#self.bt.setDelegate(self)
		self.bt.withDelegate(self)

	def run(self):
		self.running = True
		timer = 0
		connected = False
		while self.running:
			if not connected:
				try:
					logger.info('Connecting ' + self.address)
					self.bt.connect(self.address, addrType="public")
					self.bt.setMTU(331)

					self.incomingData = bytearray()
					self.chargeSwitch = None
					self.dischargeSwitch = None
					self.commnadAcked = False

					#serviceJkbms = self.bt.getServiceByUUID(AssignedNumbers.genericAccess)

					serviceNotifyUuid = 'ffe0'
					serviceNotify = self.bt.getServiceByUUID(serviceNotifyUuid)

					characteristicConnectionUuid = 'ffe1'
					characteristicConnection = serviceNotify.getCharacteristics(characteristicConnectionUuid)[0]
					self.handleConnection = characteristicConnection.getHandle()

					# make subscription, dynamic search for the respective 2902 characteristics
					characteristicConnectionDescriptor = characteristicConnection.getDescriptors(AssignedNumbers.client_characteristic_configuration)[0]
					characteristicConnectionDescriptorHandle = characteristicConnectionDescriptor.handle

					self.bt.writeCharacteristic(characteristicConnectionDescriptorHandle, b'\x01\x00')

					logger.info('Connected ' + self.address)
					connected = True

					self.sendCommand(COMMAND_REQ_DEVICE_INFO)
					self.sendCommand(COMMAND_REQ_EXTENDED_RECORD)


				except BTLEException as ex:
					logger.info('Connection failed')
					time.sleep(3)
					continue

			try:

				if self.bt.waitForNotifications(0.5):
					continue

			except BTLEDisconnectError:
				logger.info('Disconnected')
				connected = False
				continue


	def connect(self):
		self.start()

	def stop(self):
		self.running = False


	def crc(self, data):
		sum = 0
		for b in data:
			sum += b

		return sum&0xff


	def readString(self, data, start, maxlen):
		ret = ""
		i = start
		while (i < start + maxlen) and (data[i] != 0):
			ret += f'{data[i]:c}'
			i += 1

		return ret



	def sendCommand(self, address, value=0, length=0):

		self.commandAcked = False

		frame = bytearray()
		frame += OUTGOING_HEADER
		frame += bytes([
			address&0xff, # address
			length&0xff, # length
			value&0xff, (value>>8)&0xff, (value>>16)&0xff, (value>>24)&0xff # value
			])
		frame += bytes([
			0, 0, 0, 0, 0, 0, 0, 0, 0, # fill up to 19 Bytes
			self.crc(frame) # CRC8
			])

		log = binascii.hexlify(frame)

		try:
			self.bt.writeCharacteristic(self.handleConnection, frame)
		except:
			logger.info(f'cannot send command: {log}')
			return

		t = time.time()
		timeout = t + MAX_COMMAND_TIMEOUT_SECONDS
		while (not self.commandAcked) and (t < timeout):
			self.bt.waitForNotifications(timeout - t)
			t = time.time()




	def handleNotification(self, handle, data):

		if (data.startswith(OUTGOING_HEADER)) and (len(data) == 20):
			# ACK/NACK packet inside one datagram
			self.incomingData = data
			self.processData()
			self.incomingData = bytearray()
		else:
			if (len(self.incomingData) == 0) and (not data.startswith(INCOMING_HEADER)):
				# ignore wrong start
				d = binascii.hexlify(data)
				logger.info('received missaligned data: {d}')
				return

			self.incomingData += data
			if len(self.incomingData) == 300:
				self.processData()
				self.incomingData = bytearray()

	def processData(self):
		# check CRC8
		if self.crc(self.incomingData[:-1]) != self.incomingData[len(self.incomingData)-1]:
			# invalid CRC8
			d = binascii.hexlify(self.incomingData)
			logger.info('received packet with invaid CRC8: {d}')
			return

		address = self.incomingData[4]

		if address == RESPONSE_ACK:
			if (self.incomingData[5] == 0x01) and (self.incomingData[6] == 0x01):
				print("ACK")
				self.commandAcked = True
				return
			logger.info('received NACK')
		elif address == RESPONSE_DEVICE_INFO_RECORD:
			print("DEVICE_INFO_RECORD")

			deviceModel = self.readString(self.incomingData, 6, 16)
			hardwareVer = self.readString(self.incomingData, 22, 8)
			softwareVer = self.readString(self.incomingData, 30, 8)
			upTime = int.from_bytes(self.incomingData[38:42], byteorder='little')
			powerOnTimes = int.from_bytes(self.incomingData[42:46], byteorder='little')
			deviceName = self.readString(self.incomingData, 46, 16)
			devicePass = self.readString(self.incomingData, 62, 16)
			manufacturingDate = self.readString(self.incomingData, 78, 8)
			serialNum = self.readString(self.incomingData, 86, 11)
			password = self.readString(self.incomingData, 97, 5)
			userData = self.readString(self.incomingData, 102, 16)
			setupPass = self.readString(self.incomingData, 118, 16)
			

			print(deviceModel)
			print(deviceName)
			print(devicePass)

			self.name = deviceName
		elif address == RESPONSE_EXTENDED_RECORD:
			print("DEVICE_EXTENDED_RECORD")
			self.chargeSwitch = True if (self.incomingData[118] == 0x01) else False
			self.dischargeSwitch = True if (self.incomingData[122] == 0x01) else False
		elif address == RESPONSE_CELL_DATA:
			print("DEVICE_CELL_DATA")
			soc = self.incomingData[141] # SoC
			totalVol = int.from_bytes(self.incomingData[118:122], byteorder='little')/1000 # Voltage
			print(totalVol)
			cellVol = [0] * 16
			for i in range(0,16):
				cellVol[i] = int.from_bytes(self.incomingData[6+2*i:8+2*i], byteorder='little')/1000 # Cell Voltage
			chgCurr = int.from_bytes(self.incomingData[126:130], byteorder='little', signed=True)/1000 # Current
			if chgCurr < 0:
				disCurr = - chgCurr
				chgCurr = 0
			capacityAH = int.from_bytes(self.incomingData[142:146], byteorder='little')/1000 # remaining capacity AH
			cycleAH = int.from_bytes(self.incomingData[154:158], byteorder='little')/1000 # cycle AH (accumulated value over master reset)
			tempMOSFET = int(int.from_bytes(self.incomingData[134:136], byteorder='little', signed=True)/10) # MOSFET temperature
			tempT1 = int(int.from_bytes(self.incomingData[130:132], byteorder='little', signed=True)/10) # T1 temperature
			tempT2 = int(int.from_bytes(self.incomingData[132:134], byteorder='little', signed=True)/10) # T2 temperature
			chgMOSFET = self.incomingData[166] # Charging MOSFET status flag
			if (chgMOSFET == 0) and (not self.chargeSwitch):
				chgMOSFET = 15
			disMOSFET = self.incomingData[167] # Discharge MOSFET status flag
			if (disMOSFET == 0) and (not self.dischargeSwitch):
				disMOSFET = 15
			balSt = 0 if (self.incomingData[140] == 0) else 4
			disPower = int(int.from_bytes(self.incomingData[122:126], byteorder='little')/1000) # Power
			if chgCurr > 0:
				chgPower = disPower
				disPower = 0
			cellHigh = self.incomingData[62]+1 # Cell High number
			cellHighVol = cellVol[cellHigh-1] # Cell High Voltage
			cellLow = self.incomingData[63]+1 # Cell Low number
			cellLowVol = cellVol[cellLow-1] # Cell Low Voltage
			cellAvgVol = int.from_bytes(self.incomingData[58:60], byteorder='little')/1000 # Cell Average
			cellDiffVol = int.from_bytes(self.incomingData[60:62], byteorder='little')/1000 # Cell diff

			errorState = int.from_bytes(self.incomingData[136:138], byteorder='big')
			if (errorState & 0x0003 != 0) and (chgMOSFET != 1): # bit 0 - charge over temp & bit 1 - charge under temp
				chgMOSFET = 6
			if (errorState & 0x0008 != 0) and (disMOSFET != 1): # bit 3 - cell undervoltage
				disMOSFET = 2
			if (errorState & 0x0010 != 0) and (chgMOSFET != 1): # bit 4 - cell overvoltage
				chgMOSFET = 2
			if (errorState & 0x0040 != 0) and (chgMOSFET != 1): # bit 6 - charge overcurrent
				chgMOSFET = 3
			if (errorState & 0x0800 != 0): # bit 9 - current sensor annomaly
				ignore = 1
			if (errorState & 0x2000 != 0) and (disMOSFET != 1): # bit 13 - discharge over current
				disMOSFET = 3
			if (errorState & 0x8000 != 0) and (disMOSFET != 1): # bit 15 - discharge over temp
				disMOSFET = 6
			if (errorState & 0x57a4 != 0):
				logger.info(f'unknown system alarms: {errorState:x}')

			


class JkBt(Battery):
	def __init__(self, address):
		Battery.__init__(self, 0, 0, address)

		self.protection = None
		self.type = "JK BT"

		# Bluepy stuff
		self.bt = Peripheral()
		self.bt.setDelegate(self)

		self.mutex = Lock()

		self.address = address
		self.port = "/bt" + address.replace(":", "")
		self.interval = 5

		dev = JkBtDev(self.address)
		dev.connect()


	def test_connection(self):
		return False

	def get_settings(self):
		return False

	def refresh_data(self):
		return False

	def log_settings(self):
		# Override log_settings() to call get_settings() first
		self.get_settings()
		Battery.log_settings(self)






# Unit test
if __name__ == "__main__":


	batt = JkBt( "c8:47:8c:e5:93:6c" )

	batt.get_settings()

	while True:
		batt.refresh_data()


		print("")


		time.sleep(5)



