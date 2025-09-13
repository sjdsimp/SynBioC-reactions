from reaction_platform import bronkhorst_control
import numpy as np
import time

instrument = bronkhorst_control.bronkhorst(1)
instrument.writeParameter(7, 64)
instrument.writeParameter(329, 2)

matrix = np.zeros([50, 1])

slope = 20
setpoint_1 = int(0.50 * 32000)
setpoint_2 = int(0.10 * 32000)

instrument.writeParameter(9, setpoint_1)

instrument.writeParameter(10, 600)
instrument.writeParameter(9, setpoint_2)
instrument.writeParameter(10, 0)
for i in range(50):
    matrix[i] = instrument.readParameter(9)
    time.sleep(1)
