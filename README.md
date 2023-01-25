# dbus-btbattery
This is a driver for VenusOS devices (As of yet only tested on Raspberry Pi running the VenusOS v2.92 image). 

The driver will communicate with a Battery Management System (BMS) via Bluetooth and publish this data to the VenusOS system. 

This project is derived from Louis Van Der Walt's dbus-serialbattery found here: https://github.com/Louisvdw/dbus-serialbattery

### Instructions
To get started you need a VenusOS device. I've only tried on Raspberry Pi, you can follow my instructions here: https://www.youtube.com/watch?v=yvGdNOZQ0Rw
to set one up.


You need to setup some depenacies on your VenusOS first

1) SSH to IP assigned to venus device<br/>

2) Resize/Expand file system<br/>
/opt/victronenergy/swupdate-scripts/resize2fs.sh

3) Update opkg<br/>
opkg update

4) Install pip<br/>
opkg install python3-pip

5) Install build essentials as bluepy has some C code that needs to be compiled<br/>
opkg install packagegroup-core-buildessential

6) Install glib-dev required by bluepy<br/>
opkg install libglib-2.0-dev

7) Install bluepi<br/>
pip3 install bluepy

8) Install git<br/>
opkg install git

9) Clone dbus-btbattery repo<br/>
git clone https://github.com/bradcagle/dbus-btbattery.git


You can now run ./dbus-btbattery.py 70:3e:97:08:00:62<br/>
replace 70:3e:97:08:00:62 with the Bluetooth address of your BMS/Battery

You can run ./scan.py to find Bluetooth devices around you


NOTES: This driver is far from complete, so some things will probably be broken. Also only JBD BMS is currenly supported 


