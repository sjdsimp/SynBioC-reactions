# -*- coding: utf-8 -*-
"""
Created on Wed Jan 15 15:16:09 2020

Module for sending and recieving serial commands/messages to the ISCO pumps.
When instantiating the class, enter the COM port where the USB-to-RS232 connction is made. Default baudrate and UID
for the pump is 9600 and 6. This can be changed in on the instrument panel (refer to manual). A serial connection
is opened. You can get actual pump parameters as arrays with [system flow rate (mL/min), system pressure (bar),
system volume (mL)] by invoking systfpv(). Other standard commands to control the pump require you to first lock
the panel for remote control, by calling control(). Control can be returned to the instrument panel, call local().
When finished, call close() which will return control to the panel and close the serial connection.
You can also send custom commands to the pump by passing the command as an argument through send().

@author: begle, sdesimp
"""

import serial
from serial.serialutil import SerialException, SerialTimeoutException
import time
import sys
import warnings


# TODO: add functionality to distinguish between single and dual pump mode
# TODO: inquire whether all dual pumps can be run in continuous mode
# TODO: provide standardized methods to run pumps, independent of pump mode
# TODO: set default timeout

class DASnet:
    _version = '0.2.1'  # changes made to make driver more suitable for integration into paltform

    def __init__(self, comport, baudr=9600, U='6', timeout=5, pump='A'):
        self.flow_rate = None
        self.max_rate = None
        self.max_refill_rate = None
        self.cylinder_volume = None
        self._type = 'isco'
        self.name = None
        self.pump = pump
        self.multi = False  # flag to check if the system is in multipump mode
        self.UID = str(U)
        self.presslimit = 0  # current pressure limit for the system, '0' means no limit is set

        self.das = serial.Serial()  # initiate serial port to pump, no parity, 8 bits per byte, 1 stop and start bit
        self.das.baudrate = baudr  # Baud rate, check/set via the on-unit control panel (default = 9600)
        self.das.timeout = timeout
        self.das.port = str(comport)  # USB-to-RS232 Port to connect to
        try:
            self.das.open()  # open serial connection
        except SerialException:
            sys.exit("Error opening serial port")
        print('Connected to port %s' % comport)

        # empty input and output buffer first:
        self.das.reset_input_buffer()
        self.das.reset_output_buffer()

        try:
            self.das.write(self.dasconv('identify', self.UID))  # Ask device to identify itself
        except SerialTimeoutException:
            print('Error writing to port. Closing connection.')
            self.das.close()
            sys.exit(1)
        time.sleep(0.2)
        try:
            ident = self.das.read_until(b'\r')  # receive response (read until CR)
        except:
            print('No response from pump.')
            sys.exit(1)
        # generate more human readable output of pump details
        print(ident.decode('utf-8').replace(', ', '\n').replace('; ', '\n'))

        # assume control of pump
        self.control()
        time.sleep(0.1)
        # set internal flags to right value
        #self.send('CONST FLOW')
        time.sleep(0.1)
        #self.get_pump_data()

    def setPlimit(self, limit):  # Set a maximum pressure limit
        try:
            self.presslimit = float(limit)
        except:
            print("Please enter a limit")
            return "Error setting limit"
        print("Current pressure limit = %i" % self.presslimit)

    def systfpv(self):
        out = self.send('g&').split('=')[1].strip().split(',')
        # if system is in multipump mode: return system flow rate (mL/min), system pressure (bar), system volume (mL)
        if self.multi == True:
            return (float(out[-4]) / 10000000), (float(out[-3]) / 5 * 0.0689476), (float(out[-2]) / 1000)
        # if pumps are used separately: return flow rate (mL/min), pressure (bar), volume (mL) for each pump as a list 
        if self.multi == False:
            A = [(float(out[9]) / 10000000), (float(out[0]) / 5 * 0.0689476), (float(out[10]) / 1000000)]
            B = [(float(out[14]) / 10000000), (float(out[1]) / 5 * 0.0689476), (float(out[15]) / 1000000)]
            return A, B

    @staticmethod
    def dasconv(command, destination, source='0', acknowl='R'):  # default source = 0 for computer control
        # converts a command into a DASNET protocol compliant frame. Destination and source should be one-digit.
        # followed by a carriage return
        UMessage = command.upper()  # put command in all caps
        if len(UMessage) > 256:
            return print("Command too long! (max size = 256 characters)")
        if len(destination) > 1:
            return print("Destination should be a one-digit number!")
        length = "{:=02X}".format(len(UMessage))  # calculate length of message and convert to 2 digit hexadecimal value
        checksum = "{:=02X}".format(256 - (sum((ord(x) for x in (
                    UMessage + length + source + destination + acknowl))) % 256))  # generate the checksum
        return (str(destination) + acknowl + str(source) + str(length) + UMessage + checksum + '\r').encode('utf-8')

    def control(self):
        # lock the instrument panel and assume control
        print('Assuming remote control.')
        try:
            self.das.write(self.dasconv('remote', self.UID))
        except:
            print('Error taking control')
        print('Remote control enabled, front panel locked.')

    def close(self):
        # return control to panel and close the serial connection.
        print('Returning control to panel and closing serial connection')
        self.das.write(self.dasconv('local', self.UID))
        time.sleep(0.2)
        self.das.close()
        print('Connection closed')

    def setUID(self, id):  # Change UID setting. Careful: commands will not work if wrong UID is set!
        print('Changing UID from %s to %s.' % self.UID, str(id))
        self.UID = str(id)

    def local(self):
        # return control to panel.
        print('Returning control to panel.')
        self.das.write(self.dasconv('local', self.UID))
        time.sleep(0.2)
        print('Control returned to panel.')

    def setflowrate(self, rate, pump='A'):
        # set flow rate for desired pump (A or B) in mL/min
        if (pump != 'A' and pump != 'B'):
            print("Choose pump A or B")
            return "no pump selected"
        elif pump == 'A':
            resp = self.send('flowA=' + str(rate))
            return resp
        elif pump == 'B':
            resp = self.send('flowb=' + str(rate))
            return resp

    def dispense(self, vol, flowrate, pump):
        """Dispense a certain volume (in mL) for desired pump"""
        # Dispense only implemented for newer D4 controllers
        # if (pump != 'A' and pump != 'B'):
        #     print("Choose pump A or B")
        #     return "no pump selected"
        # elif pump == 'A':
        #     resp = self.send('dispenseA=' + str(vol))
        #     return resp
        # elif pump == 'B':
        #     resp = self.send('dispenseB='+str(vol))
        #     return resp
        warnings.warn('Not implemented for legacy controller. Pump will run at preset flowrate')
        self.start(flowrate=flowrate)

    def constflow(self):
        """put pumps in continuous flow mode, constant flow rate"""
        self.multi = True
        return self.send('CONTIN CONST FLOW')

    def indep(self):
        # put pumps in independent mode
        return self.send('independent')

    def startA(self):
        # Start pump A
        self.send('run')

    def startB(self):
        # start pump B
        self.send('runb')

    def startAll(self):
        # start all pumps
        self.send('runall')

    def send(self, command):
        # custom command sending/receiving
        self.das.reset_input_buffer()
        self.das.reset_output_buffer()
        self.das.write(self.dasconv(command, self.UID))
        time.sleep(0.05)
        response = self.das.read_until(b'\r')
        self.das.reset_input_buffer()
        self.das.reset_output_buffer()
        if response.decode('utf-8') == 'R 8E\r':  # 'R 8E\r' means command is received in the DASnet protocol.
            print('Command received.')
            return 'ok'
        else:
            return response.decode('utf-8')

    def start(self, flowrate=None, volume=None, echo_runtime=False):
        """start pump with specified flow rate"""
        if flowrate is None:
            flowrate = self.flow_rate

        self.set_setpoint(setpoint=flowrate, pump=self.pump)

        if volume is None:
            if echo_runtime:
                level = self.get_fill_level()
                if flowrate > 0:
                    runtime = level / flowrate
                elif flowrate < 0:
                    max_level = self.cylinder_volume
                    runtime = abs((max_level - level) / flowrate)
                print("{} will be able to run for {:.2f} minutes".format(self.name, runtime))

            if self.pump == 'A':
                command = 'run'
            else:
                command = 'run' + self.pump

            self.send(command=command)
        else:
            if flowrate > 0:
                self.dispense(vol=volume, pump=self.pump)
            elif flowrate < 0:
                # TODO: check what command to send to aspirate certain volume
                pass

    def fill(self, rate=None, pump=None):
        """fill the cylinder at a defined rate"""
        if pump is None:
            pump = self.pump
        if pump == 'A':
            command = 'refill'
        else:
            command = 'refill' + self.pump

        if rate is not None:
            command_rate = command + '=' + str(float(rate).__round__(3))
            self.send(command_rate)

        self.send(command)

    def stop(self, pump=None):
        """stop the cylinder"""
        if pump is None:
            pump = self.pump

        if pump == 'A':
            command = 'stop'
        else:
            command = 'stop' + self.pump

            self.send(command=command)
        self.send(command)

    def set_setpoint(self, setpoint, pump=None):
        """adjust pump setpoint"""
        if pump is None:
            pump = self.pump
        # for pump A, the command is different
        if pump == 'A':
            pump = ''

        sp = float(setpoint).__round__(5)  # 5 significant digits
        self.flow_rate = sp
        command = 'FLOW' + pump + '=' + str(sp)
        self.send(command)

    def get_flow_is(self, pump=None) -> float:
        """get current flow rate"""
        if pump is None:
            pump = self.pump

        command = 'FLOW' + pump
        response = self.send(command)
        flowrate = float(response.split('=')[1].strip()[:-2])
        return flowrate

    def get_fill_level(self, pump=None) -> float:
        """get the current level of the cylinder"""
        if pump is None:
            pump = self.pump

        command = 'VOL' + pump
        response = self.send(command)
        level = float(response.split('=')[1].strip()[:-2])
        return level

    def get_pump_data(self, pump=None):
        """determine max pressure, max flow rate, max refill rate and total cylinder volume"""
        if pump is None:
            pump = self.pump

        command = 'RANGE' + pump
        response = self.send(command).split(',')
        pressure_psi = float(response[0].split('=')[1].strip())
        self.presslimit = pressure_psi * 0.0689475728
        self.max_rate = float(response[1].split('=')[1].strip())
        self.max_refill_rate = float(response[2].split('=')[1].strip())
        self.cylinder_volume = float(response[3].split('=')[1].strip())
