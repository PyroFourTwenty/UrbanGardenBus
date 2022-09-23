import sys

sys.path.append("..") # needed to import the following packages
import threading
import headstation
from GardenBusClient.SupportedSensors.supported_sensors import sensors
from GardenBusClient.sensor import GardenBusSensor
from GardenBusClient.client import GardenBusClient, utils
import can
import random
from time import sleep


def get_pseudo_temperature_value():
    """
    This function returns an imaginary sensor value. This function is passed to the sensor object and 
    gets called when a sensor reading is requested by another node or the headstation.
    """
    # return a random value (the range is totally arbitrary)
    return round(random.uniform(14.80, 32.99), 2)


def request_value_after_10_seconds():
    sleep(10)
    print("requesting value")
    bytes= [
        70, # --> VALUE_REQUEST
        *utils.number_to_bytes(420,2), # --> node_id 
        *utils.number_to_bytes(1) # --> sensor slot
    ]
    bus = can.interface.Bus('test', bustype='virtual')
    msg = can.Message(arbitration_id=100, data=bytes)
    bus.send(msg)



if __name__ == '__main__':
    headstation = headstation.Headstation(bus=can.interface.Bus(
        'test', bustype='virtual'), start_looping=False)

    # create a thread that simulates a value request
    value_requester = threading.Thread(target=request_value_after_10_seconds)

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

    client.send_entry_packet()  # nodes have to be connected to the headstation before
    # they are able to register sensors
    # Note: clients send an entry packet automatically when starting to loop, which may result
    # in the headstation thinking, that the node is reconnecting to the network.

    dht22_temperature = GardenBusSensor(
        # get the id of DHT22 (temperature only)
        sensor_model_id=sensors["dht22_temperature"]["id"],
        tags=["dht22", "temperature", "no_calibration"],
        # pass our function which retrieves the sensor value
        get_value_function=get_pseudo_temperature_value
    )

    # print the tags of the sensor
    print(dht22_temperature.tags)

    success = client.register_sensor(
        sensor=dht22_temperature,  # pass the GardenBusSensor instance
        slot=1,  # the slot on which the sensor wil be registered
        resend_count=6,  # the number of times a new 'register sensor' packet is sent
        response_timeout=30  # the number of seconds to wait for a 'register sensor ACK' packet after sending the 'register sensor' packet
    )
    # start the value requester thread
    value_requester.start()
    try:
        client.loop()
    except KeyboardInterrupt:
        print("Stopping client and sending 'leave' packet")
        # let the client send a 'leave' packet to  inform other nodes that is not longer available
        client.leave_network()
        headstation.running = False  # tell the headstation to stop looping
        head_thread.join()  # wait for the headstation thread to end
        value_requester.join() # wait for the value requester thread to end