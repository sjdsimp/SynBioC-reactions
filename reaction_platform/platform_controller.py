"""
Module to control the reaction platform in a modular fashion

classes
----------
    controller
        acts as a central controller for the reaction platform

    platformConfiguration
        Generates a configuration object containing the specifications of the equipment for the platform,
        from a configuration file

"""
import sys
import os

sys.path.append("C:\\Reaction platform\\Central Control")
import time
from reaction_platform import cetoni_control, huber_control, bronkhorst_control, DASnet, photoreactor
import threading
from functools import partial
import csv
from serial.serialutil import SerialException

__version__ = "0.2.1"  # added photoreactor integration


class Configuration:
    """
    Class to generate a platform configuration object from a configuration file

    Attributes
    ----------
        no_pumps: int
            Number of pumps to connect to the platform
        datalog: str
            name of the file containing the data-log. Defaults to 'datalog.csv'
        platform_log: str
            name of the file containing the latform log. Defaults to 'platform_log.csv'
        pumps: dict
            dictionary containing the names and configuration of the different pumps. the keys are the names of the
            different pumps, and the value associated to each key contains in turn a dictionary with the configuration.
            This dict is structured as follows: {"type": 'cetoni' or 'isco', "address": for type 'cetoni'--> device
            index (indicated on pump), for type 'isco'--> COM port ('COMx')}
        huber: dict
            dictionary containing the configuration of the huber. the structure is as follows:
            {"address": COM-port ('COMx')}. If not included in platform, defaults to a string: 'disabled'
        MFC: dict
            dictionary containing the configuration of the Bronkhorst mass flow controller. the structure is as
            follows: {"address": COM-port ('COMx'}. If not included in platform, defaults to a string: 'disabled'
        P_control: dict
            dictionary containing the configuration of the Bronkhorst pressure controller. the structure is as follows:
            {"address": COM-port ('COMx')}. If not included in platform, defaults to a string: 'disabled'
        photoreactor: dict
            dictionary containing the configuration of the Borealis photoreactor. the structure is as follows:
            {"address": COM-port ('COMx')}. If not included in the platform, defaults to a string: 'disabled'.

    methods
    ----------
        parse_configuration
            parse the configuration file and construct the configuration object
    """

    def __init__(self, configuration_file: str):
        """
        Initialization for the platformConfiguration class

        Parameters
        ----------
            configuration_file: str
                The name (includes path if not in main directory) of the configuration file for the platform.
        """

        self.no_pumps = 0
        self.pumps = {}
        self.huber = {}
        self.MFC = {}
        self.P_control = {}
        self.photoreactor = {}
        self.datalog = "datalog"
        self.platform_log = "platform_log"

        self.parse_configuration(configuration_file)

    def parse_configuration(self, configuration_file: str):
        """
        Parses the configuration file and updates the platformConfiguration object.

        Parameters
        -----------
            configuration_file: str
                Contains the configuration of the platform, in the following standard format (as .csv file).
                the first entry on each row is mandatory, even when not included in the platform.

                    logfile,name_of logfile, name_of_event_log (2nd and 3rd optional)
                    pumps,no_of_pump
                    pump_name,type,adress,additional arguments (repeat no_of_pumps times)
                    huber,enable/disable,address,additional arguments (3rd and 4th optional, if 'enable')
                    MFC,enable/disable,address,additional arguments (3rd and 4th optional, if 'enable')
                    PresCont,enable/disable,address,additional arguments(3rd and 4th optional, if 'enable')
                    photoreactor,enable/disable,address,additional arguments (3rd and 4th optional, if 'enable')

        """
        config_file = open(configuration_file, 'r')

        config_file_content = []
        csvreader = csv.reader(config_file)
        for row in csvreader:
            config_file_content.append(row)

        config_file.close()

        # log-file
        if len(config_file_content[0]) > 1:  # check whether filename for datalog-file is provided
            self.datalog = config_file_content[0][1]  # set logfile flag to the provided logfile
        if len(config_file_content[0]) > 2:  # check whether filename for platform log-file is provided
            self.platform_log = config_file_content[0][2]  # set logfile flag to the provided logfile

        # pumps
        self.no_pumps = int(config_file_content[1][1])

        if self.no_pumps > 0:
            for i in range(self.no_pumps):
                pump_config = config_file_content[i + 2]
                pump = {"type": pump_config[1], "address": pump_config[2]}
                self.pumps[pump_config[0]] = pump

        else:
            self.pumps = "disabled"

        # huber
        huber_config = config_file_content[2 + self.no_pumps]
        if huber_config[1].lower() == "enable":
            huber = {"address": huber_config[2]}
            self.huber = huber

        elif huber_config[1].lower() == "disable":
            self.huber = "disabled"

        # mass flow controller
        mfc_config = config_file_content[3 + self.no_pumps]
        if mfc_config[1].lower() == "enable":
            mfc = {"address": mfc_config[2]}
            self.MFC = mfc

        elif mfc_config[1].lower() == "disable":
            self.MFC = "disabled"

        # pressure controller
        prc_config = config_file_content[4 + self.no_pumps]
        if prc_config[1].lower() == "enable":
            prc = {"address": prc_config[2]}
            self.P_control = prc

        elif prc_config[1].lower() == "disable":
            self.P_control = "disabled"

        # photoreactor
        photoreactor_config = config_file_content[5 + self.no_pumps]
        if photoreactor_config[1].lower() == "enable":
            photoreactor_dict = {"address": photoreactor_config[2]}
            self.photoreactor = photoreactor_dict

        elif photoreactor_config[1].lower() == "disable":
            self.photoreactor = "disabled"

        # TODO: add support for **kwargs for pumps, Huber and Bronkhorst equipment


