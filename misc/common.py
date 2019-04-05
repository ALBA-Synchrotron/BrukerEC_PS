#!/usr/bin/python

import PyTango as Tg
import telnetlib
import logging
import socket
DB = Tg.Database()
from time import time,sleep

class BrukerRemote(object):
    def __init__(self, host, log=None):
        self.log =logging.getLogger('BrukerRemote.'+host) if log is None else log
        self.tel = telnetlib.Telnet(host)
        self.PS1 = '\n# '
        self.host = host

    def command(self, *args):
        cmd = " ".join(args)+'\n'
        self.log.debug('command %s', cmd)
        self.tel.write(cmd)
        self.tel.read_until(self.PS1)

    def cd(self, path):
        self.command('cd',path)

    def cat(self, *fname):
        ip = socket.gethostbyname(socket.gethostname())
        names = " ".join(fname)
        nc_cmd = 'nc -l -p10001 < %s\n' % names
        self.log.debug(nc_cmd)
        self.tel.write(nc_cmd)
        sok = socket.socket()
        self.log.debug('connecting to %s', self.host)
        sleep(0.05)
        sok.connect( (self.host, 10001) )
        fin = sok.makefile()
        self.log.debug('connected, now reading...')
        data = fin.read()
        self.tel.read_until(self.PS1)
        self.log.info('cat %s finished' % names)
        return data


def get_cabinets(pat='BrukerEC_PS/*'):
    cab_list = []
    for serv in DB.get_server_list(pat):
            dcl = DB.get_device_class_list(serv)
            for dev,cl in zip(dcl[::2],dcl[1::2]):
                if cl=='BrukerEC_Cabinet':
                    cab_list.append(Tg.DeviceProxy(dev))
    return cab_list

def get_hosts():
    host_list = []
    pat = 'BrukerEC_PS/*'
    for serv in DB.get_server_list(pat):
            dcl = DB.get_device_class_list(serv)
            for dev,cl in zip(dcl[::2],dcl[1::2]):
                    if cl=='BrukerEC_Cabinet':
                        prop = DB.get_device_property(dev, ('IpAddress',))
                        host_list.append(prop['IpAddress'][0])
    return host_list


if __name__=='__main__':
    print get_hosts()
