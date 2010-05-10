#!/usr/bin/env python
# -*- coding: utf-8 -*-
#       "$Name: lkrause@cells.es $";
#       "$Header:  $";
#=============================================================================
#
# file :        BrukerBend_PS.py
#
# description : Python source for the BrukerBend_PS and its commands.
#                The class is derived from Device. It represents the
#                CORBA servant object which will be accessed from the
#                network. All commands which can be executed on the
#                BrukerBend_PS are implemented in this file.
#
# project :     TANGO Device Server
#
# $Author:  Lothar Krause <lkrause@cells.es> $
#
# $Revision:  $
#
# $Log:  $
#
# copyleft :    European Synchrotron Radiation Facility
#               BP 220, Grenoble 38043
#               FRANCE
#
#=============================================================================
#               This file is generated by POGO
#       (Program Obviously used to Generate tango Object)
#
#         (c) - Software Engineering Group - ESRF
#=============================================================================
#


class Release(object):
    pass

"""
Used to provide a single Tango server for both bending magnet power supplies.
It allows also to synchronize dipoles and quadrupoles PS at the same time.
"""
import PyTango as Tg
import sys
import ps_standard as PS
import ps_util as PU
from time import time
from pprint import pprint

AQ_ALARM = Tg.AttrQuality.ATTR_ALARM
AQ_WARNING = Tg.AttrQuality.ATTR_WARNING
AQ_VALID = Tg.AttrQuality.ATTR_VALID
AQ_INVALID = Tg.AttrQuality.ATTR_INVALID
AQ_CHANGING = Tg.AttrQuality.ATTR_CHANGING

DevState = Tg.DevState
ON = Tg.DevState.ON
OFF = Tg.DevState.OFF
STANDBY = Tg.DevState.STANDBY
ALARM = Tg.DevState.ALARM
MOVING = Tg.DevState.MOVING

BEND_FAULT_STATE = frozenset( (0x0c, 0x0d) )
BEND_ON_STATE = 0x0a
BEND_OFF_STATE = 0x03

BEND_ON_T = {
    0x03 : 5*60,
    0x0A : 0.0
}

BEND_OFF_T = {
    0x0A : 5*60.0,
    0x0B : 5*60.0,
    0x0E : 5*60.0,
    0x0F : 5*60.0
}

CAB_ON_STATE = 0x06
CAB_OFF_STATE = 0x01
CAB_FAULT_STATE = frozenset( (0x08,) )

CAB_ON_T = {
    0x06 : 0.0,
    0x01 : 5 * 60.0
}

CAB_OFF_T = {
    0x01 : 0.0, # IDLE (DC off)
    0x0B : 5*60.0,
    0x0E : 5*60.0,
    0x0F : 5*60.0
}




#==================================================================
#   BrukerBend_PS Class Description:
#
#         Bundles together the Current and CurrentSetpoint attributes of a number of power supplies in order to behave as a single device.
#         This is for example used by to provide a single device for ALBAs Bruker PS.
#
#==================================================================
#       Device States Description:
#
#   DevState.ON :     on, if all on
#   DevState.OFF :    off, if both are off.
#   DevState.ALARM :  default.
#==================================================================

SWITCH_NEUTRAL = 'sw 0'
SWITCH_ON = 'sw on'
SWITCH_OFF = 'sw off'
DB = PS.DATABASE

tv2time = lambda x: x.tv_sec + x.tv_usec/1000.0

class BrukerBend_PS(PS.PowerSupply):