class Controller:
    """
    Provides control of reaction platform.

    Attributes
    ----------
        _errorstate: int (private)
            Keeps track of errors that arise during initialization of the equipment. This attribute is incremented
            by one each time an error occurs upon trying to connect with an instrument.
        _no_pumps_connected: int (private)
            The number of pumps connected to the platform. This is used internally to keep track of the different
            pumps and for diagnostic purposes.
        _any_cetoni: bool (private)
            Is True if at least one cetoni pump is connected, False otherwise. Used internally to decide whether a
            cetoni.bus object needs to be initialized.
        _datalog: file
            .csv file where data is written to by the datalogger
        _platform_log: file
            .csv file containing the platform event log, written to by the platform logger
        _pump_types: list of str
            List containing the types of all pumps to connect to, constructed from the platform config-object.
        platform_logger: object of 'csv' class
            csv-writer to write platform event data to the event log
        logging_state: Threading.event object
            Used for communication with the datalogger thread. Specifically, indicates wheter logging should be active
        platform_state: threading.event object
            Used for communication with the datalogger thread. Specifically, indicates whether the platform is active
        T_control_enabled: bool
            Flag to indicate whether temperature control is enabled (i.e. a huber is connected).
        P_control_enabled: bool
            Flag to indicate whether pressure control is enabled (i.e. a pressure controller is connected)
        MFC_enabled: bool
            Flag to indicate whether a mass flow controller is connected
        huber_SP: float
            The current setpoint of the huber unit. Present as internal flag to minimize amount of commands to be sent
            to the instrument.
        MFC_SP: float
            The current setpoint of the MFC. Present as internal flag to minimize amount of commands to be sent
            to the instrument.
        P_control_SP: float
            The current setpoint of the Pressure controller. Present as internal flag to minimize amount of commands
            to be sent to the instrument.
        config_dir: str
            The directory containing the configuration files for the cetoni system.
        config: platform_controller.configuration object
            Object containing the configuration of the platform, used for initialization
        logging_thread: Threading.thread object
            Thread where the datalogger function is excecuted, to be able to concurrently use the platform
        cetoni_bus: qmixbus.Bus object
            Object providing communication with the Cetoni unit
        pump1: cetoni_control.cetoni or DASnet.DASnet object
            Provides communication with a pump. The type depends on the pump type.
        pump1_SP: float
            The current setpoint for pump 1.
        pump2: cetoni_control.cetoni or DASnet.DASnet object
            Provides communication with a pump. The type depends on the pump type.
        pump2_SP: float
            The current setpoint for pump 2.
        pump3: cetoni_control.cetoni or DASnet.DASnet object
            Provides communication with a pump. The type depends on the pump type.
        pump3_SP: float
            The current setpoint for pump 3.
        pump4: cetoni_control.cetoni or DASnet.DASnet object
            Provides communication with a pump. The type depends on the pump type.
        pump4_SP: float
            The current setpoint for pump 4.
        pump5: cetoni_control.cetoni or DASnet.DASnet object
            Provides communication with a pump. The type depends on the pump type.
        pump5_SP: float
            The current setpoint for pump 5.
        pump6: cetoni_control.cetoni or DASnet.DASnet object
            Provides communication with a pump. The type depends on the pump type.
        pump6_SP: float
            The current setpoint for pump 6.
        pump7: cetoni_control.cetoni or DASnet.DASnet object
            Provides communication with a pump. The type depends on the pump type.
        pump7_SP: float
            The current setpoint for pump 7.
        MFC: bronkhorst_control.bronkhorst object
            Object to communicate with a Bronkhorst MFC
        huber: huber_control.huber object
            Object to communicate with a huber unit
        P_controller: bronkhorst_control.bronkhorst object
            Object to communicate with a Bronkhorst pressure controller

    Methods
    ----------
        append_platform_log
            add a line to the platform event log
        add_pump
            add a pump to the platform
        update_setpoints
            update the setpoints, both the internal flags and those of the equipment objects themselves
        ready_equipment
            Fill the pumps and start temperature control, if a huber unit is connected
        start_pump
            Helper function to start a single pumps
        start_experiment
            Start the experiment: start all pumps, gas flow if an MFC is present, set the pressure to the right value
            if a pressure controller is present. Start logging data to the datalog file
        stop_experiment
            Stop all equipment, stop logging and disconnect all equipment.
        pause_experiment
            Stop pumping and gas flow, but temperature and pressure control active, if present. Keep logging
        resume_experiment
            Resume pumping and gas flow
        change_setpoints
            Change the setpoints of the equipmen while the experiment is running
        toggle_logging
            Set or clear the logging state, depending on the initial state
        data_logger
            Logs data to a datalog file. The file is generated dynamically upon initialization, depending on which
            equipment is present
        get_pump_data: static method
            Helper function to get data from a pump
        start_all_pumps
            Start all pumps

    """

    def __init__(self, config_file: str, setpoints=None, config_dir=None):
        """
        Initializes platform object

        Parameters
        ----------
            config_file: str
                name (and path if not in root directory) of .csv-file containing the platform configuration.
                The format of this file is documented in the docstring of platform_controller.Configuration.
            setpoints: list
                contains setpoints for all equipment. The order of this list is the following:
                pump 1, ..., pump n, huber (if not present, enter 0), MFC (if not present, enter 0),
                Pressure controller (if not present, enter 0).
        """
        # some utility flags
        self._errorstate = 0
        self._no_pumps_connected = 0
        self._any_cetoni = False
        self.logging_state = threading.Event()
        self.platform_state = threading.Event()
        self.T_control_enabled = False
        self.P_control_enabled = False
        self.MFC_enabled = False
        self.photoreactor_enabled = False

        # initial setpoints
        # TODO: remove initial setpoints from configuration file
        self.huber_SP = 20
        self.MFC_SP = 0
        self.P_control_SP = 0
        self.photoreactor_SP = 0

        if config_dir is None:
            self.config_dir = "C:\\Reaction platform\\Cetoni\\Configuration\\4_nem_mid"
        else:
            self.config_dir = config_dir

        # parse configuration file
        self.config = Configuration(configuration_file=config_file)

        self.logging_thread = threading.Thread(target=partial(self.data_logger, logging_interval=2))

        # initialize platform logging
        self._datalog = None
        self._platform_log = open('.\logs\\' + self.config.platform_log + '.csv', 'w', newline='')
        self.platform_logger = csv.writer(self._platform_log, delimiter=',')
        self.platform_logger.writerow(['datalog:', self.config.datalog])
        self.append_platform_log(message='platform initialized')

        # connect to the pumps, as specified in configuration file
        if self.config.no_pumps > 0:
            self._pump_types = []
            for pump in self.config.pumps.values():
                self._pump_types.append(pump['type'])
            # if one of the pumps is cetoni, open the cetoni bus
            if 'cetoni' in self._pump_types:
                self.cetoni_bus = cetoni_control.initialize(self.config_dir)
                self._any_cetoni = True

            self.pump1 = None
            self.pump1_SP = 0
            if self.config.no_pumps > 1:
                self.pump2 = None
                self.pump2_SP = 0
            if self.config.no_pumps > 2:
                self.pump3 = None
                self.pump3_SP = 0
            if self.config.no_pumps > 3:
                self.pump4 = None
                self.pump4_SP = 0
            if self.config.no_pumps > 4:
                self.pump5 = None
                self.pump5_SP = 0
            if self.config.no_pumps > 5:
                self.pump6 = None
                self.pump6_SP = 0
            if self.config.no_pumps > 6:
                self.pump7 = None
                self.pump7_SP = 0

            # loop over pumps and add them to platform
            for pump, config in self.config.pumps.items():
                self.add_pump(name=pump, configuration=config)
            message = "connected to all pumps"
            print(message)
            self.append_platform_log(message)

        # check if huber enabled; if yes, add to platform
        if self.config.huber != 'disabled':
            self.T_control_enabled = True
            try:
                self.huber = huber_control.huber(self.config.huber["address"])
                self.huber.setpoint(self.huber_SP)
                message = "connected to huber at " + self.config.huber["address"]
                print(message)
                self.append_platform_log(message)

            except SerialException:
                self._errorstate += 1
                print("error connecting to huber")

        # check if MFC enabled; if yes, add to platform
        if self.config.MFC != "disabled":
            self.MFC_enabled = True
            try:
                self.MFC = bronkhorst_control.bronkhorst(self.config.MFC["address"])
                self.MFC.set_setpoint(self.MFC_SP, unit=self.MFC.unit, instrument_running=False)
                message = "connected to MFC at " + self.config.MFC["address"]
                print(message)
                self.append_platform_log(message)

            except SerialException:
                self._errorstate += 1
                print("error connecting to MFC")

        # check if Pressure controller enabled; if yes, add to platform
        if self.config.P_control != "disabled":
            self.P_control_enabled = True
            try:
                self.P_control = bronkhorst_control.bronkhorst(self.config.P_control["address"], device='PC', slope=100)
                self.P_control.set_setpoint(self.P_control_SP, unit=self.P_control.unit, instrument_running=False)
                message = "connected to Pressure controller at " + self.config.P_control["address"]
                print(message)
                self.append_platform_log(message)

            except SerialException:
                self._errorstate += 1
                print("error connecting to pressure controller")

        if self.config.photoreactor != "disabled":
            self.photoreactor_enabled = True
            try:
                self.photoreactor = photoreactor.Borealis(self.config.photoreactor["address"], baudrate=115200,
                                                          verbose=False)
                if self.photoreactor._connected:
                    message = "connected to Borealis at " + self.config.photoreactor["address"]
                    print(message)
                    self.append_platform_log(message)

            except SerialException:
                self._errorstate += 1
                print("error connecting to photoreactor")

        if setpoints is not None:
            self.update_setpoints(setpoints)

        if not self._errorstate:
            message = "Platform initialized, connected to all equipment"
            print(message)
            self.append_platform_log(message)

    def append_platform_log(self, message: str):
        """Appends message to the platform log"""
        self.platform_logger.writerow([time.asctime(), message])

    def add_pump(self, name, configuration):
        """
        function to add pumps to the platform. Currently, the platform supports up to 7 pumps, but the code
        can easily be adjusted to allow more pumps. The function takes a pump name and configuration string and
        initializes the hardware connection with the device to the corresponding attribute of the platform object.

        Parameters
        ----------
            name: str
                The name to give the device
            configuration: [str]
                List containing the configuration of the device, used for making the connection to the hardware.
                The format of this list can be found in the documentation of the Configuration class.
        """

        # check whether the pump is Cetoni or Isco
        if self._no_pumps_connected == 0:
            pump_type = configuration["type"]
            if pump_type == 'cetoni':
                self.pump1 = cetoni_control.cetoni(int(configuration['address']))
            elif pump_type == 'isco':
                self.pump1 = DASnet.DASnet(configuration["address"])
                self.pump1.control()
            self.pump1.flow_rate = self.pump1_SP
            self.pump1.name = name
            message = "pump 1 configured as " + name + ", connected at " + configuration["address"]
            print(message)
            self.append_platform_log(message)

        if self._no_pumps_connected == 1:
            pump_type = configuration["type"]
            if pump_type == 'cetoni':
                self.pump2 = cetoni_control.cetoni(int(configuration['address']))
            elif pump_type == 'isco':
                self.pump2 = DASnet.DASnet(configuration["address"])
                self.pump2.control()
            self.pump2.flow_rate = self.pump2_SP
            self.pump2.name = name
            message = "pump 2 configured as " + name
            print(message)
            self.append_platform_log(message)

        if self._no_pumps_connected == 2:
            pump_type = configuration["type"]
            if pump_type == 'cetoni':
                self.pump3 = cetoni_control.cetoni(int(configuration['address']))
            elif pump_type == 'isco':
                self.pump3 = DASnet.DASnet(configuration["address"])
                self.pump3.control()
            self.pump3.flow_rate = self.pump3_SP
            self.pump3.name = name
            message = "pump 3 configured as " + name
            print(message)
            self.append_platform_log(message)

        if self._no_pumps_connected == 3:
            pump_type = configuration["type"]
            if pump_type == 'cetoni':
                self.pump4 = cetoni_control.cetoni(int(configuration['address']))
            elif pump_type == 'isco':
                self.pump4 = DASnet.DASnet(configuration["address"])
                self.pump4.control()
            self.pump4.flow_rate = self.pump4_SP
            self.pump4.name = name
            message = "pump 4 configured as " + name
            print(message)
            self.append_platform_log(message)

        if self._no_pumps_connected == 4:
            pump_type = configuration["type"]
            if pump_type == 'cetoni':
                self.pump5 = cetoni_control.cetoni(int(configuration['address']))
            elif pump_type == 'isco':
                self.pump5 = DASnet.DASnet(configuration["address"])
                self.pump5.control()
            self.pump5.flow_rate = self.pump5_SP
            self.pump5.name = name
            message = "pump 5 configured as " + name
            print(message)
            self.append_platform_log(message)

        if self._no_pumps_connected == 5:
            pump_type = configuration["type"]
            if pump_type == 'cetoni':
                self.pump6 = cetoni_control.cetoni(int(configuration['address']))
            elif pump_type == 'isco':
                self.pump6 = DASnet.DASnet(configuration["address"])
                self.pump6.control()
            self.pump6.flow_rate = self.pump6_SP
            self.pump6.name = name
            message = "pump 6 configured as " + name
            print(message)
            self.append_platform_log(message)

        if self._no_pumps_connected == 6:
            pump_type = configuration["type"]
            if pump_type == 'cetoni':
                self.pump7 = cetoni_control.cetoni(int(configuration['address']))
            elif pump_type == 'isco':
                self.pump7 = DASnet.DASnet(configuration["address"])
                self.pump7.control()
            self.pump7.flow_rate = self.pump7_SP
            self.pump7.name = name
            message = "pump 7 configured as " + name
            print(message)
            self.append_platform_log(message)
        self._no_pumps_connected += 1

    def update_setpoints(self, setpoints):
        """ Update setpoint flags and internal setpoints for all equipment

        Parameters
        ----------
            setpoints: list
                contains setpoints for all equipment. The order of this list is the following:
                pump 1, ..., pump n, huber (if not present, enter 20), MFC (if not present, enter 0),
                Pressure controller (if not present, enter 0), photoreactor (if not present, enter 0).
        """
        if self._no_pumps_connected >= 1:
            self.pump1_SP = setpoints[0]
            self.pump1.flow_rate = setpoints[0]

        if self._no_pumps_connected >= 2:
            self.pump2_SP = setpoints[1]
            self.pump2.flow_rate = setpoints[1]

        if self._no_pumps_connected >= 3:
            self.pump3_SP = setpoints[2]
            self.pump3.flow_rate = setpoints[2]

        if self._no_pumps_connected >= 4:
            self.pump4_SP = setpoints[3]
            self.pump4.flow_rate = setpoints[3]

        if self._no_pumps_connected >= 5:
            self.pump5_SP = setpoints[4]
            self.pump5.flow_rate = setpoints[4]

        if self._no_pumps_connected >= 6:
            self.pump6_SP = setpoints[5]
            self.pump6.flow_rate = setpoints[5]

        if self._no_pumps_connected >= 7:
            self.pump7_SP = setpoints[6]
            self.pump7.flow_rate = setpoints[6]

        if self.T_control_enabled:
            self.huber_SP = setpoints[self._no_pumps_connected]
            self.huber.setpoint(self.huber_SP)

        if self.MFC_enabled:
            self.MFC_SP = setpoints[self._no_pumps_connected + 1]
            self.MFC.set_setpoint(self.MFC_SP, unit=self.MFC.unit, instrument_running=False)

        if self.P_control_enabled:
            self.P_control_SP = setpoints[self._no_pumps_connected + 2]
            self.P_control.set_setpoint(self.MFC_SP, unit=self.P_control.unit, instrument_running=False)

        if self.photoreactor_enabled:
            self.photoreactor_SP = setpoints[self._no_pumps_connected + 3]
            self.photoreactor.power = self.photoreactor_SP

        message = "setpoints updated"
        print(message)
        self.append_platform_log(message)

    def ready_equipment(self):
        """Fill pumps, start temperature control"""
        if self._no_pumps_connected >= 1:
            self.pump1.fill()

        if self._no_pumps_connected >= 2:
            self.pump2.fill()

        if self._no_pumps_connected >= 3:
            self.pump3.fill()

        if self._no_pumps_connected >= 4:
            self.pump4.fill()

        if self._no_pumps_connected >= 5:
            self.pump5.fill()

        if self._no_pumps_connected >= 6:
            self.pump6.fill()

        if self._no_pumps_connected >= 7:
            self.pump7.fill()

        if self.T_control_enabled:
            self.huber.start()

        time.sleep(10)

        self.logging_thread.start()

        message = "pumps filled, temperature control started, logging file initialized. Platform " \
                  "ready for start of experiment."

        print(message)
        self.append_platform_log(message)

    def start_pump(self, pump, setpoint, volume=None, echo=True):
        """" Start pumping with provided parameters"""
        pump.flow_rate = setpoint
        pump.start(flowrate=setpoint, volume=volume, echo_runtime=echo)
        message = "{} started.".format(pump.name)
        print(message)
        self.append_platform_log(message)

    def start_experiment(self, setpoints=None, volumes=None, pump_echo=True):
        """start all equipment and start logging data"""
        if volumes is None:
            volumes = [None] * self._no_pumps_connected

        self.platform_state.set()

        if setpoints is not None:
            self.update_setpoints(setpoints)

        # start logging data
        self.toggle_logging()

        # start pumps
        self.start_all_pumps(volumes=volumes, pump_echo=pump_echo)
        self.append_platform_log("pumps started")

        # start gas flow
        if self.MFC_enabled:
            self.MFC.start()
            self.append_platform_log("Gas flow started")

        # increase pressure until setpoint.
        if self.P_control_enabled:
            self.P_control.start()
            self.append_platform_log("Pressure controller started")

        if self.photoreactor_enabled:
            self.photoreactor.enable()
            self.append_platform_log("Photoreactor switched on")

    def stop_experiment(self, empty=False):
        """"Stop the experiment, close log files, close connections to equipment"""
        self.append_platform_log("experiment stopped, closing connections to equipment")

        # clear events to stop logging
        self.logging_state.clear()
        self.platform_state.clear()
        self.append_platform_log("datalogging stopped")

        time.sleep(1)

        # TODO: fix emptying
        # close connections to pumps
        if self._no_pumps_connected >= 1:
            if empty:
                self.pump1.empty()
            self.pump1.stop()
            self.pump1.close()
        if self._no_pumps_connected >= 2:
            if empty:
                self.pump2.empty()
            self.pump2.stop()
            self.pump2.close()
        if self._no_pumps_connected >= 3:
            if empty:
                self.pump3.empty()
            self.pump3.stop()
            self.pump3.close()
        if self._no_pumps_connected >= 4:
            if empty:
                self.pump4.empty()
            self.pump4.stop()
            self.pump4.close()
        if self._no_pumps_connected >= 5:
            if empty:
                self.pump5.empty()
            self.pump5.stop()
            self.pump5.close()
        if self._no_pumps_connected >= 6:
            if empty:
                self.pump6.empty()
            self.pump6.stop()
            self.pump6.close()
        if self._no_pumps_connected >= 7:
            if empty:
                self.pump7.empty()
            self.pump7.stop()
            self.pump7.close()
        self.append_platform_log("pumps disconnected")

        # if a cetoni pump was present, close the bus
        if 'cetoni' in self._pump_types:
            cetoni_control.close_communication(self.cetoni_bus)
            self.append_platform_log("cetoni bus closed")

        # turn of LED
        if self.photoreactor_enabled:
            self.photoreactor.disable()
            self.photoreactor.close_connection()
            self.append_platform_log("LED turned off, connection to borealis closed")

        # stop and close connection to Huber
        if self.T_control_enabled:
            self.huber.stop()
            self.huber.close()
            self.append_platform_log("Temperature control stopped, connection to huber closed")

        # stop and close connection to MFC
        if self.MFC_enabled:
            self.MFC.stop()
            self.MFC.close()
            self.append_platform_log("MFC stopped, connection closed")

        # stop and close connection to pressure controller, gradual pressure release
        if self.P_control_enabled:
            self.P_control.stop()
            self.P_control.close()
            self.append_platform_log("Pressure controller stopped, connection closed")

        self.append_platform_log("platform stopped, stopping platform logging")
        time.sleep(1)
        self._platform_log.close()

    def pause_experiment(self, logging=False):
        """pause the experiment: stop all pumps, but keep Temperature and pressure control active LED turned off.
        keep logging data, but keep datalog file open."""
        # TODO: check functioning of 'logging' parameter
        if self.MFC_enabled:
            self.MFC.stop()

        if self.photoreactor_enabled:
            self.photoreactor.disable()

        if self._no_pumps_connected >= 1:
            self.pump1.stop()
        if self._no_pumps_connected >= 2:
            self.pump2.stop()
        if self._no_pumps_connected >= 3:
            self.pump3.stop()
        if self._no_pumps_connected >= 4:
            self.pump4.stop()
        if self._no_pumps_connected >= 5:
            self.pump5.stop()
        if self._no_pumps_connected >= 6:
            self.pump6.stop()
        if self._no_pumps_connected >= 7:
            self.pump7.stop()

        if logging:
            self.logging_state.clear()

        message = "experiment paused"
        print(message)
        self.append_platform_log(message)

    def resume_experiment(self):
        """resume the experiment (pumps and MFC) and data logging if it was paused)"""
        # TODO: add setpoints, if provided: change upon restart
        if not self.logging_state.is_set():
            self.logging_state.set()

        self.start_all_pumps()

        if self.MFC_enabled:
            self.MFC.start()

        if self.photoreactor_enabled:
            self.photoreactor.resume()

        message = "experiment resumed"
        print(message)
        self.append_platform_log(message)

    def toggle_logging(self):
        """toggle logging"""
        if self.logging_state.is_set():
            self.logging_state.clear()
        else:
            self.logging_state.set()

    def change_setpoints(self, setpoints, volumes=None, pump_echo=True):
        """change setpoints of the equipment while an experiment is running.
        The logging is paused to not block the connections to the equipment"""
        if volumes is None:
            volumes = [None] * self._no_pumps_connected

        # update setpoints
        self.update_setpoints(setpoints)

        # pause logging to free up connections
        self.toggle_logging()
        time.sleep(1)

        # start pumps with new setpoints
        self.start_all_pumps(volumes=volumes, pump_echo=pump_echo)

        # change MFC setpoint
        if self.MFC_enabled:
            self.MFC.set_setpoint(setpoint=self.MFC_SP, unit=self.MFC.unit, instrument_running=True)

        # change P_controller setpoint
        if self.P_control_enabled:
            self.P_control.set_setpoint(setpoint=self.P_control_SP, unit=self.P_control.unit, instrument_running=True)

        # change huber setpoint
        if self.T_control_enabled:
            self.huber.setpoint(self.huber_SP)
        # TODO: wait until temperature reached

        # set photoreactor power
        if self.photoreactor_enabled:
            self.photoreactor.set_power(self.photoreactor_SP)

        # turn logging back on
        self.toggle_logging()

        message = "platform running with updated setpoints: {}".format(setpoints)
        print(message)
        self.append_platform_log(message)

    def data_logger(self, logging_interval=2):
        """Log experiment data to datalog file

        Parameters
        ----------
            logging_interval: float, optional
                The time between data points, in seconds. The default is 2.
        """

        # wait until platform_state is set, indicating an experiment was started
        self.platform_state.wait()

        # construct header
        header = ['timestamp']

        for pump in self.config.pumps.keys():
            header.append(pump + ' setpoint [mL/min')
            header.append(pump + ' flowrate [ mL/min]')
            header.append(pump + ' fill level [mL]')

        if self.T_control_enabled:
            header.append('Huber setpoint')
            header.append('Huber process temperature')

        if self.MFC_enabled:
            header.append('MFC setpoint [{}]'.format(self.MFC.unit))
            header.append('MFC measure [{}]'.format(self.MFC.unit))

        if self.P_control_enabled:
            header.append('Pressure setpoint [{}]'.format(self.P_control.unit))
            header.append('Pressure [{}]'.format(self.P_control.unit))

        if self.photoreactor_enabled:
            header.append('LED power setpoint')
            header.append('LED power actual')
            header.append('LED current')
            header.append('reactor temperature')
            header.append('LED temperature')

        header.append('response time [ms]')
        # TODO: get huber internal setpoint

        # open file
        self._datalog = open('.\logs\\' + self.config.datalog + '.csv', 'w', newline='')
        # define datalogger
        datalogger = csv.writer(self._datalog, delimiter=',')
        # write metadata
        metadata = ['log file initialized at ' + time.asctime()]
        datalogger.writerow(metadata)
        # write header
        datalogger.writerow(header)

        message = "logging file initialized"
        print(message)
        self.append_platform_log(message)

        while self.platform_state.is_set():
            # wait until logging stat is set
            self.logging_state.wait()
            message = "logging active"
            print(message)
            self.append_platform_log(message)

            while self.logging_state.is_set():
                # collect data
                data = [time.asctime()]
                start_time = time.time()
                # pumps
                if self._no_pumps_connected >= 1:
                    setpoint, flowrate, level = self.get_pump_data(self.pump1)
                    data.append(setpoint)
                    data.append(flowrate)
                    data.append(level)
                if self._no_pumps_connected >= 2:
                    setpoint, flowrate, level = self.get_pump_data(self.pump2)
                    data.append(setpoint)
                    data.append(flowrate)
                    data.append(level)
                if self._no_pumps_connected >= 3:
                    setpoint, flowrate, level = self.get_pump_data(self.pump3)
                    data.append(setpoint)
                    data.append(flowrate)
                    data.append(level)
                if self._no_pumps_connected >= 4:
                    setpoint, flowrate, level = self.get_pump_data(self.pump4)
                    data.append(setpoint)
                    data.append(flowrate)
                    data.append(level)
                if self._no_pumps_connected >= 5:
                    setpoint, flowrate, level = self.get_pump_data(self.pump5)
                    data.append(setpoint)
                    data.append(flowrate)
                    data.append(level)
                if self._no_pumps_connected >= 6:
                    setpoint, flowrate, level = self.get_pump_data(self.pump6)
                    data.append(setpoint)
                    data.append(flowrate)
                    data.append(level)
                if self._no_pumps_connected >= 7:
                    setpoint, flowrate, level = self.get_pump_data(self.pump7)
                    data.append(setpoint)
                    data.append(flowrate)
                    data.append(level)

                # huber
                if self.T_control_enabled:
                    data.append(self.huber_SP)
                    data.append(self.huber.T_process())
                # MFC
                if self.MFC_enabled:
                    data.append(self.MFC_SP)
                    data.append(self.MFC.get_measure(unit=self.MFC.unit))
                # Pressure
                if self.P_control_enabled:
                    data.append(self.P_control_SP)
                    data.append(self.P_control.get_measure(unit=self.P_control.unit))
                # Photoreactor
                if self.photoreactor_enabled:
                    data.append(self.photoreactor_SP)
                    status = self.photoreactor.get_status()
                    data.append(status.iloc[0]['Power'] * status.iloc[0]['Lamp enabled'])
                    data.append(status.iloc[0]['Current'])
                    data.append(status.iloc[0]['T reactor'])
                    data.append(status.iloc[0]['T lamp'])

                stop_time = time.time()
                response_time = stop_time - start_time
                data.append(response_time * 1000)

                datalogger.writerow(data)

                if response_time < logging_interval:
                    time.sleep(logging_interval - response_time)
            message = "logging paused"
            print(message)
            self.append_platform_log(message)
        self._datalog.close()
        message = "logging stopped, log file saved at '{}".format(os.getcwd()) + "\logs'"
        print(message)
        self.append_platform_log(message)

    @staticmethod
    def get_pump_data(pump):
        setpoint = pump.flow_rate
        flowrate = pump.get_flow_is()
        level = pump.get_fill_level()
        return setpoint, flowrate, level

    def start_all_pumps(self, volumes=None, pump_echo=True):
        """start all connected pumps with the currently configured setpoints"""

        if volumes is None:
            volumes = [None] * self._no_pumps_connected

        if self._no_pumps_connected >= 1:
            self.start_pump(self.pump1, self.pump1_SP, volume=volumes[0], echo=pump_echo)

        if self._no_pumps_connected >= 2:
            self.start_pump(self.pump2, self.pump2_SP, volume=volumes[0], echo=pump_echo)

        if self._no_pumps_connected >= 3:
            self.start_pump(self.pump3, self.pump3_SP, volume=volumes[0], echo=pump_echo)

        if self._no_pumps_connected >= 4:
            self.start_pump(self.pump4, self.pump4_SP, volume=volumes[0], echo=pump_echo)

        if self._no_pumps_connected >= 5:
            self.start_pump(self.pump5, self.pump5_SP, volume=volumes[0], echo=pump_echo)

        if self._no_pumps_connected >= 6:
            self.start_pump(self.pump6, self.pump6_SP, volume=volumes[0], echo=pump_echo)

        if self._no_pumps_connected >= 7:
            self.start_pump(self.pump7, self.pump7_SP, volume=volumes[0], echo=pump_echo)
