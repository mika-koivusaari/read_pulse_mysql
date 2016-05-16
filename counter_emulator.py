#!/usr/bin/python

import random

random.seed()

text=raw_input()
while text!='':
  if text=='GET':
    print "Counters: "+str(random.randint(0,15))+","+str(random.randint(0,15))
  text=raw_input()

