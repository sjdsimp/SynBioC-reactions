# -*- coding: utf-8 -*-
"""
Created on Fri Mar 11 10:36:32 2022

Module to control the 'challenge' reaction platform.

Methods
----------
    start_equipment
        start the platform
    
    stop_equipment
        stop the platform
        
    data_logger
        log the data to a file
    
    setpoint_changer
        Change the setpoints of the equipment  

@author: SDesimp1
"""
import sys
import os 
sys.path.append("C:\\Reaction platform\\Central control")
import time
from reaction_platform import cetoni_control
from reaction_platform import huber_control
import threading
import csv
from functools import partial

class controller:
    """ 
    A class to centralize platform control to a platform object.

    Parameters
    ----------
        config_dir: str
            The path to the Cetoni configuration folder. The default is None

        pump1_args: dict (optional)
            Additional arguments passed to the __init__ function of pump1. For an overview, consult the documentation
            of the pump drivers.
            Defaults to an empty dictionary.

        pump2_args: dict (optional)
            Additional arguments passed to the __init__ function of pump2. For an overview, consult the documentation
            of the pump drivers.
            Defaults to an empty dictionary.

        huber_args
            Additional arguments passed to the __init__ function of the Huber. For an overview, consult the
            documentation of the huber drivers.
            Defaults to an empty dictionary.

        setpoints: list (optional)
            setpoints of the equipment in the following format: [pump1_setpoint, pump2_setpoint, huber_setpoint]

                pump1_setpoint: float
                    The flowrate setpoint of pump 1, in the same units as the pump (default units: ml/min).
                    The default value is 0.

                pump2_setpoint: float
                    The flowrate setpoint of pump 2, in the same units as the pump (default units: ml/min).
                    The default value is 0.

                huber_setpoint: float
                    The temperature setpoint of the huber unit, in degrees Celcius. The default is 25.

        filename: str (optional)
            The name under which to save the log-file.

    Attributes
    ----------
        cetoni_bus: Bus object of qmixBus module
            Provides a bus for communication with the cetoni pumps
    
        pump1: cetoni object
            A member of the cetoni_control.cetoni class, to communicate with a pump.
            
        pump2: cetoni object
            A member of the cetoni_control.cetoni class, to communicate with a pump.
            
        huber: huber object
            A member of the huber_control.huber class, to communicate with a Huber unit.

        logging_state

        platform_state



    
    Methods
    ----------
    
    
    """
    def __init__(self, config_dir, pump1_args={}, pump2_args={}, huber_args={}, setpoints=None, filename="log",
                 T_control=True):
        
        if setpoints is None:
            setpoints = [0, 0]

        self.T_control = T_control

        if self.T_control:
            setpoints[2] = 25

        self._errorstate = 0
        self.logging_state = threading.Event()
        self.platform_state = threading.Event()

        self.logging_thread = threading.Thread(target=partial(self.data_logger, filename=filename))

        self._pump1_index = int(input("Provide index of pump 1. "))
        self._pump2_index = int(input("Provide index of pump 2. "))

        self.pump1_SP = 0
        self.pump2_SP = 0
        self.huber_SP = 25
        
        self.cetoni_bus = cetoni_control.initialize(config_dir)
        
        try:
            self.pump1 = cetoni_control.cetoni(self._pump1_index, **pump1_args)
        except:
            print("Error connecting to pump 1")
            self._errorstate = 1

        try:
            self.pump2 = cetoni_control.cetoni(self._pump2_index, **pump2_args)
        except:
            print("Error connecting to pump 2")
            self._errorstate = 1

        if self.T_control:
            self._huber_port = 'COM' + input("Enter the COM-port to connect with the huber: COM")
        
            try:
                self.huber = huber_control.huber(self._huber_port, **huber_args)
            except:
                print("Error connecting to the huber")
                self._errorstate = 1
        
        self.update_setpoints(setpoints)
        
        if not self._errorstate:
            print("Platform initialized, successfully connected to all equipment")
        
    def ready_equipment(self):
        self.pump1.fill()
        self.pump2.fill()

        if self.T_control:
            self.huber.start()

        time.sleep(5)
        self.logging_thread.start()
        
        print("Pumps filled, Temperature control started and logging thread started: platform ready.")
    
    @staticmethod
    def start_pump(pump, setpoint, volume=None, echo=True):
        pump.flow_rate = setpoint
        pump.start(flowrate=setpoint, volume=volume, echo_runtime=echo)
        print("{} started.".format(pump.device_name))
    
    def update_setpoints(self, setpoints):
        """ update setpoint flags"""
        self.pump1_SP = setpoints[0]
        self.pump2_SP = setpoints[1]
        if self.T_control:
            self.huber_SP = setpoints[2]

        # update setpoints in equipment itself
        self.pump1.flow_rate = self.pump1_SP
        self.pump2.flow_rate = self.pump2_SP
        if self.T_control:
            self.huber.setpoint(T=self.huber_SP)
    
    def start_platform(self, setpoints=None, volumes=[None, None], pump_echo=[True, True]):
        """ Start the platform. If no setpoints are given, use the current ones.
            Starting the platform also starts logging
        
        Parameters
        ----------
            setpoints: list, optional
                List with floating points representing the setpoints of the different equipment.
                always use the format [pump1_SP, pump2_sp, huber_sp]. The default is None.
        """
        self.platform_state.set()
        
        if setpoints is not None:
            self.update_setpoints(setpoints)
        
        self.start_pump(self.pump1, self.pump1_SP, volume=volumes[0], echo=pump_echo[0])
        self.start_pump(self.pump2, self.pump2_SP, volume=volumes[1], echo=pump_echo[1])

        self.toggle_logging()
        
    def stop_platform(self, empty=False):
        """ Stop the platform: stop pumps, and stop temperature control. Also stop logging and close the log file.
         Optionally, enpty the pumps"""
        
        self.pump1.stop()
        self.pump2.stop()
        if empty:
            self.pump1.generate_flow(100)
            self.pump1.generate_flow(100)
        if self.T_control:
            self.huber.stop()

        self.platform_state.clear()
        self.logging_state.clear()

        cetoni_control.close_communication(self.cetoni_bus)
        if self.T_control:
            self.huber.close()

        print("platform stopped, all connections to equipment closed")
    
    def pause_platform(self):
        """ 
        Pause the platform: stop pumps, but keep T control active. Pause logging, but keep log file open
        
        When this method is called, if the pumps are in the progress of dispensing a certain volume,
        the remaining volume to be dispensed will be discarded.
        """
        # TODO: implement attribute that remembers the volume that it was asked to dispense,
        # together with the fill level at the start of that command and use that to calculate the volume
        # remaining to be dispensed to complete  the initial request. Calculate this here and set as attribute
        
        self.pump1.stop()
        self.pump2.stop()
        
        self.logging_state.clear()
        print("Platform paused")
        
    def resume_platform(self):
        """Resume platform operation and logging """
        
        # TODO: when volume dispensing was active before pausing, set volume to remaining volume
        
        self.start_pump(self.pump1, self.pump1_SP)
        self.start_pump(self.pump2, self.pump2_SP)
        
        self.logging_state.set()
        print("Platform resumed")

    def toggle_logging(self):
        if self.logging_state.is_set():
            self.logging_state.clear()
        else:
            self.logging_state.set()

    def setpoint_changer(self, setpoints, volumes=None):
        """ 
        Change the setpoints of the equipment while it is running. For pumps, volumes are input as separate parameter.
        
        Parameters
        ----------
            setpoints: list
                List of setpoints for the equipment, in following format
                
            volumes: list
                Volumes to dispense for pump 1 and pump 2 respectively, in mL.
        """
        # pause logging to free up communication ports
        if volumes is None:
            volumes = [None, None]

        self.toggle_logging()
        # wait to make sure ports are free
        time.sleep(0.2)
        # change setpoints
        self.update_setpoints(setpoints)
        
        self.pump1.start(volume=volumes[0], flowrate=setpoints[0], echo_runtime=True)
        self.pump2.start(volume=volumes[1], flowrate=setpoints[1], echo_runtime=True)
        if self.T_control:
            self.huber.setpoint(T = setpoints[2])
        
        # resume logging
        self.toggle_logging()
        
    def data_logger(self, filename='log', logging_interval=2):
        """
        Log data to specified file
        
        Parameters
        ----------
            filename: str, optional
                Name of the log file, without the .csv extension. The default is 'log'
            
            logging_interval: float, optional
                The time between data points, in seconds. The default is 2.
        """
        # wait for event indicating platform is active
        self.platform_state.wait()
        
        # define header
        header = ['Timestamp', 'Pump 1 setpoint [mL/min]', 'Pump 1 flowrate [mL/min]', 'Pump 1 fill level [mL]', 
                  'Pump 2 setpoint [mL/min]', 'Pump 2 flowrate [mL/min]', 'Pump 2 fill level [mL]',
                  'Huber setpoint', 'Huber T internal', 'response time [ms]']
        # open file
        csv_file = open('.\logs\\' + filename + '.csv', 'w', newline='')
        # define logger
        datalogger = csv.writer(csv_file, delimiter=',')
        # write metadata
        metadata = ['log file initialized at ' + time.asctime()]
        datalogger.writerow(metadata)
        # write header
        datalogger.writerow(header)
        
        print("logging initialized")
        
        # log while the platform_state event is set (meaning the platform is active)
        while self.platform_state.isSet():
            
            # wait until logging_state event is set
            self.logging_state.wait()
            print("logging active")
            
            # log while logging_state event is set
            while self.logging_state.isSet():
                # collect data
                timestamp = time.asctime()
                start_time = time.time()
                # pump 1
                pump1_setpoint = self.pump1.flow_rate
                pump1_level = self.pump1.get_fill_level()
                pump1_flowrate = self.pump1.get_flow_is()
                # pump 2
                pump2_setpoint = self.pump2.flow_rate
                pump2_level = self.pump2.get_fill_level()
                pump2_flowrate = self.pump2.get_flow_is()
                # huber

                if self.T_control:
                    T_setpoint = self.huber_SP
                    T_actual = self.huber.T_internal()
                else:
                    T_setpoint = 'NA'
                    T_actual = 'NA'
                stop_time = time.time()
                response_time = (stop_time - start_time)
                
                # aggregate data
                data = [timestamp, pump1_setpoint, pump1_flowrate, pump1_level, pump2_setpoint,
                        pump2_flowrate, pump2_level, T_setpoint, T_actual, response_time*1000]
                # write data to file
                datalogger.writerow(data)
                
                # wait to collect next log until time between logs is at least equal to logging interval. if response time >= logging interval, directly proceed
                if response_time < logging_interval:
                    time.sleep(logging_interval-response_time)
            
            # if logging is paused (because the logging_state event is cleared), indicate this
            print("logging paused")
        
        # When platform_state event is cleared (indicating platform was stopped), close the log file
        csv_file.close()
        print("logging stopped at {}".format(time.asctime()))
        print("log file saved at '{}".format(os.getcwd())+"\logs'")
                