#------------------------------------------------------------------
#       Device constructor
#------------------------------------------------------------------
    def __init__(self,cl, name):
        PS.PowerSupply.__init__(self,cl,name)
        BrukerBend_PS.init_device(self)

    def tell_my(self, aname):
        if aname == 'RegulationPrecision':
            return 0.05
        else:
            return 1.0

    def init_device(self):
        PS.PowerSupply.init_device(self)
        self.__shiver = {}
        self.switching = SWITCH_NEUTRAL
        self.switch_eta = 0
        self._aWaveGeneration = None

        self.bend1 = Tg.DeviceProxy(self.Bend1)
        self.bend2 = Tg.DeviceProxy(self.Bend2)

        def find_cab(ec_name):
            serv_name = self.bend1.adm_name().partition('/')[2]
            ls = DB.get_device_class_list(serv_name)
            dictum = dict(zip(ls[1::2],ls[::2]))
            return dictum['BrukerEC_Cabinet']

            ## finds name of BrukerEC_Cabinet corresponding to
            ## the device name specified
        self.bend1.cab = Tg.DeviceProxy(find_cab(self.bend1))
        self.bend2.cab = Tg.DeviceProxy(find_cab(self.bend2))

        self.RegulationPrecision = self.tell_my('RegulationPrecision')
        self.Inominal = self.bend1.read_attribute('CurrentNominal').value
        self.cabq = Tg.DeviceProxy(self.QuadCabinet)
        self.trig = Tg.DeviceProxy(self.Trigger)

        # prepares also DeviceProxy for the Synchronization
        self.sync_devices = [ self.bend1.cab, self.bend2.cab, self.cabq ]

        self.errors = PU.UniqList()

    def Lock(self):
        self.bend1.lock()
        self.bend2.lock()
        self.cab1.lock()
        self.cab2.lock()

    def Unlock(self):
        self.bend1.unlock()
        self.bend2.unlock()
        self.cab1.unlock()
        self.cab2.unlock()

    def shiver(self, aname, x,y):
        self.__shiver.setdefault(aname,0)
        self.__shiver[aname] += 1
        return (x if self.__shiver[aname] % 2 else y)

    def shiver_name(self, aname):
        return (self.bend1,'bend1') if self.__shiver[aname] % 2 else (self.bend2, 'bend2')


    def distill_ne_quality(self, quality, x,y):
        return AQ_ALARM if x.value != y.value else quality

    def distill_waveform_quality(self, quality, x,y):
            return AQ_ALARM if tuple(x.value) != tuple(y.value) else quality


    def read_attr1(self, bend, attr):
        aname = attr.get_name()
        try:
            return bend.read_attribute(aname)
        except Tg.DevFailed, fail:
            reason = fail[0].reason
            if reason == 'API_AttrNotAllowed':
                return
            elif reason == 'PyDs_PythonError':
                return
