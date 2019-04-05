#!/usr/bin/python

import os
import sys
from time import time, strftime, sleep, gmtime
from pprint import pprint, pformat
from subprocess import Popen, PIPE
import pickle
import traceback

HTML_HEAD = '''<html>
<head><title>Power Supply Status</head><body>
<table>
<tr>
<th>Hostname</th>
<th>Status</th>
<th>last down</th><th></th>
<th>last up</th><th></th>
'''
HTML_TAIL = '</table></body></html>'

HOST_LIST = ( 'dpclt04b01', 'dpclt04c01',
  'dpcbo02b12', 'dpcbo02b13',
  'dpcbo06b11', 'dpcbo06b12',
  'dpcbo10b11', 'dpcbo10b12',
  'dpcbo14b07', 'dpcbo14b08',
  'dpcbo14b13',
)

def html_dump(fname, status, last_contact, last_down):
    fout = open('ping-report2.html','w')
    fout.write(HTML_HEAD)
    for host in HOST_LIST:
      dt, ds = last_down[host]
      ut, us = last_contact[host]
      fout.write(
'''<tr>
<td>%(host)s</td>
<td>%(status)s</td>
<td>%(down)s</td>
<td>%(down_s)s</td>
<td>%(up)s</td>
<td>%(up_s)s</td>
</tr>''' % dict(host=host, down=dt, down_s=ds, up=ut, up_s=us, status=status[host])
)
    fout.write(HTML_TAIL)
    fout.close()



last_contact = {}
last_down = {}
status = {}
uptime = {}
try:
  for host in HOST_LIST:
    last_contact[host] = '','never'
    last_down[host] ='','unknown'
    status[host] ='?'

  while True:
    start_t = time()
    for host in HOST_LIST:
      sys.stdout.flush()
      P = Popen('ping -c 1 -w 1 '+host, shell=True, stdout=PIPE)
      r = P.wait()
      P.stdout.read()
      t = time()
      dat =  t, strftime('%F %T')
      if r == 0:
        last_contact[host] = dat
        status[host] = 'up '
      else:
        last_down[host] = dat
        status[host] = 'down '

      down_t = last_down[host][0]
      up_t = last_contact[host][0]
      if down_t and up_t and up_t > down_t:
        status[host] += strftime('%T', gmtime(abs(up_t-down_t)))

    html_dump('ping-report.html', status, last_contact, last_down)
    sleep_t = max(0, time()-start_t-1)
    sleep(sleep_t)

except BaseException, exc:
  pprint(last_contact)
  traceback.print_exc()
  try:
    html_dump('ping-report.html', status, last_contact, last_down)
  except Exception, exc2:
    print exc2
  raise exc