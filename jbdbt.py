from bluepy.btle import Peripheral, DefaultDelegate, BTLEException, BTLEDisconnectError
from threading import Thread, Lock
from battery import Protection, Battery, Cell
from utils import *
from struct import *
import argparse
import sys
import time
import binascii
import atexit


class JbdProtection(Protection):
	def __init__(self):
		Protection.__init__(self)
		self.voltage_high_cell = False
		self.voltage_low_cell = False
		self.short = False
		self.IC_inspection = False
		self.software_lock = False

	def set_voltage_high_cell(self, value):
		self.voltage_high_cell = value
		self.cell_imbalance = (
			2 if self.voltage_low_cell or self.voltage_high_cell else 0
		)

	def set_voltage_low_cell(self, value):
		self.voltage_low_cell = value
		self.cell_imbalance = (
			2 if self.voltage_low_cell or self.voltage_high_cell else 0
		)

	def set_short(self, value):
		self.short = value
		self.set_cell_imbalance(
			2 if self.short or self.IC_inspection or self.software_lock else 0
		)

	def set_ic_inspection(self, value):
		self.IC_inspection = value
		self.set_cell_imbalance(
			2 if self.short or self.IC_inspection or self.software_lock else 0
		)

	def set_software_lock(self, value):
		self.software_lock = value
		self.set_cell_imbalance(
			2 if self.short or self.IC_inspection or self.software_lock else 0
		)



class JbdBtDev(DefaultDelegate, Thread):
	def __init__(self, address):
		DefaultDelegate.__init__(self)
		Thread.__init__(self)

		self.cellDataCallback = None
		self.generalDataCallback = None
		self.cellData = None
		self.generalData = None
		self.cellDataTotalLen = 0
		self.generalDataTotalLen = 0
		self.cellDataRemainingLen = 0
		self.generalDataRemainingLen = 0
		self.address = address
		self.interval = 5

		# Bluepy stuff
		self.bt = Peripheral()
		self.bt.setDelegate(self)

	def run(self):
		self.running = True
		timer = 0
		connected = False
		while self.running:
			if not connected:
				try:
					logger.info('Connecting ' + self.address)
					self.bt.connect(self.address, addrType="public")
					logger.info('Connected ' + self.address)
					connected = True
				except BTLEException as ex:
					logger.info('Connection failed')
					time.sleep(3)
					continue

			try:
				if self.bt.waitForNotifications(0.5):
					continue

				if (time.time() - timer) > self.interval:
					timer = time.time()
					result = self.bt.writeCharacteristic(0x15, b'\xdd\xa5\x03\x00\xff\xfd\x77', True)	# write x03 (general info)
					time.sleep(1) # Need time between writes?
					result = self.bt.writeCharacteristic(0x15, b'\xdd\xa5\x04\x00\xff\xfc\x77', True)	# write x04 (cell voltages)

			except BTLEDisconnectError:
				logger.info('Disconnected')
				connected = False
				continue


	def connect(self):
		self.start()

	def stop(self):
		self.running = False

	def addCellDataCallback(self, func):
		self.cellDataCallback = func

	def addGeneralDataCallback(self, func):
		self.generalDataCallback = func

	def handleNotification(self, cHandle, data):
		hex_data = binascii.hexlify(data)
		hex_string = hex_data.decode('utf-8')
		#print(hex_string)

		HEADER_LEN = 4 #[Start Code][Command][Status][Length]
		FOOTER_LEN = 3 #[16bit Checksum][Stop Code]

		# Route incoming BMS data

		# Cell Data
		if hex_string.find('dd04') != -1:
			# Because of small MTU size, the BMS data may not be transmitted in a single packet.
			# We use the 4th byte defined as "data len" in the BMS protocol to calculate the remaining bytes
			# that will be transmitted in the second packet 
			self.cellDataTotalLen = data[3] + HEADER_LEN + FOOTER_LEN
			self.cellDataRemainingLen = self.cellDataTotalLen - len(data)
			self.cellData = data
		elif hex_string.find('77') != -1 and len(data) == self.cellDataRemainingLen: # Look for the stop code, and check if the len matches P2Len (i.e. the remaining bytes)
			self.cellData = self.cellData + data
		# General Data
		elif hex_string.find('dd03') != -1:
			self.generalDataTotalLen = data[3] + HEADER_LEN + FOOTER_LEN
			self.generalDataRemainingLen = self.generalDataTotalLen - len(data)
			self.generalData = data
		elif hex_string.find('77') != -1 and len(data) == self.generalDataRemainingLen:
			self.generalData = self.generalData + data

		# Hack
		#elif len(data) == 20:
		#	self.cellDataCallback(data, 1)


		if self.cellData and len(self.cellData) == self.cellDataTotalLen:
			self.cellDataCallback(self.cellData)
			self.cellData = None

		if self.generalData and len(self.generalData) == self.generalDataTotalLen:
			self.generalDataCallback(self.generalData)
			self.generalData = None
			