#                raise PS.PS_Exception(fail[0].desc)
            else:
                raise

    def read_attribute(self, attr, qual_fun=None):
        aname = attr.get_name()
        aval1 = self.read_attr1(self.bend1, attr)
        aval2 = self.read_attr1(self.bend2, attr)
        if aval1 is None or aval2 is None:
            attr.set_quality(AQ_INVALID)
            return
        quality = PS.combine_aq(aval1.quality, aval2.quality)
        timestamp = min(tv2time(aval1.time),tv2time(aval2.time))

        if qual_fun:
            quality = qual_fun(quality, aval1, aval2)
        else:
            quality = self.distill_ne_quality(quality, aval1, aval2)


        x = self.shiver(aname, aval1.value, aval2.value)
        if not aval1.w_value is None and not aval2.w_value is None:
            w = self.shiver(aname+'_W', aval1.w_value, aval2.w_value)
            attr.set_write_value(w)
        if quality!=AQ_INVALID:
            setattr(self, '_a'+aname, x)
            attr.set_value_date_quality(x, timestamp, quality)
        else:
            setattr(self, '_a'+aname, None)
            attr.set_quality(AQ_INVALID)

    def distill_I_quality(self, quality, aval1, aval2):
        diff = abs(aval1.value - aval2.value) / self.Inominal
        if self._aWaveGeneration:
            quality =  AQ_CHANGING
        elif quality == AQ_VALID:
            if diff > self.RegulationPrecision:
                quality = AQ_WARNING
            if diff > 2*self.RegulationPrecision:
                quality = AQ_ALARM
        return quality


    def is_Voltage_allowed(self, write):
        return not self._aWaveGeneration

    @PS.ExceptionHandler
    def read_Current(self, attr):
        self.read_attribute(attr, self.distill_I_quality)

    @PS.ExceptionHandler
    def read_Current1(self, attr):
        self._read_CurrentX(self.bend1, attr)

    def _read_CurrentX(self, bend_x, attr):
        aval = bend_x.read_attribute('Current')
        I = aval.value
        timestamp = tv2time(aval.time)
        quality = aval.quality
        attr.set_value_date_quality(I, timestamp, quality)

    @PS.ExceptionHandler
    def read_Current2(self, attr):
        self._read_CurrentX(self.bend2, attr)

    def On(self):
        if self.get_state() in (DevState.ALARM, DevState.FAULT):
            return
        self.set_state(DevState.INIT)
        self.set_status('switching on...')
        self.switching = SWITCH_ON
        self.switch_eta = time() + self.estimate_switch_on_time()
        self.upswitch_on(self.bend1)
        self.upswitch_on(self.bend2)

    def Off(self):
        if self.get_state() in (DevState.ALARM, DevState.FAULT):
            return
        self.set_state(DevState.INIT)
        self.set_status('switching off...')
        self.switching = SWITCH_OFF
        self.switch_eta = time() + self.estimate_switch_off_time()
        self.upswitch_off(self.bend1)
        self.upswitch_off(self.bend2)

    def est1_on_t(self, b, c):
        if c in CAB_ON_T:
            t = CAB_ON_T[c]
            if b in BEND_ON_T:
                return t+BEND_ON_T[b]
            else:
                msg = 'cabinet ready, but can not switch on PC %x' % b
                raise PS.PS_Exception(msg)
        else:
            msg = 'currently impossible to switch on bending cabinet %x' % c
            raise PS.PS_Exception(msg)

    def est1_off_t(self, b, c):
        return CAB_OFF_T.get(c,0.0)+BEND_OFF_T.get(b,0.0)

    def estimate_switch_on_time(self, mc1=None, mc2=None):
        if mc1 is None: mc1 = self.mac_state(self.bend1)
        if mc2 is None: mc2 = self.mac_state(self.bend2)
        on1_t = self.est1_on_t(*mc1)
        on2_t = self.est1_on_t(*mc2)
        return max(on1_t, on2_t)

    def estimate_switch_off_time(self, mc1=None, mc2=None):
        if mc1 is None: mc1 = self.mac_state(self.bend1)
        if mc2 is None: mc2 = self.mac_state(self.bend2)
        off1_t = self.est1_off_t(*mc1)
        off2_t = self.est1_off_t(*mc2)
        return max(off1_t, off2_t)

    @PS.ExceptionHandler
    def UpdateState(self):
        try:
            if self.switching == SWITCH_ON:
                fin = self.upswitch_on(self.bend1) and self.upswitch_on(self.bend2)
                self.update_switch_status('on', fin)
            elif self.switching == SWITCH_OFF:
                fin = self.upswitch_off(self.bend1) and self.upswitch_off(self.bend2)
                self.update_switch_status('off', fin)

        except Exception:
            self.switching = SWITCH_NEUTRAL
            raise

        finally:
            if not self.switching in (SWITCH_ON, SWITCH_OFF):
                self.update_neutral()


    def update_switch_status(self, switch, fin):
        if fin:
            self.switching = SWITCH_NEUTRAL
            self.update_neutral()
        else:
            rem_t = self.switch_eta - time()
            rem_str = int(rem_t / 60) + ':' + int(rem_t % 60)
            self.set_state(DevState.INIT)
            self.set_status('switching %s, %s remaining' % (switch, rem_str))


    def update_neutral(self):
        # defines two shortcuts to improve readability later
        bend1, bend2 = self.bend1, self.bend2

        # first new state is determined
        b1_state, b2_state = bend1.State(), bend2.State()

        # if States are equal it is used as-is
        state = b1_state
        if b1_state == DevState.FAULT or b2_state == DevState.FAULT:
            state = DevState.FAULT

        elif b1_state == DevState.ALARM or b2_state == DevState.ALARM:
            state = DevState.ALARM

        bss1 = bend1.read_attribute('ShortStatus').value
        bss2 = bend2.read_attribute('ShortStatus').value

        # if ShortStatus are equal the same
        if bss1==bss2:
            short_status = bss1

        # otherwise its alternated between them, prefixed with bend1 resp
        # bend2 to indicated where ShortStatus comes from
        else:
            short_status = bss1 + " / " + bss2

        b1_status = bend1.Status()
        b2_status = bend2.Status()

        # if Status is the same, use as-is
        if b1_status==b2_status:
            status = b1_status

        elif bss1!=bss2:
            status = short_status

        else:
            status = b1_status + ' / ' + bs_status
        self.STAT.set_stat2(state, short_status, status)

    def upswitch_on(self, bend):
        '''Switches one bending power supply on.
           Returns True once PS are on otherwise None or False.
        '''
        c,b = self.mac_state(bend)

        if c == CAB_OFF_STATE:
            c.On()

        elif c == CAB_ON_STATE:
            b.On()

        elif c == CAB_ON_STATE and b == BEND_ON_STATE:
            return True

        elif c in CAB_FAULT_STATE or b in BEND_FAULT_STATE:
            self.switching = SWITCH_NEUTRAL
            return True

    def upswitch_off(self, bend):
        '''Switches one bending power supply off.
           Returns True once PS are on otherwise None or False.

        '''
        c,b = self.mac_state(bend)

        if b == BEND_OFF_STATE:
            return True

        elif b == BEND_ON_STATE:
            b.Off()

        elif c in CAB_FAULT_STATE or b in BEND_FAULT_STATE:
            self.switching = SWITCH_NEUTRAL
            return True


    def mac_state(self, bend):
        baval = bend.read_attribute('MachineState')
        cabaval = bend.cab.read_attribute('MachineState')
        assert baval.quality == AQ_VALID
