#!/bin/bash  
# Short script to install picamera and apriltags from source

# Make sure this is a Pi-Puck
if [[ $(whoami) != $ROBOTS_NAME && $SUDO_USER != $ROBOTS_NAME ]]; then
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
	cd apriltag
    python3 setup.py install
    cd ..
fi