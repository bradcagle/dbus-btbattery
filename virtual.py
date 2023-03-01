from battery import Protection, Battery, Cell
from utils import *
from struct import *
import argparse
import sys
import time
import binascii
import atexit



class Virtual(Battery):
	def __init__(self, b1=None, b2=None, b3=None, b4=None):
		Battery.__init__(self, 0, 0, 0)

		self.type = "Virtual"
		self.port = "/" + self.type

		self.batts = []
		if b1:
			self.batts.append(b1)
		if b2:
			self.batts.append(b2)
		if b3:
			self.batts.append(b3)
		if b4:
			self.batts.append(b4)
		

	def test_connection(self):
		return False


	def get_settings(self):
		self.voltage = 0
		self.current = 0
		self.cycles = 0
		self.production = 0
		self.soc = 0
		self.cell_count = 0
		self.capacity = 0
		self.capacity_remain = 0
		self.charge_fet	= True
		self.discharge_fet = True

		result = False
		# Loop through all batteries
		for b in self.batts:
			result = b.get_settings();
			if result:
				# Add battery voltages together
				self.voltage += b.voltage
			
				# Add cell counts
				self.cell_count += b.cell_count

				# Add current values, and div by cell count after the loop to get avg
				self.current += b.current

				# Use the highest cycle count 
				if b.cycles > self.cycles:
					self.cycles = b.cycles
				
				# Use the lowest capacity value
				if b.capacity < self.capacity or self.capacity == 0:
					self.capacity = b.capacity

				# Use the lowest capacity_remain value
				if b.capacity_remain < self.capacity_remain or self.capacity_remain == 0:
					self.capacity_remain = b.capacity_remain

				# Use the lowest SOC value
				if b.soc < self.soc or self.soc == 0:
					self.soc = b.soc

				self.charge_fet &= b.charge_fet 
				self.discharge_fet &= b.discharge_fet 


		self.cells = [None]*self.cell_count

		bcnt = len(self.batts)

		if bcnt:
			# Avg the current
			self.current /= bcnt

			# Use the temp sensors from the first battery?
			self.temp_sensors = self.batts[0].temp_sensors
			self.temp1 = self.batts[0].temp1
			self.temp2 = self.batts[0].temp2


		self.max_battery_voltage = MAX_CELL_VOLTAGE * self.cell_count
		self.min_battery_voltage = MIN_CELL_VOLTAGE * self.cell_count

		self.max_battery_charge_current = MAX_BATTERY_CHARGE_CURRENT
		self.max_battery_discharge_current = MAX_BATTERY_DISCHARGE_CURRENT
		return result


	def refresh_data(self):
		result = self.get_settings()

		# Clear cells list
		self.cells: List[Cell] = []

		result2 = False
		# Loop through all batteries
		for b in self.batts:
			result2 = b.refresh_data();
			if result2:
				# Append cells list
				self.cells += b.cells


		result = result and result2
		return result


	def log_settings(self):
		# Override log_settings() to call get_settings() first
		self.get_settings()
		Battery.log_settings(self)





# Unit test
if __name__ == "__main__":
	from jbdbt import JbdBt

	batt1 = JbdBt( "70:3e:97:08:00:62" )
	batt2 = JbdBt( "a4:c1:37:40:89:5e" )

	vbatt = Virtual(batt1, batt2)

	vbatt.get_settings()

	print("Cells " + str(vbatt.cell_count) )
	print("Voltage " + str(vbatt.voltage) )

	while True:
		vbatt.refresh_data()

		print("Cells " + str(vbatt.cell_count) )
		print("Voltage " + str(vbatt.voltage) )
		print("Current " + str(vbatt.current) )
		print("Charge FET " + str(vbatt.charge_fet) )
		print("Discharge FET " + str(vbatt.discharge_fet) )

		for c in range(vbatt.cell_count):
			print( str(vbatt.cells[c].voltage) + "v", end=" " )

		print("")


		time.sleep(5)



