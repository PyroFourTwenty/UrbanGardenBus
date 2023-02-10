import can
import sys
from GardenBusClient.sensor import GardenBusSensor
from . import gb_utils as utils
from . import gardenbus_config as config
from time import time, sleep
import numpy as np
sys.path.append('..')
from RAK811.rak811_control import RAK811


class GardenBusClient():

    bus: can.interface.Bus = None
    node_id = None
    sensors = {}
    tick_rate: float = None  # defines the rate at that the node sends alive packets
    # as well as other periodically timed packets (in seconds)
    running = False
    __last_alive = 0
    last_headstation_alive = None

    ttn_dev_eui = None
    ttn_dev_id = None
    ttn_app_key = None
    ttn_join_eui = None

    lorawan_serial = "serial-here"

    def __init__(self, bus: can.interface.Bus, node_id: int, ttn_dev_eui:str, ttn_dev_id:str, ttn_app_key:str, ttn_join_eui:str,tick_rate: float = 30, start_looping: bool = True, print_tick_rate=True):
        self.bus = bus
        self.node_id = node_id
        self.tick_rate = tick_rate
        
        self.ttn_dev_eui = ttn_dev_eui 
        self.ttn_dev_id = ttn_dev_id 
        self.ttn_app_key = ttn_app_key 
        self.ttn_join_eui = ttn_join_eui
        
        if print_tick_rate:
            print("[ {node_id} ] Initializing (tick rate: {tick_rate}s)".format(
                node_id=node_id, tick_rate=tick_rate))
        self.last_headstation_alive = time()
        if start_looping:
            self.loop()

    def send_packet(self, arbitration_id: int, bytes: list):
        msg = can.Message(arbitration_id=arbitration_id, data=bytes)
        self.bus.send(msg)
        return msg

    def send_entry_packet(self):
        self.running = True
        self.__last_alive = time()
        arbit_id = 100
        bytes = [1, *utils.number_to_bytes(self.node_id, 2)]
        return self.send_packet(arbitration_id=arbit_id, bytes=bytes)

    def send_alive_packet(self):
        self.__last_alive = time()
        arbit_id = 100
        bytes = [3, *utils.number_to_bytes(self.node_id, 2)]
        return self.send_packet(arbitration_id=arbit_id, bytes=bytes)

    def send_leave_packet(self):
        arbit_id = 100
        bytes = [2, *utils.number_to_bytes(self.node_id, 2)]
        return self.send_packet(arbitration_id=arbit_id, bytes=bytes)

    def send_register_sensor_packet(self, sensor: GardenBusSensor, sensor_slot: int, resend_count: int = 6, response_timeout: float = 30):
        arbit_id = 100
        self.sensors[sensor_slot] = sensor  # save the sensor
        bytes = [
            config.SENSOR_REGISTER_PACKET,  # header -> 1 byte
            *utils.number_to_bytes(self.node_id, 2),  # node_id -> 2 bytes
            # sensor_model_id -> 2 bytes
            *utils.number_to_bytes(sensor.sensor_model_id, 2),
            *utils.number_to_bytes(sensor_slot)  # sensor_slot -> 1 byte
        ]  # total size -> 6 bytes
        for _ in range(resend_count):
            self.send_packet(arbitration_id=arbit_id, bytes=bytes)

            timestamp = time()
            while (self.running and time()-timestamp < response_timeout):
                msg = self.bus.recv(timeout=0.01)
                if msg is not None:
                    targeted_node_id_of_packet = utils.bytes_to_number(
                        msg.data[1:3])
                    # check if the received packet is from the headstation that registered the sensor
                    if msg.data[0] == config.SENSOR_REGISTER_ACK_PACKET and targeted_node_id_of_packet == self.node_id:
                        # the slot that the sensor was registered on
                        slot = msg.data[5]
                        self.sensors[slot] = sensor  # save the sensor
                        sensor_name = utils.get_sensor_key_by_id(
                            sensor.sensor_model_id)

                        print("[ {node} ] registration successful: {sensor}".format(
                            node=self.node_id, sensor=sensor_name))
                        return True  # sensor was successfully registered at the headstation
                            
        print("{node} giving up".format(node=self.node_id))
        return False  # return False if the client was not able to register the sensor

    def send_unregister_sensor_packet(self, sensor_slot: int, resend_count: int = 6, response_timeout: float = 30):
        arbit_id = 100
        if sensor_slot in self.sensors:
            bytes = [
                config.SENSOR_UNREGISTER_PACKET, *utils.number_to_bytes(self.node_id, 2), *utils.number_to_bytes(sensor_slot)]
            for _ in range(resend_count):
                self.send_packet(arbitration_id=arbit_id, bytes=bytes)
                timestamp = time()
                while(self.running and time()-timestamp < response_timeout):
                    msg = self.bus.recv(timeout=0.01)
                    if msg is not None:
                        targeted_node_ide_of_packet = utils.bytes_to_number(
                            msg.data[1:3])
                        if msg.data[0] == config.SENSOR_UNREGISTER_ACK_PACKET and targeted_node_ide_of_packet == self.node_id:
                            print("[ {node} ] successfully unregistered sensor {sensor} on slot {slot}".format(
                                node=self.node_id,
                                sensor=self.sensors[sensor_slot],
                                slot=sensor_slot))
                            return True
            print("[ {node} ] unregistration of sensor on  {sensor} failed".format(
                node=self.node_id, sensor=self.sensors[sensor_slot]["model_name"]))
            return False
        else:
            print("[ {node} ] cannot unregister the sensor on slot {slot} because it is not registered".format(
                node=self.node_id, slot=sensor_slot))

    def send_calibration_request_packet(self, sensor_model_id, sensor_slot, resend_count: int = 6, response_timeout: float = 30):
        arbit_id = 100
        bytes = [
            config.CALIBRATION_REQUEST,
            *utils.number_to_bytes(self.node_id, 2),
            *utils.number_to_bytes(sensor_model_id, 2),
            *utils.number_to_bytes(sensor_slot)
        ]
        for _ in range(resend_count):
            self.send_packet(arbitration_id=arbit_id, bytes=bytes)
            timestamp = time()
            while(self.running and time()-timestamp < response_timeout):
                msg = self.bus.recv(timeout=0.01)
                if msg is not None:
                    targeted_node_id_of_packet = utils.bytes_to_number(
                        msg.data[1:3])
                    if msg.data[0] == config.CALIBRATION_RESPONSE and targeted_node_id_of_packet == self.node_id:
                        value_bytes = msg.data[4:9]
                        calibration_value = float(
                            np.frombuffer(value_bytes, dtype=np.float32))
                        self.sensors[sensor_slot].calibration_value = float(
                            calibration_value)
                        print("[ {node_id} ] got calibration value for sensorid {sensor_id} on slot {sensor_slot}: {calibration_value}".format(
                            node_id=self.node_id, sensor_id=sensor_model_id, sensor_slot=sensor_slot, calibration_value=calibration_value
                        ))
                        calibration_ack_bytes = [
                            config.CALIBRATION_ACK,
                            *utils.number_to_bytes(self.node_id, 2),
                            *utils.number_to_bytes(sensor_slot)
                        ]
                        self.send_packet(arbitration_id=arbit_id,
                                        bytes=calibration_ack_bytes)
                        return True

    def handle_value_request(self, sensor_slot):
        arbit_id = 100
        # send value request ACK packet
        print("[ {node_id} ] got value value request for slot {sensor_slot}".format(
            node_id=self.node_id, sensor_slot=sensor_slot,
        ))
        value_request_ack_bytes = [
            config.VALUE_REQUEST_ACK,
            *utils.number_to_bytes(self.node_id, 2),
            *utils.number_to_bytes(sensor_slot)
        ]
        self.send_packet(arbitration_id=arbit_id,
                        bytes=value_request_ack_bytes)
        # get actual sensor reading, this may take longer periods of time, so we send a VALUE_REQUEST_ACK packet beforehand,
        # so that the headstation knows that we got the packet but need more time to acquire the sensor reading
        sensor_value = self.sensors[sensor_slot].get_value()

        value_response_bytes = [
            config.VALUE_RESPONSE,
            *utils.number_to_bytes(self.node_id, 2),
            *utils.number_to_bytes(sensor_slot),
            *list(np.float32(sensor_value).tobytes())
        ]
        # send value response packet
        self.send_packet(arbitration_id=arbit_id, bytes=value_response_bytes)

    def register_sensor(self, sensor: GardenBusSensor, slot, resend_count: int = 6, response_timeout: float = 30):
        return self.send_register_sensor_packet(sensor=sensor, sensor_slot=slot, resend_count=resend_count, response_timeout=response_timeout)

    def unregister_sensor(self, slot):
        return self.send_unregister_sensor_packet(slot)

    def join_network(self):
        return self.send_entry_packet()

    def leave_network(self):
        return self.send_leave_packet()

    def calibrate_sensor(self, sensor: GardenBusSensor, sensor_slot):
        return self.send_calibration_request_packet(sensor_model_id=sensor.sensor_model_id, sensor_slot=sensor_slot)

    def send_lorawan_message(self):
        import numpy as np
        rak811 = RAK811(self.lorawan_serial)
        payload = ''
        for sensor_slot in sorted(self.sensors):
            sensor_value = self.sensors[sensor_slot].get_value()
            payload = ''.join([str(hex(b)).replace('0x','') for b in np.float32(sensor_value).tobytes()])
        rak811.send_lorawan_message(message=payload,
            region='EU868',
            app_eui=self.ttn_join_eui, 
            app_key=self.ttn_app_key,
            dev_eui=self.ttn_dev_eui
        )


    def loop(self):
        sleep(self.tick_rate)
        self.join_network()
        headstation_timeout_detected = False
        while self.running:
            if time()-self.__last_alive >= self.tick_rate:  # if the last alive-packet is more than the tickrate ago
                if not headstation_timeout_detected:
                    self.send_alive_packet()
                else:
                    self.send_lorawan_message()
            
            if time()-self.last_headstation_alive >= config.HEADSTATION_TICK_RATE and not headstation_timeout_detected:  # if the last alive-packet is more than the tickrate ago
                headstation_timeout_detected = True
                print("[ {node_id} ] Headstation timeout detected!".format(node_id=self.node_id))

            msg = self.bus.recv(timeout=1)  # wait for 1 second
            if msg is not None:  # handle message if one has been received
                if msg.data[0] == config.VALUE_REQUEST and utils.bytes_to_number(msg.data[1:3]) == self.node_id:
                    sensor_slot = utils.byte_to_number(msg.data[3])
                    self.handle_value_request(sensor_slot)
                elif msg.data[0] == config.ALIVE_PACKET:
                    node_id = utils.bytes_to_number(msg.data[1:3])
                    if node_id == config.HEADSTATION_NODE_ID:
                        if headstation_timeout_detected:
                            print("[ {node_id} ] headstation reconnected".format(node_id=self.node_id))
                        else:
                            print("[ {node_id} ] headstation is still connected".format(node_id=self.node_id))

                        self.last_headstation_alive = time()
                #print(str(self.node_id), "received a packet:", msg.data[0])

        print("[ {node_id} ] Goodbye".format(node_id=self.node_id))
        self.send_leave_packet()
        self.running = False