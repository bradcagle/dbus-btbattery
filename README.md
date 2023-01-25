# dbus-btbattery
This is a driver for VenusOS devices (As of yet only tested on Raspberry Pi running the VenusOS v2.92 image). 

The driver will communicate with a Battery Management System (BMS) via Bluetooth and publish this data to the VenusOS system. 

This project is derived from Louis Van Der Walt's dbus-serialbattery found here: https://github.com/Louisvdw/dbus-serialbattery

### Instructions
To get started you need a VenusOS device. I've only tried on Raspberry Pi, you can follow my instructions here: https://www.youtube.com/watch?v=yvGdNOZQ0Rw
to set one up.


You need to setup some depenacies on your VenusOS first

1) SSH to IP assigned to venus device

2) Resize/Expand file system
/opt/victronenergy/swupdate-scripts/resize2fs.sh

3) Update opkg
opkg update

4) Install pip
opkg install python3-pip

5) Install build essentials as bluepy has some C code that needs to be compiled 
opkg install packagegroup-core-buildessential

6) Install glib-dev required by bluepy
opkg install libglib-2.0-dev

7) Install bluepi
pip3 install bluepy

8) Install git
opkg install git

9) Clone dbus-btbattery repo
git clone https://github.com/bradcagle/dbus-btbattery.git


