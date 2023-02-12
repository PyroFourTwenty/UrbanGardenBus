import can
from gb_headstation_utils import *
from time import time
from gardenbus_config import *
from GardenBusClient.SupportedSensors import supported_sensors
import numpy as np
from PersistenceLayer.persistence import Persistence
from RAK811.rak811_control import RAK811

class Headstation():
    connected_clients: dict = None
    bus: can.interface.Bus = None
    running: bool = False
    nodes_sensors_calibration_data: dict = None  # has to be set before looping
    tick_rate:float = None
    __last_alive = 0
    node_id = 0 # headstation id should always be 0
    db_access = None

    def __init__(self, bus, db_connection_data: dict, start_looping: bool = True, nodes_sensors_calibration_data={}, tick_rate=30):
        self.bus = bus
        self.db_access = Persistence(db_connection_data)
        self.connected_clients = {}
        self.nodes_sensors_calibration_data = nodes_sensors_calibration_data
        self.tick_rate = float(tick_rate)
        if start_looping:
            self.loop()
    
    def request_value(self, node_id, sensor_slot):
        arbit_id = 99
        value_request_bytes = [
            VALUE_REQUEST,
            *number_to_bytes(node_id, 2),
            *number_to_bytes(sensor_slot)
        ]
        self.db_access.write_to_db({
            "packet_identifier": VALUE_REQUEST,
            "meta":{
                "node_id": node_id,
                "sensor_slot": sensor_slot,
                "packet_direction": "outgoing"
            }
        })
        self.send_packet(arbitration_id=arbit_id, bytes=value_request_bytes)

    def send_packet(self, arbitration_id, bytes: list):
        msg = can.Message(arbitration_id=arbitration_id, data=bytes)
        self.bus.send(msg)
        return msg
    
    def send_entry_packet(self):
        arbit_id = 100
        bytes = [ENTRY_PACKET, *number_to_bytes(self.node_id, 2)]
        self.db_access.write_to_db({
            "packet_identifier": ENTRY_PACKET,
            "meta":{
                "node_id": self.node_id,
                "packet_direction": "outgoing"
            }
        })
        return self.send_packet(arbitration_id=arbit_id, bytes=bytes)

    def send_alive_packet(self):
        print('[ HEAD ] sending ALIVE packet @',time())
        self.__last_alive = time()
        arbit_id = 100
        bytes = [ALIVE_PACKET, *number_to_bytes(self.node_id, 2)]
        self.db_access.write_to_db({
            "packet_identifier": ALIVE_PACKET,
            "meta":{
                "node_id": self.node_id,
                "packet_direction": "outgoing"
            }
        })
        return self.send_packet(arbitration_id=arbit_id, bytes=bytes)

    def handle_node_entry(self, node_id: int):
        data = {
            "packet_identifier": ENTRY_PACKET,
            "meta":{
                "node_id": node_id,
                "packet_direction": "ingoing"
            }
        }
        if node_id in self.connected_clients:
            print('[ HEAD ] Node {node_id} reconnected to the network'.format(
                node_id=node_id))
            data["meta"]["type"] = "reconnect"
            self.connected_clients[node_id]["last_alive"] = time()
        else:
            data["meta"]["type"] = "join"
            self.connected_clients[node_id] = {
                "last_alive": time(),
                "sensors": {},
            }
            print('[ HEAD ] Node {node_id} joined the network'.format(
                node_id=node_id))
        self.db_access.write_to_db(data)
        

    def handle_node_leave(self, node_id):
        self.connected_clients.pop(node_id, None)
        print('[ HEAD ] Node {node_id} left the network'.format(
            node_id=node_id))

    def handle_node_alive(self, node_id):
        data = {
            "packet_identifier": ALIVE_PACKET,
            "meta":{
                "node_id": node_id,
                "packet_direction": "ingoing"
            }
        }
        if node_id in self.connected_clients:
            print('[ HEAD ] Node {node_id} is still connected ({timestamp})'.format(
                node_id=node_id, timestamp=time()))
            data["meta"]["sent_entry"] = True
            self.connected_clients[node_id]["last_alive"] = time()
        else:
            self.connected_clients[node_id] = {
                "last_alive": time(),
                "sensors": {},
            }
            data["meta"]["sent_entry"] = False
            print("[ HEAD ] Node {node} sent alive packet but was not registered via an entry packet".format(
                node=node_id))
        self.db_access.write_to_db(data)

    def handle_sensor_registered(self, node_id: int, sensor_model_id, sensor_slot: int):
        arbit_id = 99
        data = {
            "packet_identifier": SENSOR_REGISTER_PACKET,
            "meta":{
                "node_id": node_id,
                "packet_direction": "ingoing",
                "sensor_model": sensor_model_id,
                "sensor_slot" : sensor_slot
            }
        }
        if node_id in self.connected_clients:
            data["meta"]["sent_entry_packet"]=True
        else:
            print("[ HEAD ] Node {node} tried to register a sensor but has never sent an entry packet".format(
                node=node_id))
            data["meta"]["sent_entry_packet"]=False
        
        bytes = [SENSOR_REGISTER_ACK_PACKET, *number_to_bytes(node_id, 2), *number_to_bytes(
            sensor_model_id, 2), *number_to_bytes(sensor_slot)]
        self.db_access.write_to_db({
            "packet_identifier": SENSOR_REGISTER_ACK_PACKET,
            "meta":{
                "node_id": self.node_id,
                "packet_direction": "outgoing"
            }
        })
        self.send_packet(arbitration_id=arbit_id, bytes=bytes)
        if not node_id in self.connected_clients:
            self.connected_clients[node_id] = {
                "last_alive": time(),
                "sensors": {
                    sensor_slot:{
                        sensor_model_id:sensor_model_id
                    }
                },
            }
        self.connected_clients[node_id]["sensors"][sensor_slot]={
            "sensor_model_id": sensor_model_id
        }
        print("[ HEAD ] Node {node} registered sensor model {sensor_model} on slot {slot}".format(
            node=node_id, sensor_model=sensor_model_id, slot=sensor_slot))
        self.db_access.write_to_db(data)

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

    def handle_sensor_calibration_requested(self, node_id: int, sensor_slot: int, sensor_model_id: int, resend_count: int = 3, response_timeout: float = 3):
        arbit_id = 99
        sensor_model_from_db = get_model_id_of_sensor_of_node(node_id=node_id, sensor_slot=sensor_slot)
        calibration_value = get_calibration_value_for_sensor_of_node(node_id=node_id, sensor_slot=sensor_slot)
        data = {
                "packet_identifier": CALIBRATION_REQUEST,
                "meta":{
                    "node_id": node_id,
                    "packet_direction": "ingoing",
                    "sensor_slot": sensor_slot,
                    "calibration_value_present": True
                }
        }
        if calibration_value is None:
            print('[ HEAD ] Node {node_id} requested calibration value for sensor {sensor_model_id} on slot {sensor_slot} but no calibration value was found'.format(
            node_id=node_id, sensor_model_id=sensor_model_id, sensor_slot=sensor_slot))
            data["meta"]["calibration_value_present"] = False
            self.db_access.write_to_db(data)

            return False
        self.db_access.write_to_db(data)
        print('[ HEAD ] Node {node_id} requested calibration value for sensor {sensor_model_id} on slot {sensor_slot} which is: {calibration_value}'.format(
            node_id=node_id, sensor_model_id=sensor_model_id, sensor_slot=sensor_slot, calibration_value=calibration_value))

        # check if the calibration data corresponds to the request of the node
        if sensor_model_id == sensor_model_from_db:
            bytes = [CALIBRATION_RESPONSE,
                     *number_to_bytes(node_id, 2),
                     *number_to_bytes(sensor_slot),
                     *list(np.float32(calibration_value).tobytes())
                    ]
            for _ in range(resend_count):
                print("[ HEAD ] sending calibration response")
                self.db_access.write_to_db({
                    "packet_identifier": CALIBRATION_RESPONSE,
                    "meta":{
                        "node_id": node_id,
                        "packet_direction": "outgoing",
                        "sensor_slot": sensor_slot,
                        "calibration_value_present": True
                    }
                })
                self.send_packet(arbitration_id=arbit_id, bytes=bytes)
                timestamp = time()
                while(self.running and time()-timestamp < response_timeout):
                    msg = self.bus.recv(timeout=0.01)
                    if msg is not None:
                        if msg.data[0] == CALIBRATION_ACK:
                            received_packet_node_id = bytes_to_number(
                                msg.data[1:3])
                            received_packet_slot = byte_to_number(msg.data[3])
                            self.db_access.write_to_db({
                                "packet_identifier": CALIBRATION_ACK,
                                "meta":{
                                    "node_id": received_packet_node_id,
                                    "packet_direction": "ingoing",
                                    "sensor_slot": received_packet_slot,
                                }
                            })
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
            self.db_access.write_to_db({
                "packet_identifier": VALUE_REQUEST,
                "meta":{
                    "node_id": self.node_id,
                    "packet_direction": "ingoing"
                }
            })
            print("[ HEAD ] A node has requested a value from node {node_id} on slot {slot}".format(
                node_id=node_id, slot=slot))
        elif packet_identifier == VALUE_REQUEST_ACK:
            node_id = bytes_to_number(data[1:3])
            slot = byte_to_number(data[3])
            self.db_access.write_to_db({
                "packet_identifier": VALUE_REQUEST_ACK,
                "meta":{
                    "node_id": node_id,
                    "sensor_slot": slot,
                    "packet_direction": "ingoing"
                }
            })
            print("[ HEAD ] Node {node_id} has acknowledged the request for slot {slot}".format(
                node_id=node_id, slot=slot))
        elif packet_identifier == VALUE_RESPONSE:
            node_id = bytes_to_number(data[1:3])
            slot = byte_to_number(data[3])
            value = float(np.frombuffer(data[4:9], dtype=np.float32))
            self.db_access.write_to_db({
                "packet_identifier": VALUE_RESPONSE,
                "meta":{
                    "node_id": node_id,
                    "sensor_slot": slot,
                    "packet_direction": "ingoing"
                },
                "payload":{
                    "value":value
                }
            })
            if node_id in self.connected_clients:
                if slot in self.connected_clients[node_id]["sensors"]:
                    self.connected_clients[node_id]["sensors"][slot]["last_value"] = value
            print("[ HEAD ] Node {node_id} has responded to the value request on slot {slot} (value is {value})".format(
                node_id=node_id, slot=slot, value=value))

        else:
            print("[ HEAD ] received bytes:", data)
    
    def check_sensor_values_for_station_and_send_lorawand_message(self):
        for node in self.connected_clients:
            all_values_present = True
            values = []
            for sensor in sorted(self.connected_clients[node]["sensors"]):
                if not "last_value" in self.connected_clients[node]["sensors"][sensor] or self.connected_clients[node]["sensors"][sensor]["last_value"] is None:
                    all_values_present=False
                else:
                    values.append(self.connected_clients[node]["sensors"][sensor]["last_value"])
            if all_values_present:
                if len(self.connected_clients[node]["sensors"].keys())!=0:
                    for sensor in sorted(self.connected_clients[node]["sensors"]):
                        self.connected_clients[node]["sensors"][sensor]["last_value"] = None
                    payload=''
                    ttn_data = get_ttn_data_from_db_for_node(node)
                    for value in values:
                        stuff_to_add_to_payload= ''.join([str(hex(b)).replace('0x','') for b in np.float32(value).tobytes()]) 
                        while len(stuff_to_add_to_payload)<8:
                            stuff_to_add_to_payload="0"+stuff_to_add_to_payload
                        print("stuff to add to payload",stuff_to_add_to_payload)
                        payload += stuff_to_add_to_payload
                    
                    if not "last_lorawan_message" in self.connected_clients[node] or time()-self.connected_clients[node]["last_lorawan_message"] >= 120:
                        print("[ HEAD ] all values present for node {node}, sending payload to TTN: {payload}".format(
                            node=node, payload=payload
                        ))
                        print("sending to TTN")
                        RAK811('/dev/ttyUSB0').send_lorawan_message(message=payload,
                            region='EU868',
                            app_eui = ttn_data["app_eui"],
                            app_key = ttn_data["app_key"],
                            dev_eui = ttn_data["dev_eui"]
                        )
                        self.db_access.write_to_db({
                                "packet_identifier": "lorawan",
                                "meta":{
                                    "node_id": node,
                                    "packet_direction": "outgoing"
                                }
                        })
                        self.connected_clients[node]["last_lorawan_message"]=time()
                else:
                    print("station has no sensor ")



    def loop(self):
        self.running = True
        print("[ HEAD ] starting to loop")
        self.send_entry_packet()
        while self.running:
            if time()-self.__last_alive >= self.tick_rate:
                self.send_alive_packet()
                for node in self.connected_clients:
                    for sensor in self.connected_clients[node]["sensors"]:
                        print("[ HEAD ] requesting value from node {node} on slot {slot}".format(node=node, slot=sensor))
                        self.request_value(node, sensor)
            msg = self.bus.recv(timeout=.1)
            if msg is not None:
                self.parse_packet(msg.data)
            self.check_sensor_values_for_station_and_send_lorawand_message()
        print("[ HEAD ] ending service loop, waiting for {count} clients to disconnect".format(
            count=len(self.connected_clients.keys())))
        while len(self.connected_clients.keys()) != 0:
            msg = self.bus.recv(1)
            if msg is not None:
                self.parse_packet(msg.data)
        print("[ HEAD ] ending loop")


