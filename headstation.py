import can
from gb_headstation_utils import *
from time import time
from gardenbus_config import *
from GardenBusClient.SupportedSensors import supported_sensors
import numpy as np


class Headstation():
    connected_clients: dict = None
    bus: can.interface.Bus = None
    running: bool = False
    nodes_sensors_calibration_data: dict = None  # has to be set before looping

    def __init__(self, bus, start_looping: bool = True, nodes_sensors_calibration_data={}):
        self.bus = bus
        self.connected_clients = {}
        self.nodes_sensors_calibration_data = nodes_sensors_calibration_data
        if start_looping:
            self.loop()

    def send_packet(self, arbitration_id, bytes: list):
        msg = can.Message(arbitration_id=arbitration_id, data=bytes)
        self.bus.send(msg)
        return msg

    def handle_node_entry(self, node_id: int):
        if node_id in self.connected_clients:
            print('[ HEAD ] Node {node_id} reconnected to the network'.format(
                node_id=node_id))

            self.connected_clients[node_id]["last_alive"] = time()
        else:
            self.connected_clients[node_id] = {
                "last_alive": time(),
                "sensors": {},
            }
            print('[ HEAD ] Node {node_id} joined the network'.format(
                node_id=node_id))

    def handle_node_leave(self, node_id):
        self.connected_clients.pop(node_id, None)
        print('[ HEAD ] Node {node_id} left the network'.format(
            node_id=node_id))

    def handle_node_alive(self, node_id):
        if node_id in self.connected_clients:
            print('[ HEAD ] Node {node_id} is still connected ({timestamp})'.format(
                node_id=node_id, timestamp=time()))
            self.connected_clients[node_id]["last_alive"] = time()
        else:
            print("[ HEAD ] Node {node} sent alive packet but has never sent an entry packet".format(
                node=node_id))

    def handle_sensor_registered(self, node_id: int, sensor_model_id, sensor_slot: int):
        arbit_id = 99
        if node_id in self.connected_clients:
            bytes = [SENSOR_REGISTER_ACK_PACKET, *number_to_bytes(node_id, 2), *number_to_bytes(
                sensor_model_id, 2), *number_to_bytes(sensor_slot)]
            self.send_packet(arbitration_id=arbit_id, bytes=bytes)
            sensor_name = supported_sensors.sensors[get_sensor_key_by_id(
                sensor_model_id)]["model_name"]
            self.connected_clients[node_id]["sensors"][sensor_slot] = {
                "sensor_model_id": sensor_model_id,
                "sensor_model_name": sensor_name
            }
            print("[ HEAD ] Node {node} registered sensor {sensor} on slot {slot}".format(
                node=node_id, sensor=sensor_name, slot=sensor_slot))
        else:
            print("[ HEAD ] Node {node} tried to register a sensor but has never sent an entry packet".format(
                node=node_id))

    def handle_sensor_unregistered(self, node_id: int, sensor_slot):
        arbit_id = 99
        if node_id in self.connected_clients:
            del self.connected_clients[node_id]["sensors"][sensor_slot]
            bytes = [SENSOR_UNREGISTER_ACK_PACKET,
                     *number_to_bytes(node_id, 2), *number_to_bytes(sensor_slot)]
            self.send_packet(arbitration_id=arbit_id, bytes=bytes)
        else:
            print(
                "[ HEAD ] Node {node} wanted to unregister sensor on slot {sensor_slot} but is not a registered client".format(node=node_id, sensor_slot=sensor_slot))

    def handle_sensor_calibration_requested(self, node_id: int, sensor_slot: int, sensor_model_id: int, resend_count: int = 6, response_timeout: float = 30):
        arbit_id = 99
        sensor_calibration_data = self.nodes_sensors_calibration_data[node_id][sensor_slot]
        calibration_value = sensor_calibration_data["calibration_value"]
        print('[ HEAD ] Node {node_id} requested calibration value for sensor {sensor_model_id} on slot {sensor_slot} which is: {calibration_value}'.format(
            node_id=node_id, sensor_model_id=sensor_model_id, sensor_slot=sensor_slot, calibration_value=calibration_value))

        # check if the calibration data corresponds to the request of the node
        if sensor_model_id == sensor_calibration_data["sensor_model_id"]:
            bytes = [CALIBRATION_RESPONSE,
                     *number_to_bytes(node_id, 2),
                     *number_to_bytes(sensor_slot),
                     *list(np.float32(calibration_value).tobytes())
                     ]
            for _ in range(resend_count):
                self.send_packet(arbitration_id=arbit_id, bytes=bytes)
                timestamp = time()
                while(self.running and time()-timestamp < response_timeout):
                    msg = self.bus.recv(timeout=0.01)
                    if msg is not None:
                        if msg.data[0] == CALIBRATION_ACK:
                            received_packet_node_id = bytes_to_number(
                                msg.data[1:3])
                            received_packet_slot = byte_to_number(msg.data[3])
                            if msg.data[0] == CALIBRATION_ACK and received_packet_node_id == node_id and received_packet_slot == sensor_slot:
                                print("[ HEAD ] Node {node_id} successfully received calibration value for sensor on slot {sensor_slot}".format(
                                    node_id=node_id, sensor_slot=sensor_slot))
                                return True
            return False

    def parse_packet(self, data: list):
        packet_identifier = data[0]
        node_id = bytes_to_number(data[1:3])
        if packet_identifier == ENTRY_PACKET:
            self.handle_node_entry(node_id)
        elif packet_identifier == LEAVE_PACKET:
            self.handle_node_leave(node_id)
        elif packet_identifier == ALIVE_PACKET:
            self.handle_node_alive(node_id)
        elif packet_identifier == CALIBRATION_REQUEST:
            sensor_model_id = bytes_to_number(data[3:5])
            sensor_slot = byte_to_number(data[5])  # something was changed here
            self.handle_sensor_calibration_requested(
                node_id, sensor_slot, sensor_model_id)
        elif packet_identifier == SENSOR_REGISTER_PACKET:
            sensor_model_id = bytes_to_number(data[3:5])
            sensor_slot = bytes_to_number([data[5]])
            self.handle_sensor_registered(
                node_id=node_id,
                sensor_model_id=sensor_model_id, sensor_slot=sensor_slot)
        elif packet_identifier == SENSOR_UNREGISTER_PACKET:
            slot = byte_to_number(data[3])
            self.handle_sensor_unregistered(node_id, slot)
        elif packet_identifier == VALUE_REQUEST:
            node_id = bytes_to_number(data[1:3])
            slot = byte_to_number(data[3])
            print("[ HEAD ] A node has requested a value from node {node_id} on slot {slot}".format(
                node_id=node_id, slot=slot))
        elif packet_identifier == VALUE_REQUEST_ACK:
            node_id = bytes_to_number(data[1:3])
            slot = byte_to_number(data[3])
            print("[ HEAD ] Node {node_id} has acknowledged the request for slot {slot}".format(
                node_id=node_id, slot=slot))
        elif packet_identifier == VALUE_RESPONSE:
            node_id = bytes_to_number(data[1:3])
            slot = byte_to_number(data[3])
            value = float(np.frombuffer(data[4:9], dtype=np.float32))
            print("[ HEAD ] Node {node_id} has responded to the value request on slot {slot} (value is {value})".format(
                node_id=node_id, slot=slot, value=value))
        else:
            print("[ HEAD ] received bytes:", data)

    def loop(self):
        self.running = True
        print("[ HEAD ] starting to loop")
        while self.running:
            msg = self.bus.recv(timeout=100)
            if msg is not None:
                self.parse_packet(msg.data)
        print("[ HEAD ] ending service loop, waiting for {count} clients to disconnect".format(
            count=len(self.connected_clients.keys())))
        while len(self.connected_clients.keys()) != 0:
            msg = self.bus.recv(1)
            if msg is not None:
                self.parse_packet(msg.data)
        print("[ HEAD ] ending loop")
