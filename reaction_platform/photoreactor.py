import serial
import pandas as pd


class Borealis:
    """
    Class to provide communication with the Uniqsis Borealis photoreactor

    attributes
    ----------
        _connected: bool.
        _verbose
        power
        ser

    methods
    ----------
        enable: turn on Borealis
        resume: resume Borealis with previously set power
        disable: turn off Borealis
        set_power: set the power level
        get_power: get the current power level
        get_lamp_current: get the current flowing through the LED unit
        get_lamp_temperature: current temperature of teh lamp
        get_reactor_temperature: current temperature of the thermocouple in the reactor
        get_status: request device status.
        send: format and send commands
    """

    def __init__(self, comport, baudrate=115200, verbose=False):
        """
        Initialization of the borealis object.

        parameters
        ----------
            comport: the COM-port the unit is connected to
            baudrate: the communication speed
        """
        self.power = 0
        self._connected = False
        self._verbose = verbose

        # connect to device
        self.ser = serial.Serial(port=comport, baudrate=baudrate)

        # test
        self.send('V')
        check = self.ser.read_until(b'\r\n').decode('ascii')
        self.ser.reset_output_buffer()

        if check[:2] == '*V':
            self._connected = True
            if self._verbose:
                print('connection to Borealis on {} successfull'.format(comport))

    def enable(self, power=None):
        """
        Turn on the borealis at a certain intensity

        parameters
        ----------
            power: the intensity of the lamp, in % (0-100). the default is 10 (the minimum)
        """
        if power is None:
            power = self.power
        if power == 1:
            self.resume()
        else:
            self.set_power(power=power)

    def resume(self):
        """resume operation at the previously selected power level"""
        self.send('P 1')
        reply = self.ser.read_until(b'\r\n').decode('ascii')
        self.ser.reset_output_buffer()
        if self._verbose:
            print(reply)

    def disable(self):
        """
        Turn of the borealis
        """
        self.send('P 0')
        reply = self.ser.read_until(b'\r\n').decode('ascii')
        self.ser.reset_output_buffer()

        if self._verbose:
            print(reply)

    def set_power(self, power):
        """
        set the intensity

        parameters
        ----------
            power: the intensity of the unit
        """
        power = int(power)
        if (power < 10) | (power > 100):
            raise ValueError('power needs to be a number between 10 and 100')

        self.power = power
        self.send('P {}'.format(power))
        reply = self.ser.read_until(b'\r\n').decode('ascii')
        self.ser.reset_output_buffer()

        if self._verbose:
            print(reply)

    def get_power(self, update=False):
        """get the light intensity of the unit"""

        out = self.get_status()
        power = out.iloc[0]['Power']

        if update:
            self.power = power

        return power

    def get_lamp_current(self):
        """get the reactor temperature from the borealis"""
        status = self.get_status()

        return status.iloc[0]['Current']

    def get_lamp_temperature(self):
        """get the lamp temperature from the borealis"""
        status = self.get_status()

        return status.iloc[0]['T lamp']

    def get_reactor_temperature(self):
        """get the reactor temperature from the borealis"""
        status = self.get_status()

        return status.iloc[0]['T reactor']

    def get_status(self):
        """get the status of the Borealis. Store the values in a dataframe"""
        self.send('?')

        lamp_status = self.ser.read_until(b'\r\n').decode('ascii').split(' ')
        temperatures = self.ser.read_until(b'\r\n').decode('ascii').split(' ')
        errors = self.ser.read_until(b'\r\n').decode('ascii').split(' ')
        self.ser.reset_output_buffer()

        # TODO: check response, raise exception if not like expected
        lamp_current = float(lamp_status[1][3:])
        lamp_temperature = float(lamp_status[3][3:])
        lamp_power = int(lamp_status[5][4:-1])
        lamp_enabled = bool(int(lamp_status[6][6]))

        temperature_reactor = float(temperatures[5][4:-2])

        lock_ok = int(errors[1][7])
        error_ttrip = int(errors[2][6])
        error_itrip = int(errors[3][6])
        error_fatal = errors[3][:-2]

        out = pd.DataFrame({'Current': lamp_current, 'T lamp': lamp_temperature, 'Power': lamp_power,
                                      'Lamp enabled': lamp_enabled, 'T reactor': temperature_reactor, 'lock OK':
                                      lock_ok, 'Error T': error_ttrip, 'Error I': error_itrip, 'Fatal errors':
                                      error_fatal}, index=[0])

        return out

    def send(self, command):
        """send a command to the unit"""
        message = '*' + command + '\r\n'
        self.ser.write(message.encode('ascii'))

    def close_connection(self):
        """close connection with the unit"""
        self.disable()
        self.ser.close()

    # TODO: check what happens with unknown commands
    # TODO: improve error and exception handling

