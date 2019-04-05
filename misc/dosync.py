#!/usr/bin/python

import PyTango as Tg
from time import time,sleep
import sys


GSM_CONFIG = 0x00
GSM_CONFIG_1 = 0x01


cab = [ Tg.DeviceProxy(d) for d in ('bo/ct/pc-b1', 'bo/ct/pc-b2', 'bo/ct/pc-q') ]
powersupplies = [ Tg.DeviceProxy('bo/pc/'+d) for d in ('bend-1','bend-2','qh01','qh02','qv01', 'qv02') ]
trig = Tg.DeviceProxy('bo04/ti/evr-cpc1502-A')



def sync_proc():

    OKAY_COUNT = 0
    for ps in powersupplies:
      ms = ps['MachineState'].value
      if ms==GSM_CONFIG:
          OKAY_COUNT += 1
      else:
          msg = 'in state %02x but must be in GSM_CONFIG %02x' % (ms,GSM_CONFIG)
          print ps.dev_name(),  msg , ps          

    print '-'*80
    for ps in powersupplies:
      ms = ps['MachineState'].value
      print ps.dev_name(), ps.State(), ps.Status(), "%02x" % ms, "%02x" % \
          ps['ErrorCode'].value
     
    if OKAY_COUNT<len(powersupplies):
        print 'not all power supplies are ready to be synchronized, leaving...'
        return 1
    
    print 'proceed?',
    try:
        r = raw_input()
    except KeyboardInterrupt:
        r = None

    if r not in ('y','Y','yes'):
        print 'bailing out...'
        return

    print 'switch off event receiver', trig.dev_name()
    trig.Off()
    WAIT = 3
    for t in range(WAIT):
      print WAIT-t,
      sys.stdout.flush()
      sleep(1)
    print 'sending SYNC...'
    for c in cab:
        c.Command( ['PRT=25', 'SYNC' ])
    print 'switch on event receiver', trig.dev_name()
    trig.On()
    print 'synchronized'

sync_proc()