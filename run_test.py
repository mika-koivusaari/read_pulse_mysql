#!/usr/bin/python

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