class JbdBt(Battery):
	def __init__(self, address):
		Battery.__init__(self, 0, 0, address)

		self.protection = JbdProtection()
		self.type = "JBD BT"

		# Bluepy stuff
		self.bt = Peripheral()
		self.bt.setDelegate(self)

		self.mutex = Lock()
		self.generalData = None
		self.cellData = None

		self.address = address
		self.port = "/bt" + address.replace(":", "")
		self.interval = 5

		dev = JbdBtDev(self.address)
		dev.addCellDataCallback(self.cellDataCB)
		dev.addGeneralDataCallback(self.generalDataCB)
		dev.connect()


	def test_connection(self):
		return False

	def get_settings(self):
		result = self.read_gen_data()
		while not result:
			result = self.read_gen_data()
			time.sleep(1)
		self.max_battery_charge_current = MAX_BATTERY_CHARGE_CURRENT
		self.max_battery_discharge_current = MAX_BATTERY_DISCHARGE_CURRENT
		return result

	def refresh_data(self):
		result = self.read_gen_data()
		result = result and self.read_cell_data()
		return result

	def log_settings(self):
		# Override log_settings() to call get_settings() first
		self.get_settings()
		Battery.log_settings(self)

	def to_protection_bits(self, byte_data):
		tmp = bin(byte_data)[2:].rjust(13, zero_char)

		self.protection.voltage_high = 2 if is_bit_set(tmp[10]) else 0
		self.protection.voltage_low = 2 if is_bit_set(tmp[9]) else 0
		self.protection.temp_high_charge = 1 if is_bit_set(tmp[8]) else 0
		self.protection.temp_low_charge = 1 if is_bit_set(tmp[7]) else 0
		self.protection.temp_high_discharge = 1 if is_bit_set(tmp[6]) else 0
		self.protection.temp_low_discharge = 1 if is_bit_set(tmp[5]) else 0
		self.protection.current_over = 1 if is_bit_set(tmp[4]) else 0
		self.protection.current_under = 1 if is_bit_set(tmp[3]) else 0

		# Software implementations for low soc
		self.protection.soc_low = (
			2 if self.soc < SOC_LOW_ALARM else 1 if self.soc < SOC_LOW_WARNING else 0
		)

		# extra protection flags for LltJbd
		self.protection.set_voltage_low_cell = is_bit_set(tmp[11])
		self.protection.set_voltage_high_cell = is_bit_set(tmp[12])
		self.protection.set_software_lock = is_bit_set(tmp[0])
		self.protection.set_IC_inspection = is_bit_set(tmp[1])
		self.protection.set_short = is_bit_set(tmp[2])

	def to_cell_bits(self, byte_data, byte_data_high):
		# clear the list
		#for c in self.cells:
		#	self.cells.remove(c)
		self.cells: List[Cell] = []

		# get up to the first 16 cells
		tmp = bin(byte_data)[2:].rjust(min(self.cell_count, 16), zero_char)
		for bit in reversed(tmp):
			self.cells.append(Cell(is_bit_set(bit)))

		# get any cells above 16
		if self.cell_count > 16:
			tmp = bin(byte_data_high)[2:].rjust(self.cell_count - 16, zero_char)
			for bit in reversed(tmp):
				self.cells.append(Cell(is_bit_set(bit)))

	def to_fet_bits(self, byte_data):
		tmp = bin(byte_data)[2:].rjust(2, zero_char)
		self.charge_fet = is_bit_set(tmp[1])
		self.discharge_fet = is_bit_set(tmp[0])

	def read_gen_data(self):
		self.mutex.acquire()
		if self.generalData == None:
			self.mutex.release()
			return False

		gen_data = self.generalData[4:]
		self.mutex.release()

		if len(gen_data) < 27:
			return False

		(
			voltage,
			current,
			capacity_remain,
			capacity,
			self.cycles,
			self.production,
			balance,
			balance2,
			protection,
			version,
			self.soc,
			fet,
			self.cell_count,
			self.temp_sensors,
		) = unpack_from(">HhHHHHhHHBBBBB", gen_data, 0)
		self.voltage = voltage / 100
		self.current = current / 100
		self.capacity_remain = capacity_remain / 100
		self.capacity = capacity / 100
		self.to_cell_bits(balance, balance2)
		self.version = float(str(version >> 4 & 0x0F) + "." + str(version & 0x0F))
		self.to_fet_bits(fet)
		self.to_protection_bits(protection)
		self.max_battery_voltage = MAX_CELL_VOLTAGE * self.cell_count
		self.min_battery_voltage = MIN_CELL_VOLTAGE * self.cell_count

		for t in range(self.temp_sensors):
			temp1 = unpack_from(">H", gen_data, 23 + (2 * t))[0]
			self.to_temp(t + 1, kelvin_to_celsius(temp1 / 10))

		return True

	def read_cell_data(self):
		self.mutex.acquire()

		if self.cellData == None:
			self.mutex.release()
			return False

		cell_data = self.cellData[4:]
		self.mutex.release()

		if len(cell_data) < self.cell_count * 2:
			return False

		for c in range(self.cell_count):
			try:
				cell_volts = unpack_from(">H", cell_data, c * 2)
				if len(cell_volts) != 0:
					self.cells[c].voltage = cell_volts[0] / 1000
			except struct.error:
				self.cells[c].voltage = 0

		return True

	def cellDataCB(self, data):
		self.mutex.acquire()
		self.cellData = data
		self.mutex.release()

	def generalDataCB(self, data):
		self.mutex.acquire()
		self.generalData = data
		self.mutex.release()



# Unit test
if __name__ == "__main__":


	batt = JbdBt( "70:3e:97:08:00:62" )
	#batt = JbdBt( "a4:c1:37:40:89:5e" )
	#batt = JbdBt( "a4:c1:37:00:25:91" )

	batt.get_settings()

	while True:
		batt.refresh_data()

		print("Cells " + str(batt.cell_count) )

		for c in range(batt.cell_count):
			print( str(batt.cells[c].voltage) + "v", end=" " )

		print("")


		time.sleep(5)



