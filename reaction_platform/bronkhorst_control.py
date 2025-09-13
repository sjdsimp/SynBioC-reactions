# -*- coding: utf-8 -*-
"""
Created on Wed Feb  9 14:22:56 2022

This module wraps around the Bronkhorst propar module to provide custom, 
more streamlined functionality tailored for the reaction platform for 
aerobic oxidations developed at Janssen Pharmaceutica

All functionality of the Bronkhorst propar.instrument class is still available.

@author: SDesimp1
"""
import propar
import numpy as np

class bronkhorst(propar.instrument):
    """
    Facilitates communication with Bronkhorst equipment by creating an object
    that can be used to communicate with the physical device. Inherits from propar.instrument
    
    Methods
    ----------
        set_setpoint

        start

        stop

        close

    Attributes
    ----------
    
    """
    
    def __init__(self, comport, device: str = "MFC", slope: int = 0, **kwargs):
        """
        
        """
        
        if type(comport) is int:
            comport = "COM" + str(comport)
        
        propar.instrument.__init__(self, comport, **kwargs)
        
        try:
            self.wink(1)
        except: 
            print("failed to connect to instrument")
        else:
            print("Connection to instrument successful on {}".format(comport))
            
        if self.readParameter(12)!=0:
            self.writeParameter(12, 0)
            print("Control mode of instrument set to BUS/RS232")
        else:
            print("Control mode of instrument already set to BUS/RS232")
        
        self._device  = device
        self.max_capacity = self.readParameter(21)
        self.min_capacity = self.readParameter(183)
        self.unit = self.readParameter(129)
        self.setpoint_flag = 0
        self.setpoint_unit = self.unit
        self.slope = 0
        if slope > 0:
            self.writeParameter(10, slope)
            self.slope = slope
    
    def set_setpoint(self,setpoint, unit=None, instrument_running=False):
        """
        Write setpoint to device

        Parameters
        ----------
        setpoint : float
            setpoint to send, in correct unit
        unit : str, optional
            The unit of the setpoint. The default is '%'.
            for MFC this is 'mls/min' or 'mln/min'
            for PC this is 'bar(g) '
            can be checked by calling self.unit
        instrument_running: bool, optional
            should the setpoint be sent to the instrument (that will start running or change SP if already running?
            The default is False (nothing sent to instrument)

        Returns
        -------
        None.

        """
        if unit is None:
            unit = self.unit

        self.setpoint_flag = setpoint  # the flag is always in the same units as self.setpoint_unit
        self.setpoint_unit = unit

        sp = self.convert_to_instrument(data=setpoint, unit=unit)

        # only send to instrument if it is running or can be started
        if instrument_running:
            self.writeParameter(9, sp)
            
    # TODO: function to query parameter without waiting for response, just send the command, optional parameter to
    #  adjust timeout
    
    # TODO: function to read the buffer of the serial instance . functions laid out above allow first querying all
    #  equipment and then reading all responses, to minimize time difference between measurement and logging

    def start(self, setpoint=None, unit=None):
        """ Start the instrument with the provided setpoint. if no setpoint is provided, use the internal setpoint flag.
        Parameters
        ----------
            slope: int, optional
                Digital instruments can establish a smooth setpoint control using the setpoint slope time. The setpoint
                will be linear increased in time from old setpoint to new setpoint value. A value between 0 and 3000
                seconds, with a resolution of 0.1 seconds, can be given to set the time for the integrator on the
                setpoint signal. The default is 0, meaning the setpoint is instantly changed
        """
        if unit is None:
            unit = self.unit

        if setpoint is None:
            setpoint = self.setpoint_flag

        self.set_setpoint(setpoint, unit=unit, instrument_running=True)

    def get_setpoint(self, unit=None):
        """gets the setpoint, in the unit of choice (% or self.unit)
        Parameters
        ----------
            unit: str
                The unit in which to return the setpoint. the options are '%' and self.unit.
        """
        data = self.setpoint
        return self.convert_from_instrument(data, unit=unit)

    def get_measure(self, unit=None):
        data = self.measure
        return self.convert_from_instrument(data, unit=unit)

    def stop(self):
        """Stop instrument (set setpoint to 0)

        Parameters
        ----------
            slope: int, optional
                Digital instruments can establish a smooth setpoint control using the setpoint slope time. The setpoint
                will be linear increased in time from old setpoint to new setpoint value. A value between 0 and 3000
                seconds, with a resolution of 0.1 seconds, can be given to set the time for the integrator on the
                setpoint signal. The default is 0, meaning the setpoint is instantly changed
        """
        self.writeParameter(9, 0)

    def close(self):
        """Set setpoint to 0 and close port to instrument"""
        self.writeParameter(9, 0)
        self.master.stop()

    def convert_from_instrument(self, data, unit=None):
        """convert the setpoint/measure data coming from the instrument as an integer value between 0-32000 to
        the units of choice (e.g. mls/min, mln/min or bar(g).

        Parameters
        ----------
            data: int
                The data coming from the instrument, it has a value between 0 and 32000
            unit: str
                The unit to convert the data to

        """
        if (unit is None) or (unit != '%' or unit != self.unit):
            unit = self.unit

        converted = 0

        if unit == self.unit:
            converted = (data / 32000) * (self.max_capacity - self.min_capacity) + self.min_capacity
        if unit == '%':
            converted = (data / 320)

        return converted

    def convert_to_instrument(self, data, unit=None):
        """"""
        if (unit is None) or (unit != '%' or unit != self.unit):
            unit = self.unit

        converted = 0

        if unit == self.unit:
            converted = int((data - self.min_capacity) / (self.max_capacity - self.min_capacity) * 32000)
        if unit == '%':
            converted = int(data*32000/100)

        return converted

