#!/usr/bin/python
# -*- coding: utf-8 -*-
from typing import Union

from time import sleep
from dbus.mainloop.glib import DBusGMainLoop
from threading import Thread
import sys

if sys.version_info.major == 2:
	import gobject
else:
	from gi.repository import GLib as gobject

# Victron packages
# from ve_utils import exit_on_error

from dbushelper import DbusHelper
from utils import logger
import utils
from battery import Battery
from jbdbt import JbdBt
from virtual import Virtual



logger.info("Starting dbus-btbattery")


def main():
	def poll_battery(loop):
		# Run in separate thread. Pass in the mainloop so the thread can kill us if there is an exception.
		poller = Thread(target=lambda: helper.publish_battery(loop))
		# Thread will die with us if deamon
		poller.daemon = True
		poller.start()
		return True


	def get_btaddr() -> str:
		# Get the bluetooth address we need to use from the argument
		if len(sys.argv) > 1:
			return sys.argv[1:]
		else:
			return False


	logger.info(
		"dbus-btbattery v" + str(utils.DRIVER_VERSION) + utils.DRIVER_SUBVERSION
	)

	btaddr = get_btaddr()
	if len(btaddr) == 2:
		battery: Battery = Virtual( JbdBt(btaddr[0]), JbdBt(btaddr[1]) )
	elif len(btaddr) == 3:
		battery: Battery = Virtual( JbdBt(btaddr[0]), JbdBt(btaddr[1]), JbdBt(btaddr[2]) )
	elif len(btaddr) == 4:
		battery: Battery = Virtual( JbdBt(btaddr[0]), JbdBt(btaddr[1]), JbdBt(btaddr[2]), JbdBt(btaddr[3]) )
	else:
		battery: Battery = JbdBt(btaddr[0])

	if battery is None:
		logger.error("ERROR >>> No battery connection at " + str(btaddr))
		sys.exit(1)

	battery.log_settings()

	# Have a mainloop, so we can send/receive asynchronous calls to and from dbus
	DBusGMainLoop(set_as_default=True)
	if sys.version_info.major == 2:
		gobject.threads_init()
	mainloop = gobject.MainLoop()

	# Get the initial values for the battery used by setup_vedbus
	helper = DbusHelper(battery)

	if not helper.setup_vedbus():
		logger.error("ERROR >>> Problem with battery " + str(btaddr))
		sys.exit(1)

	# Poll the battery at INTERVAL and run the main loop
	gobject.timeout_add(battery.poll_interval, lambda: poll_battery(mainloop))
	try:
		mainloop.run()
	except KeyboardInterrupt:
		pass


if __name__ == "__main__":
	main()