# TODO: possibly the value could be non if qualiy INVALID
#        assert cabaval.quality == AQ_VALID
        c,b = cabaval, baval.value
        return c,b

    def read_WaveLength(self, attr):
        self.read_attribute(attr)

    def read_Waveform(self, attr):
        self.read_attribute(attr, self.distill_waveform_quality)

    def write_Waveform(self, attr):
        self.write_spectrum(attr)

    def read_TriggerMask(self, attr):
        self.read_attribute(attr)

    def upswitch_cab_off(self, bend):
        '''Switches one bending power supply off.
        '''
        c,b = self.mac_state(bend)

        if c == CAB_OFF and b == BEND_OFF:
            return True

        elif b == BEND_ON:
            b.Off()

        elif b == BEND_OFF:
            c.Off()

        elif c in CAB_FAULT_STATE:
            self.switching = SWITCH_NEUTRAL
            return True

    @PS.AttrExc
    def read_Voltage(self, attr):
        self.read_attribute(attr)

    @PS.AttrExc
    def write_Current(self, attr):
            # updates Current setpoint
            Iset = attr.get_write_value()
            self.bend1.write_attribute('Current', Iset)
            self.bend2.write_attribute('Current', Iset)

    def write_scalar(self, attr):
        aname = attr.get_name()
        data = []
        attr.get_write_value(data)
        self.bend1.write_attribute(aname, data[0])
        self.bend2.write_attribute(aname, data[1])

    def write_spectrum(self, attr):
        aname = attr.get_name()
        data = []
        attr.get_write_value(data)
        self.bend1.write_attribute(aname, data)
        self.bend2.write_attribute(aname, data)

    @PS.AttrExc
    def write_Current(self, attr):
        self.write_scalar(attr)

    @PS.CommandExc
    def Sync(self):

        # checks state of power supplies
        for d in self.sync_devices:
            aval = d.read_attribute('MachineState')
            if aval.quality != AQ_VALID:
                raise PS.PS_Exception('MachineState attribute is not valid')
            if aval.value != STATE_SYNC:
                raise PS.PS_Exception('device %r not ready to be sync\'d' % self.get_name())

        # checks and switches off triggers
        evr_state = self.trig.State()
        if not evr_state in (DevState.ON, DevState.OFF):
            raise PS.PS_Exception('event receiver is in %s state, must be ON or OFF')

        try:
            self.trig.Off()

            # sends SYNC commands
            for d in self.sync_devices:
                d.Command( ['SYNC'] )


        finally:
            # re-enables trigger if they were enabled before
            if evr_state == DevState.ON:
                self.trig.On()

    @PS.CommandExc
    def ResetInterlocks(self):
        PS.PowerSupply.ResetInterlocks(self)
        self.all('ResetInterlocks')

    @PS.AttrExc
    def read_Errors(self, attr):
        ls = []
        BE1 = self.bend1.read_attribute('Errors').value
        BE2 = self.bend2.read_attribute('Errors').value
        if BE1 is None:
            BE1 = []

        if BE2 is None:
            BE2 = []

        for e1 in BE1:
            if e1 not in BE2:
                ls.append('bend1: '+e1)
            else:
                ls.append(e1)

        for e2 in BE2:
            if e2 not in BE1:
                ls.append('bend2: '+e2)

        self.errors = ls
        attr.set_value(self.errors)


    @PS.AttrExc
    def read_RemoteMode(self, attr):
        self.read_attribute(attr)

    @PS.CommandExc
    def ResetInterlocks(self):
        PS.PowerSupply.ResetInterlocks(self)
        fail = 0
        exc = None
        try:
            self.bend1.ResetInterlocks()
        except Exception,exc1:
            self._exception('resetting bending 1 failed')
            exc = exc1

        try:
            self.bend2.ResetInterlocks()
        except Exception,exc1:
            self._exception('resetting bending 2 failed')
            exc = exc2

        if exc: raise exc

    @PS.AttrExc
    def read_WaveStatus(self, attr):
        self.read_attribute(attr)

    @PS.AttrExc
    def read_WaveDuration(self, attr):
        self.read_attribute(attr)

    @PS.AttrExc
    def read_RegulationFrequency(self,attr):
        self.read_attribute(attr)

    @PS.AttrExc
    def read_WaveInterpolation(self, attr):
        self.read_attribute(attr)

    @PS.AttrExc
    def read_WaveGeneration(self, attr):
        self.read_attribute(attr)

    @PS.AttrExc
    def read_WaveOffset(self, attr):
        self.read_attribute(attr)

    @PS.AttrExc
    def read_WaveName(self, attr):
        self.read_attribute(attr)

    @PS.AttrExc
    def read_WaveId(self, attr):
        self.read_attribute(attr)

