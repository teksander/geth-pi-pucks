#!/bin/bash  
# Short script to install picamera and apriltags from source

# Run as SUDO
[ "$UID" -eq 0 ] || exec sudo bash "$0" "$@"

# Make sure this is a Pi-Puck
if [[ $SUDO_USER != $ROBOTS_NAME ]]; then
	echo "! Only run this script on robots !"
	exit 1
fi

if python3 -c "import picamera" &> /dev/null
then
    echo "Picamera is already installed"
else
	cd picamera-1.13
    python3 setup.py install
    cd ..
fi

if python3 -c "import apriltag" &> /dev/null
then
    echo "Apriltag is already installed"
else
    pip3  install apriltag-0.0.16-cp37-cp37m-linux_armv6l.whl
fi