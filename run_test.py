#!/usr/bin/python

#Depends on socat.
#Start socat to emulate serial interface and start python script to emulate hardware.
#socat open two pipes in current directory, daemon, to which the daemon connects,
#and hardware, to which the hw emulator connects
import subprocess
import shlex
import time

socatprocess=subprocess.Popen(args=shlex.split("socat -d -d pty,link=./hardware,raw,echo=0 pty,link=./daemon,raw,echo=0"))
print "Started socat."
emulator_process=subprocess.Popen(args=shlex.split("./counter_emulator.py >./hardware <./hardware"))
print "Started counter emulator."

s=raw_input("Press enter to exit.")

socatprocess.terminate()
emulator_process.terminate()