class BrukerBend_PS_Class(Tg.DeviceClass):

        FMT = '%6.4f'


        #       Class Properties
        class_property_list = {
                }


        #       Device Properties
        device_property_list = PS.gen_property_list()
        device_property_list.update({
            'Trigger' :
                [ Tg.DevString,
                    "Event receiver sending trigger for bending and quadrupoles", 'bo04/ti/evr-cpc1502-a'],

            'Bend1':
                [Tg.DevString,
                "Name of device controlling bending 1.",
            'bo/pc/bend-1' ],
            'Bend2':
                [Tg.DevString,
                "Name of device controlling bending 2.",
                'bo/pc/bend-2' ],
                'QuadCabinet':
            [Tg.DevString,
            "Name of the quadrupole cabinet, used for Sync command.",
            'bo/ct/pc-q' ],
                })


        #       Command definitions
        cmd_list = PS.gen_cmd_list(opt=('UpdateState',))
        cmd_list['UpdateState'][2]['polling period'] = 20000
        cmd_list.update({
          'On' : [ [Tg.DevVoid],[Tg.DevVoid]],
          'Off' : [ [Tg.DevVoid],[Tg.DevVoid]],
          'Sync' : [ [Tg.DevVoid, 'sync sync'],[Tg.DevVoid],
              { 'display level' : Tg.DispLevel.EXPERT }
          ],
       })



        #       Attribute definitions
        attr_list = PS.gen_attr_list(max_err=100,opt=('Current','CurrentSetpoint','Voltage'))
        attr_list.update({
                'Current1': attr_list['Current'],
                'Current2': attr_list['Current'],
                'Voltage': attr_list['Voltage'],
                'WaveGeneration' : [[ Tg.DevBoolean, Tg.SCALAR, Tg.READ_WRITE ]],
                'Waveform' : [[ Tg.DevDouble, Tg.SPECTRUM, Tg.READ_WRITE, 2**14] , {} ],
                'WaveLength' : [[ Tg.DevShort, Tg.SCALAR, Tg.READ], {'unit' : 'points'} ],
                'WaveStatus' : [[ Tg.DevString, Tg.SCALAR, Tg.READ ]],
                'WaveName' : [[ Tg.DevString, Tg.SCALAR, Tg.READ ]],
                'WaveId' : [[ Tg.DevLong, Tg.SCALAR, Tg.READ ]],
                'WaveDuration' : [[ Tg.DevDouble, Tg.SCALAR, Tg.READ ], {'unit': 'ms'} ],
                'WaveOffset' : [[ Tg.DevDouble, Tg.SCALAR, Tg.READ_WRITE ], {'unit': 'A'} ],
                'WaveInterpolation' : [[ Tg.DevShort, Tg.SCALAR, Tg.READ_WRITE ], { 'unit': 'log2(periods/point)' } ],
                'RegulationFrequency' : [[ Tg.DevDouble, Tg.SCALAR, Tg.READ ], { 'unit' : 'kHz'} ],
                'TriggerMask': [[Tg.DevLong, Tg.SCALAR,  Tg.READ_WRITE],
                    { 'min value' : 0, 'max value' : 0x3fffffff,
    'description' : '''number of triggers to consider:
0:no wave generated, 1:generate single wave, 0x3fffffff:continously''' }
                    ]}
        )
        attr_list['CurrentSetpoint'][1]['format'] = FMT
        attr_list['Voltage'][1]['format'] = FMT
        attr_list['Current'][1]['format'] = FMT

        #  BrukerBend_PSClass Constructor
        def __init__(self, name):
                Tg.DeviceClass.__init__(self, name)
                self.set_type(name);


if __name__ == '__main__':
    classes = (BrukerBend_PS, )
    PS.tango_main( 'BrukerBend_PS', sys.argv, classes)
