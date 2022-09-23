import sys

sys.path.append("..") # needed to import the following packages
import threading
import headstation
from GardenBusClient import gb_utils
from GardenBusClient.gardenbus_config import VALUE_REQUEST

from GardenBusClient.SupportedSensors.supported_sensors import sensors
from GardenBusClient.sensor import GardenBusSensor
from GardenBusClient.client import GardenBusClient
from gardenbus_config import *
import can
from time import sleep
import random


def get_value():
    ''' - returns a random value that represents an analog reading of a sensor
        - put your code that reads a value here
        - you can name this function whatever you want (as long as you pass it as the 'get_value_function' to the GardenBusSensor object)
        - you can return any type of object here
    '''
    sleep(3) # simulates the time it sometimes needs to acquire a sensor reading
    
    return random.randint(0,1023) # returns an (arbitrary) "analog" value
    
def apply_calibration(value, calibration_value):
    print("Post-processing/Calibration value:", calibration_value)
    value += calibration_value # apply calibration to the value (change this operation to whatever you need)
    print("Value with processing:", value)
    valueScaled = (float(value)) / float(1023)*100 # convert the "analog" reading to a percentage for example
    return valueScaled
    

def request_value():
    sleep(5)
    bus =  can.interface.Bus('test', bustype='virtual')
    print("now requesting  sensor reading")
    value_request_bytes = [
        VALUE_REQUEST, # packet identifier 
        *gb_utils.number_to_bytes(420,2), # node id
        *gb_utils.number_to_bytes(1) # sensor slot
    ]
    msg = can.Message(arbitration_id=100, data=value_request_bytes)
    bus.send(msg)
        

if __name__=='__main__': 
    
    headstation = headstation.Headstation(
        bus=can.interface.Bus('test', bustype='virtual'),
        start_looping=False,
        nodes_sensors_calibration_data={
            420:{ # <-- node_id
                1: { # <-- slot
                    "sensor_model_id": 3, # <-- id of "yl_69" (see supported_sensors.py for more info)
                    "calibration_value" : 1000000 # <-- actual calibration value
                }
            }
        }
    )

    # create a thread to run the headstation
    head_thread = threading.Thread(target=headstation.loop)
    head_thread.start()  # start the headstation thread

    client = GardenBusClient(
        # this example utilizes the virtual canbus
        bus=can.interface.Bus('test', bustype='virtual'),
        # the id of the node, has to be unique, values can be (including) 1 and 65535
        node_id=420,
        tick_rate=5.0,  # specifies the seconds between "alive" packets; defaults to 30.0
        # if set to True, the client starts the (blocking) loop; defaults to True
        start_looping=False,
        print_tick_rate=True  # prints the tick rate in constructor; defaults to True
    )

    yl_69 = GardenBusSensor(
        sensor_model_id=sensors["yl_69"]["id"], # <-- 3
        tags=["yl_69", "soil moisture", "water level"], # <-- you can put personalized tags here, which will be 
        #(uniquely) combined with the tags defined for this specific sensor in supported_sensors.py
        get_value_function=get_value, # <-- pass your sensor reading function here
        calibration_function=apply_calibration, # <-- pass the function for post processing your sensor reading here
        #calibration_value=4.2 # <-- you can set the calibration value here or get it later from the headstation
    )
    #   Another way to set the calibration value (hardcoded)
    #   yl_69.calibration_value = 4.2 
    #   print("YL69 value reading", yl_69.get_value())

    client.send_entry_packet()  # nodes have to be connected to the headstation before
    # they are able to register sensors
    # Note: clients send an entry packet automatically when starting to loop, which may result
    # in the headstation thinking, that the node is reconnecting to the network.

    success = client.register_sensor(
        sensor=yl_69,
        slot=1,
        resend_count=6,
        response_timeout=30
    )
    # The following lines show the behaviour of a sensor that requires a calibration but never got a calibration value 
    try:
        print(yl_69.get_value()) # this will throw an exception because this sensor requires a calibration value (per configuration in supported_sensors.py)
    except Exception as e:
        print("Caught an exception that was thrown because the sensor was not calibrated prior to reading the output. Exception message:", e)
    
    calibration_success = client.calibrate_sensor(yl_69,1) #calibrate sensor object on slot 1 

    #print(yl_69.get_value()) # this will not throw an exception because the sensor now has a calibration value

    value_requester_thread = threading.Thread(target=request_value) # create a thread to simulate a value request
    value_requester_thread.start() # start the value requester thread
    try:
        client.loop()
    except KeyboardInterrupt:
        print("Stopping client and sending 'leave' packet")
        client.leave_network()
        headstation.running= False
        head_thread.join()
        value_requester_thread
