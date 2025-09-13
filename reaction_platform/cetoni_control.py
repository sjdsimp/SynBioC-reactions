# -*- coding: utf-8 -*-
"""
This module simplifies communication with and control of Cetoni pumps,
to facilitate integration
Created on Tue Feb 22 15:21:39 2022

Classes
----------
    Cetoni

Functions
----------
    initialize(config_dir) --> bus
    close communication(bus)

@author: SDesimp1
"""

import sys
import os

# to be able to load the Cetoni SDK, the directory needs to be added to the path first
QMIXSDK_DIR = "C:\\Reaction platform\\Cetoni\\CETONI_SDK"
sys.path.append(QMIXSDK_DIR + "\\lib\\python")
sys.path.append(QMIXSDK_DIR + "\\lib\\python\\qmixsd")
os.environ['PATH'] += os.pathsep + QMIXSDK_DIR

# now that the directories have been added to the path, the modules can be imported
from qmixsdk import qmixbus
from qmixsdk import qmixpump
from qmixsdk.qmixbus import UnitPrefix, TimeUnit
from qmixsdk.qmixpump import VolumeUnit

import qmixsdk


def initialize(config_dir):
    """
    Initialize communication with the device by opening and starting a bus.
    Bus is returned so that it can be used to stop communication

    Parameters
    -----------
        config_dir: str
            The directory where the device configuration files can be found

    Returns
    ----------
        bus: Bus object of qmixsdk.qmixbus
            Bus to enable communication with device specified in
            configuration files
    """
    bus = qmixbus.Bus()
    bus.open(config_dir, "")
    bus.start()
    return bus


def close_communication(bus):
    """
    Stop and close bus, to end communication with the device

    Parameters
    ----------
        bus: Bus object of qmixsdk.qmixbus
            Bus used for communication with device
    """
    bus.stop()
    bus.close()

def fill_pumps(pumps, flowrate=-135):
    for pump in pumps:
        pump.fill(flowrate)


class cetoni(qmixpump.Pump):

    def __init__(self, index, calibration=False, diameter=25.0171, stroke=60, verbose=1):
        """
        Initialize cetoni object through initialization of pump device and setting relevant parameters

        Parameters
        ----------
            index: int
                the index of the pump, as specified in the configuration file

            calibration: bool, optional
                Should the device be calibrated upon connecting?
                Note that performing calibration with syringes installed
                might lead to an error, requiring the syringes to be
                reinstalled. (default is False)

            diameter: int, optional
                the diameter of the installed syringe, in mm. (default is 22)

            stroke: int, optional
                the stroke of the installed syringe, in mm. (default is 60)

            verbose: int. optional
                The level of verbosity when connecting to the pump.
                    0: No feedback from pump
                    1: Print device name upon connection
                    2: Print device name, volume unit, flow unit, parameters
                (the default is 1)

        """
        self.flow_rate = 0
        self.max_rate = None
        self._type = 'cetoni'
        # initialize pump object
        qmixpump.Pump.__init__(self)
        # Retrieve device handle
        self.lookup_by_device_index(index)
        self.device_name = self.get_device_name()
        if verbose >= 1:
            print("connected to: {}".format(self.device_name))

        # bring devices into an enabled and initialized state, by clearing all faults and enabling all pump drives
        self.clear_fault()
        self.enable(True)

        # calibrate pump when necessary
        if calibration:
            self.calibrate()
            timeout_timer = qmixbus.PollingTimer(10000)
            result = timeout_timer.wait_until(self.is_calibration_finished, True)
            print(result)

        # setup of pump

        self.set_volume_unit(UnitPrefix.milli, VolumeUnit.litres)
        self.set_flow_unit(UnitPrefix.milli, VolumeUnit.litres, TimeUnit.per_minute)
        self.volume_unit = self.get_volume_unit()
        self.flow_unit = self.get_flow_unit()
        if verbose > 1:
            print("volume unit: {}".format(self.volume_unit))
            print("flow unit: {}".format(self.flow_unit))

        self.set_syringe_param(diameter, stroke)

        if verbose > 1:
            print("syringe parameters: {}".format(self.get_syringe_param()))

        self.max_flow_rate = self.get_flow_rate_max()
        self.max_volume = self.get_volume_max()

        if verbose > 1:
            print("max syringe volume: {}".format(self.max_volume))
            print("max flow rate: {}".format(self.max_flow_rate))

    def start(self,volume=None, flowrate=None, echo_runtime=False):

        if flowrate is None:
            flowrate = self.flow_rate

        if volume is None:
            level = self.get_fill_level()
            if echo_runtime:
                if flowrate > 0:
                    runtime = level/flowrate
                elif flowrate < 0:
                    max_level = self.get_volume_max()
                    runtime = abs((max_level - level)/flowrate)
                print("pump {} will be able to run for {:.2f} minutes".format(self.device_name, runtime))
            self.generate_flow(flowrate)

        else:
            if flowrate > 0:
                self.dispense(volume,flowrate)
            elif flowrate < 0:
                self.aspirate(volume,-flowrate)

    def stop(self):
        if self.is_pumping:
            self.stop_pumping()

    def fill(self, flowrate=-20):  # decreased standard filling rate to prevent air getting in the syringe
        self.generate_flow(flowrate)

    def empty(self, flowrate=80):
        self.generate_flow(flowrate)

    def close(self):
        pass






