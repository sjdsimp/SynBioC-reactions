# -*- coding: utf-8 -*-
"""
Module to simplify communication with Huber unistat units.

Communication is provided by the Huber Softcheck module, this
module simplifies the command set to more human-readable
instructions.

@author: SDesimp1 
"""
from softcheck.logic import Com
import sys
from softcheck.conversion import Hex
import re

class huber(Com):
    
    def __init__(self, port, baudrate= 9600, timeout=1, verbose_level=1, exception_on_error=True):
        """
        Constructor for huber object
        
        Parameters
        ----------
        port : str
            specifies COM-port for unit. e.g. 'COM4'
        baudrate : int, optional
            Specifies baudrate to be used. The default is 9600.
        timeout : int, optional
            Specifies timeout. The default is 1.
        verbose_level : int, optional
            explains what is done:
            '1': explains what went wrong in case of an error
            '2': prints the sent and received string on the console
            '3': prints the time on sending and receiving strings also. 
            The default is 1.
        exception_on_error : bool, optional
            If an error occurs, should the program terminate/throw an exception?. The default is True.

        Returns
        -------
        None.

        """
        if type(port) is int:
            port = "COM" + str(port)
            
        interface = "serial" #initialize via serial interface
        Com.__init__(self, interface, timeout, verbose_level, exception_on_error) 
        
        
        self.open(port, baudrate) #open port
        
    def _handle_error(self, expression,s):
        """
        Defines what to do in case of an error
        
        Parameters
        ----------
        expression : str
            The request that went wrong.
        s : str
            Answer received from unit.

        Raises
        ------
        AssertionError
            Raises this error when _exception_on_error is True.

        Returns
        -------
        Prints error handling to console, returns False if verbsoe level is 0.

        """       
        if self._verbose_level >= 1:
            print("ATTENTION: Request for: ", expression, "went wrong. Received Answer was: ", s)
            sys.stdout.flush()
        if self._exception_on_error is True:
            raise AssertionError("A check went wrong")
        else:
            return False
        
    @staticmethod
    def int2hexstr(val, bytes_used):
        """
        @brief converts the value of an PB command to hex string
        @param val: integer to convert
        @param bytes_used: number of bits used for conversion to int
        @return string with hex value
        """
        val_str = Hex.int2hex(val, bytes_used * 8) # amount in bits = amount of bytes * 8
        val_str = val_str[2:] #hexadecimals are prefixed with 0x; drop this.
        non_hex = re.compile(r"[0-9a-fA-F]+")
        val_str = non_hex.search(val_str).group() #return match between val_str and non_hex; check if val_Str is in right format
        val_str = val_str.zfill(2 * bytes_used) #add zeros to reach total amount of bits;  hex character = 4 bits; 1 byte is 8 bits so hex = bytes * 2
        return val_str.upper() 
    
    @staticmethod
    def _str2val(hex_str,bit_size = 16):
        """
        @brief converts a PB command value (hex string) to int considering the bit length
        @param hex_str: string with hex value
        @param bit_size: size in bits of expected value (16 for standard command, 32 for extended)
        @return converted integer
        
        """
        return Hex.hex2int(hex_str, bit_size) 
    
    def _msg_getval(self, cmd):
        """returns the value of a PB command"""
        s = self.recv() #read from com object
        command = self.int2hexstr(cmd, 1) #convert,  size = 1 byte (2 hex chars) 
        expression = r"{S" + command + "([0-9a-fA-F]{4,8})\r\n" #compare with expected format and filter out value with ()
        result = re.match(expression, s) #check right format
        if result is not None:
            bit_size = len(result.group(1))*8 #bit size to pass to converter
            return self._str2val(result.group(1),bit_size) # get message part, because it's grouped by () in the expression it's checked against    
        else:
            return self._handle_error(expression, s) 
        
    def check(self, command, check):
            """
            @brief checks if the value of PB command is like expected
            @param command: command to check
            @param check: expected value
            @return True if ok; False if not
            """
            val = self._msg_getval(command) 
            if val == check:
                return True
            else:
                self._assert_errors += 1
                if self._verbose_level >= 1:
                    print("ATTENTION: checking the value went wrong. ", val, " != ", check)
                    if val == 32767 :
                        print("E-Grade missing?")
                    sys.stdout.flush()
                if self._exception_on_error is True:
                    raise AssertionError("A check went wrong")
                else:
                    return False
                
    def check_range(self, command, minimum, maximum):       
        """
        @brief checks if the value of PB command is within the expected range
        @param command: command to check
        @param minimum: minimal allowed value
        @param maximum: maximal allowed value
        @return True if ok; False if not
        """
        val = self._msg_getval(command)
        if minimum <= val <= maximum:
            return True
        else:
            self._assert_errors += 1
            if self._verbose_level >= 1:
                print("ATTENTION: checking the range went wrong. The value: ", val, "is not within (", minimum, "/", maximum, ")")
                if val == 32767 :
                    print("E-Grade missing?")
                sys.stdout.flush()
            if self._exception_on_error is True:
                raise AssertionError("A check went wrong")
            else:
                return False
    
    def send(self, cmd, value, bytes_used = 2):
        """sends a PB command with a certain value"""
        string = self.int2hexstr(value, bytes_used)
        command = self.int2hexstr(cmd, 1)
        cmd_str = r"{M" + command + string + "\r\n"
        super(huber, self).send(cmd_str) #send using method of super class Com. Can't use self.send because of same name 
    
    def request(self, cmd, length = 4):
        """requests a certain value"""
        
        command = self.int2hexstr(cmd, 1)
        cmd = r"{M" + command + "*"*length +  "\r\n"
        super(huber, self).send(cmd)
        
    def request_echo(self, command, **kwargs):
        """sends a command and awaits the answer"""
        self.request(command, **kwargs)
        return self._msg_getval(command)
    
    @staticmethod    
    def _ext_bit(bit_nr, val):
        """returns the value (0 or 1) of a given bit position"""
        return (val & (1 << bit_nr)) >> bit_nr
    
    def get_bit(self, cmd, bit_nr):
        """requests the value (0 or 1) of a given bit position"""
        val = self.request_echo(cmd)
        val = val & (1 << bit_nr)
        return val >> bit_nr

    def set_bit_echo(self, cmd, bit_nr):
        """sets a bit to 1 on a given bit position (and sends the command)"""
        val = self.request_echo(cmd)
        val = val | (1 << bit_nr)
        self.send(cmd, val)
        val = self._msg_getval(cmd)
        return self._ext_bit(bit_nr, val)

    def clear_bit(self, cmd, bit_nr):
        """clears a bit to 0 on a given bit position (and sends the command)"""
        val = self.request_echo(cmd)
        val = val & (~(1 << bit_nr))
        self.send(cmd, val)
        val = self._msg_getval(cmd)
        return self._ext_bit(bit_nr, val)
    
    @staticmethod 
    def _convert_T_send(T, extended = False):
        """
        Converts the temperature to the right format for use in Huber commands. Helper function 
        that passes the converted T to functions that send it to the unit.

        Parameters
        ----------
        T : float
            Temperature value, [-151.11; 500.00] without extended commands.
        extended : bool, optional
            Should 4 bytes be used for the command. this extends the temperature range to [-200.000; 500.000], with an
            additional significant digit. The additional deciaml place only provides new information if the DV-E grade
            is activated, otherwise the value is rounded and the last digit is always 0. The default is False.

        Returns
        -------
        T_converted : int
            Temperature converted to the format huber uses: [-15111; 50000]. Due to the inherent rounding down when casting to int,
            additional digits beyond the supported resolution of the command are omitted and the information they contain is lost.

        """
        if extended:
            return int(T*1000) 
        else:
            
            return int(T*100)
    
    @staticmethod 
    def _convert_T_receive(T, extended = False):
        """
        Converts the temperature from the huber format to the format that makes sens physics-wise. Helper function 
        that gets a T received from the Huber and converts it to the right format.
        Parameters
        ----------
        T : int
            Temperature value, [-15111; 50000] without extended commands.
        extended : bool, optional
            Should 4 bytes be used for the command. this extends the physical temperature range to [-200.000; 500.000], with an
            additional significant digit. The additional deciaml place only provides new information if the DV-E grade
            is activated, otherwise the value is rounded and the last digit is always 0. The default is False.

        Returns
        -------
        T_converted : float
            Temperature converted to the real-world format: [-151.11; 500.00]

        """
        if extended:
            return T/1000
        else:
            return T/100
    
    def setpoint(self, T = None, extended = False):
        """
        The setpoint is used by the temperature controller. With internal regulation, the setpoint applies for the internal
        temperature, with process regulation it applies for the process temperature. Please note: the setpoint specification
        can be overwritten by other setpoint indicators (e.g. temperature control program, analog 4...20 mA interface,...).

        Parameters
        ----------
        T : int, optional
            The temperature to be set, without any conversions. The default is None, when the setpoint is to be requested.
        extended : Bool, optional.
            Should 4 bytes be used for the command. this extends the temperature range to [-200.000; 500.000], with an
            additional significant digit. The additional decimal place only provides new information if the DV-E grade
            is activated, otherwise the value is rounded and the last digit is always 0. The default is False.

        Returns
        -------
        .
        """
        # TODO: fix for negative temperatures
        if T is not None:
            
            if extended:
                bytes_used = 4
                
            else:
                bytes_used = 2 
            T_converted = self._convert_T_send(T, extended)
            self.send(0,T_converted,bytes_used)
            
        else:
            SP = self.request_echo(0) #get value from unit
            return  self._convert_T_receive(SP,extended)
        
    def T_internal(self):
        T = self.request_echo(1)
        return self._convert_T_receive(T)
        
    def T_process(self):
        T = self.request_echo(58)
        return self._convert_T_receive(T)
    
    def control_mode(self, mode):
        """"0: internal control mode, 1: process control mode (cascade control) """
        self.send(19, mode)
    
    def T_return(self):
        T = self.request_echo(2)
        return self._convert_T_receive(T)
    
    def current_power(self):
        P = self.request_echo(4) #resolution is 1 W
        return P
    
    def start(self):
        self.send(20,1)
        
    def stop(self):
        self.send(20,0)



    
