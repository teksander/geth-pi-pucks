#!/bin/bash  
# Short script to install picamera and apriltags from source

# Run as SUDO
[ "$UID" -eq 0 ] || exec sudo bash "$0" "$@"

# Make sure this is a Pi-Puck
if [[ $SUDO_USER != "pi" ]]; then
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
    apt update
    apt install cmake
    cd apriltag
    mkdir build
    cd build
    cmake .. -DCMAKE_BUILD_TYPE=Release
    make
    sudo make install
    echo 'export LD_LIBRARY_PATH=$LD_LIBRARY_PATH:/home/pi/apriltag/build/lib' >> ~/.bashrc
fi
