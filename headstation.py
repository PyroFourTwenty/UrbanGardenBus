import can
from gb_headstation_utils import *
from time import time
from gardenbus_config import *
import numpy as np
from PersistenceLayer.persistence import Persistence
from RAK811.rak811_control import RAK811
from threading import Thread
import random


class Headstation():
    connected_clients: dict = None
    partial_transfers: dict = None
    bus: can.interface.Bus = None
    running: bool = False
    tick_rate: float = None
    __last_alive: float = 0
    node_id: int = 0  # headstation id should always be 0
    db_access: Persistence = None
    lorawan_serial: str = None

    def __init__(self, bus: can.interface.Bus, persistence_object: Persistence, start_looping: bool = True, tick_rate=30, lorawan_serial="/dev/ttyUSB0"):
        self.bus = bus
        self.db_access = persistence_object
        self.connected_clients = {}
        self.partial_transfers = {}
        self.tick_rate = float(tick_rate)
        self.lorawan_serial = lorawan_serial
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
            "meta": {
                "node_id": node_id,
                "sensor_slot": sensor_slot,
                "packet_direction": "outgoing"
            }
        })
        self.send_packet(arbitration_id=arbit_id, bytes=value_request_bytes)

    def send_packet(self, arbitration_id, bytes: list):
        msg = can.Message(arbitration_id=arbitration_id, data=bytes)
        try:
            self.bus.send(msg)
        except can.exceptions.CanOperationError:
            self.bus.flush_tx_buffer()
        return msg

    def send_entry_packet(self):
        arbit_id = 99
        bytes = [ENTRY_PACKET, *number_to_bytes(self.node_id, 2)]
        self.db_access.write_to_db({
            "packet_identifier": ENTRY_PACKET,
            "meta": {
                "node_id": self.node_id,
                "packet_direction": "outgoing"
            }
        })
        return self.send_packet(arbitration_id=arbit_id, bytes=bytes)

    def send_alive_packet(self):
        print('[ HEAD ] sending ALIVE packet @', time())
        self.__last_alive = time()
        arbit_id = 100
        bytes = [ALIVE_PACKET, *number_to_bytes(self.node_id, 2)]
        self.db_access.write_to_db({
            "packet_identifier": ALIVE_PACKET,
            "meta": {
                "node_id": self.node_id,
                "packet_direction": "outgoing"
            }
        })
        return self.send_packet(arbitration_id=arbit_id, bytes=bytes)

    def handle_node_entry(self, node_id: int):
        data = {
            "packet_identifier": ENTRY_PACKET,
            "meta": {
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

    def handle_node_leave(self, node_id: int):
        self.connected_clients.pop(node_id, None)
        print('[ HEAD ] Node {node_id} left the network'.format(
            node_id=node_id))

    def handle_node_alive(self, node_id: int):
        data = {
            "packet_identifier": ALIVE_PACKET,
            "meta": {
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

    def handle_sensor_registered(self, node_id: int, sensor_model_id: int, sensor_slot: int):
        arbit_id = 99
        data = {
            "packet_identifier": SENSOR_REGISTER_PACKET,
            "meta": {
                "node_id": node_id,
                "packet_direction": "ingoing",
                "sensor_model": sensor_model_id,
                "sensor_slot": sensor_slot
            }
        }
        if node_id in self.connected_clients:
            data["meta"]["sent_entry_packet"] = True
        else:
            print("[ HEAD ] Node {node} tried to register a sensor but has never sent an entry packet".format(
                node=node_id))
            data["meta"]["sent_entry_packet"] = False

        bytes = [SENSOR_REGISTER_ACK_PACKET, *number_to_bytes(node_id, 2), *number_to_bytes(
            sensor_model_id, 2), *number_to_bytes(sensor_slot)]
        self.db_access.write_to_db({
            "packet_identifier": SENSOR_REGISTER_ACK_PACKET,
            "meta": {
                "node_id": self.node_id,
                "packet_direction": "outgoing"
            }
        })
        self.send_packet(arbitration_id=arbit_id, bytes=bytes)
        if not node_id in self.connected_clients:
            self.connected_clients[node_id] = {
                "last_alive": time(),
                "sensors": {
                    sensor_slot: {
                        sensor_model_id: sensor_model_id
                    }
                },
            }
        self.connected_clients[node_id]["sensors"][sensor_slot] = {
            "sensor_model_id": sensor_model_id
        }
        print("[ HEAD ] Node {node} registered sensor model {sensor_model} on slot {slot}".format(
            node=node_id, sensor_model=sensor_model_id, slot=sensor_slot))
        self.db_access.write_to_db(data)

    def handle_sensor_unregistered(self, node_id: int, sensor_slot: int):
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
        sensor_model_from_db = get_model_id_of_sensor_of_node(
            node_id=node_id, sensor_slot=sensor_slot)
        calibration_value = get_calibration_value_for_sensor_of_node(
            node_id=node_id, sensor_slot=sensor_slot)
        data = {
            "packet_identifier": CALIBRATION_REQUEST,
            "meta": {
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
                    "meta": {
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
                                "meta": {
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

    def handle_partial_transfer_id_request(self, node_id, length):
        transfer_id = random.randrange(0,256)
        if len(self.partial_transfers.keys())<256: # if partial transfers are not at capacity
            while transfer_id in self.partial_transfers:
                transfer_id = random.randrange(0,256)
            self.partial_transfers[transfer_id] = {
                "node_id": node_id,
                "length": length,
                "content": [],
            }
            partial_transfer_id_response_bytes = [
                PARTIAL_TRANSFER_ID_RESPONSE,
                *number_to_bytes(node_id, 2),
                *number_to_bytes(transfer_id),
            ]
            self.send_packet(
                bytes=partial_transfer_id_response_bytes, arbitration_id=99)
            self.db_access.write_to_db({
                "packet_identifier": PARTIAL_TRANSFER_ID_RESPONSE,
                "meta": {
                    "node_id": node_id,
                    "packet_direction": "outgoing",
                    "length": length,
                    "transfer_id": transfer_id
                }
            })
        else:
            # partial transfer are at capacity, maybe let the client know that?
            pass

    def handle_partial_transfer(self, transfer_id, part_identifier, content):
        if not transfer_id in self.partial_transfers:
            return
        count_of_bytes_per_part = 3
        current_length = len(
            self.partial_transfers[transfer_id]["content"])/count_of_bytes_per_part
        if part_identifier == 0:
            print("[ HEAD ] transfer {transfer_id} started".format(transfer_id=transfer_id))
            self.partial_transfers[transfer_id]["start_timestamp"] = time()
        if part_identifier == current_length:

            for byte in content:
                self.partial_transfers[transfer_id]["content"].append(
                    byte)  # append tuple
            percentage = current_length/self.partial_transfers[transfer_id]["length"]*100
            percentage = round(percentage,2)
            time_difference = time()-self.partial_transfers[transfer_id]["start_timestamp"]
            speed = 0
            remaining_seconds = "a few"
            if time_difference!=0 and percentage!=0:
                speed = len(self.partial_transfers[transfer_id]["content"])/(time()-self.partial_transfers[transfer_id]["start_timestamp"])
                remaining_percentage = 100.0-percentage
                factor = remaining_percentage/percentage
                remaining_seconds = round(time_difference * factor,2)
            speed = round(speed, 1)
            print("[ HEAD ]\t{percentage} % \t\t @ {speed} b/s\t current_length={current} \t length={length} \t remaining: {remaining} s".format(percentage=percentage, speed=speed,
                                                                                                                 current=current_length,length=self.partial_transfers[transfer_id]["length"], remaining=remaining_seconds))

            partial_transfer_ack_bytes = [
                PARTIAL_TRANSFER_ACK,
                *number_to_bytes(transfer_id),
                *number_to_bytes(part_identifier, 3)
            ]
            self.send_packet(bytes=partial_transfer_ack_bytes,
                            arbitration_id=99)
            node_id = self.partial_transfers[transfer_id]["node_id"]
            self.db_access.write_to_db({
                "packet_identifier": PARTIAL_TRANSFER_ACK,
                "meta": {
                    "node_id": node_id,
                    "packet_direction": "outgoing",
                    "transfer_id": transfer_id,
                    "part_identifier": part_identifier
                }
            })
        else:
            print("[ HEAD ] part-id {part_id} doesnt equal content len {length}".format(
                part_id=part_identifier, length=current_length))

    def handle_partial_transfer_finished(self, transfer_id):
        partial_transfer_ack_bytes = [
            PARTIAL_TRANSFER_FINISHED_ACK,
            transfer_id
        ]
        node_id = self.partial_transfers[transfer_id]["node_id"]

        self.send_packet(bytes=partial_transfer_ack_bytes, arbitration_id=99)
        self.db_access.write_to_db({
                "packet_identifier": PARTIAL_TRANSFER_FINISHED_ACK,
                "meta": {
                    "node_id": node_id,
                    "packet_direction": "outgoing",
                    "transfer_id": transfer_id
                }
        })
        content = self.partial_transfers[transfer_id]["content"]
        file_content=""
        for int in content:
            file_content+=chr(int)
        
        filename = self.partial_transfers[transfer_id]["meta"]["filename"]
        filename="im_copied_btw_"+filename
        paste_me = open(filename,'wb')
        paste_me.write(bytes(content))
        self.partial_transfers[transfer_id]["finished_timestamp"] = time()
        duration = self.partial_transfers[transfer_id]["finished_timestamp"]-self.partial_transfers[transfer_id]["start_timestamp"]
        duration = round(duration,2)
        speed = round(len(content)/duration, 2)
        print("[ HEAD ] transfer {transfer_id} completed in {duration}s ({speed} b/s)".format(transfer_id=transfer_id, duration=duration, speed=speed))
        self.partial_transfers.pop(transfer_id)

    def handle_partial_transfer_name_init(self, transfer_id, name_length):
        self.partial_transfers[transfer_id]["meta"]={
            "length" : name_length,
            "filename": "",
            "filename_transfer_finished" : False
        }
        partial_transfer_name_init_ack_bytes = [
            PARTIAL_TRANSFER_NAME_INIT_ACK,
            transfer_id,
            name_length
        ]
        self.send_packet(arbitration_id=99, bytes=partial_transfer_name_init_ack_bytes)
        node_id = self.partial_transfers[transfer_id]["node_id"]
        self.db_access.write_to_db({
            "packet_identifier": PARTIAL_TRANSFER_NAME_INIT_ACK,
            "meta": {
                "node_id": node_id,
                "packet_direction": "outgoing",
                "transfer_id": transfer_id
            }
        })

    def handle_partial_transfer_name_part(self, transfer_id, partial_file_name):
        for byte in partial_file_name:
            self.partial_transfers[transfer_id]["meta"]["filename"]+=chr(byte)
        filename=self.partial_transfers[transfer_id]["meta"]["filename"]
        current_length=len(filename)        
        partial_name_part_ack_bytes = [
            PARTIAL_TRANSFER_NAME_PART_ACK,
            transfer_id,
            *partial_file_name
        ]
        
        self.send_packet(arbitration_id=100, bytes=partial_name_part_ack_bytes)
        node_id = self.partial_transfers[transfer_id]["node_id"]

        self.db_access.write_to_db({
            "packet_identifier": PARTIAL_TRANSFER_NAME_PART_ACK,
            "meta": {
                "node_id": node_id,
                "packet_direction": "outgoing",
                "transfer_id": transfer_id
            }
        })

        if current_length == self.partial_transfers[transfer_id]["meta"]["length"]:
            self.partial_transfers[transfer_id]["meta"]["filename_transfer_finished"]=True
            print("[ HEAD ] Filename transfer finished for transfer {transfer_id} ({filename}) ".format(filename=filename, transfer_id=transfer_id))




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
            sensor_slot = byte_to_number(data[5])
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
                "meta": {
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
                "meta": {
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
                "meta": {
                    "node_id": node_id,
                    "sensor_slot": slot,
                    "packet_direction": "ingoing"
                },
                "payload": {
                    "value": value
                }
            })
            if node_id in self.connected_clients:
                if slot in self.connected_clients[node_id]["sensors"]:
                    self.connected_clients[node_id]["sensors"][slot]["last_value"] = value
            print("[ HEAD ] Node {node_id} has responded to the value request on slot {slot} (value is {value})".format(
                node_id=node_id, slot=slot, value=value))
        
        elif packet_identifier == PARTIAL_TRANSFER_ID_REQUEST:
            node_id = bytes_to_number(data[1:3])
            length = bytes_to_number(data[3:6])
            print("[ HEAD ] partial transfer request from node {node_id} with length {length}".format(
                node_id=node_id, length=length))
            self.db_access.write_to_db({
                "packet_identifier": PARTIAL_TRANSFER_ID_REQUEST,
                "meta": {
                    "node_id": node_id,
                    "packet_direction": "ingoing",
                    "length": length
                }
            })
            self.handle_partial_transfer_id_request(node_id, length)
        
        elif packet_identifier == PARTIAL_TRANSFER_NAME_INIT:
            transfer_id = data[1]
            name_length = data[2]
            print("[ HEAD ] partial transfer name init for tansfer id {transfer_id} with length {length}".format(
                transfer_id=transfer_id, length=name_length))
            node_id = self.partial_transfers[transfer_id]["node_id"]
            self.db_access.write_to_db({
                "packet_identifier": PARTIAL_TRANSFER_NAME_INIT,
                "meta": {
                    "node_id": node_id,
                    "packet_direction": "ingoing",
                    "name_length": name_length,
                    "transfer_id": transfer_id
                }
            })
            self.handle_partial_transfer_name_init(transfer_id, name_length)
        
        elif packet_identifier == PARTIAL_TRANSFER_NAME_PART:
            transfer_id = data[1]
            partial_file_name = data[3:8]
            self.db_access.write_to_db({
                "packet_identifier": PARTIAL_TRANSFER_NAME_PART,
                "meta": {
                    "node_id": node_id,
                    "packet_direction": "ingoing",
                    "transfer_id": transfer_id
                }
            })
            self.handle_partial_transfer_name_part(transfer_id, partial_file_name)


        elif packet_identifier == PARTIAL_TRANSFER:
            transfer_id = data[1]
            part_identifier = bytes_to_number(data[2:5])
            content = data[5:9]
            node_id = self.partial_transfers[transfer_id]["node_id"]
            self.db_access.write_to_db({
                "packet_identifier": PARTIAL_TRANSFER,
                "meta": {
                    "node_id": node_id,
                    "packet_direction": "ingoing",
                    "transfer_id": transfer_id,
                    "part_identifier": part_identifier
                }
            })
            self.handle_partial_transfer(transfer_id, part_identifier, content)
        elif packet_identifier == PARTIAL_TRANSFER_FINISHED:
            transfer_id = data[1]
            node_id = self.partial_transfers[transfer_id]["node_id"]
            self.handle_partial_transfer_finished(transfer_id)
            self.db_access.write_to_db({
                "packet_identifier": PARTIAL_TRANSFER_FINISHED,
                "meta": {
                    "node_id": node_id,
                    "packet_direction": "ingoing",
                    "transfer_id": transfer_id,
                }
            })

        else:
            print("[ HEAD ] received bytes:", data)

    def check_sensor_values_for_station_and_send_lorawan_message(self):
        while self.running:
            copied_clients = self.connected_clients.copy()
            timeout_per_node = len(copied_clients.keys())*120
            for node in copied_clients:
                all_values_present = True
                values = []
                for sensor in sorted(copied_clients[node]["sensors"]):
                    if not "last_value" in self.connected_clients[node]["sensors"][sensor] or self.connected_clients[node]["sensors"][sensor]["last_value"] is None:
                        all_values_present = False
                    else:
                        values.append(
                            self.connected_clients[node]["sensors"][sensor]["last_value"])
                if all_values_present:
                    if len(self.connected_clients[node]["sensors"].keys()) != 0:
                        for sensor in sorted(self.connected_clients[node]["sensors"]):
                            self.connected_clients[node]["sensors"][sensor]["last_value"] = None
                        payload = ''
                        ttn_data = get_ttn_data_from_db_for_node(node)
                        for value in values:
                            stuff_to_add_to_payload = ''.join(
                                [str(hex(b)).replace('0x', '') for b in np.float32(value).tobytes()])
                            while len(stuff_to_add_to_payload) < 8:
                                stuff_to_add_to_payload = "0"+stuff_to_add_to_payload
                            payload += stuff_to_add_to_payload

                        if not "last_lorawan_message" in self.connected_clients[node] or time()-self.connected_clients[node]["last_lorawan_message"] >= timeout_per_node:
                            if ttn_data is None:
                                print("[ HEAD ] Node {node} is not correctly registered, so no TTN data was found".format(
                                    node=node))
                                self.connected_clients[node]["last_lorawan_message"] = time(
                                )
                            else:
                                print("[ HEAD ] All values present for node {node}, sending payload to TTN: {payload}".format(
                                    node=node, payload=payload
                                ))
                                print("sending to TTN")
                                RAK811(self.lorawan_serial).send_lorawan_message(message=payload,
                                                                                 region='EU868',
                                                                                 app_eui=ttn_data["app_eui"],
                                                                                 app_key=ttn_data["app_key"],
                                                                                 dev_eui=ttn_data["dev_eui"]
                                                                                 )
                                self.db_access.write_to_db({
                                    "packet_identifier": "lorawan",
                                    "meta": {
                                        "node_id": node,
                                        "packet_direction": "outgoing"
                                    }
                                })
                                self.connected_clients[node]["last_lorawan_message"] = time(
                                )
                                self.send_alive_packet()

    def loop(self):
        self.running = True
        value_checker = Thread(
            target=self.check_sensor_values_for_station_and_send_lorawan_message, args=(), daemon=True)
        print("[ HEAD ] starting value checker")
        value_checker.start()
        print("[ HEAD ] starting to loop")
        self.send_entry_packet()
        while self.running:
            if time()-self.__last_alive >= self.tick_rate:
                self.send_alive_packet()
                for node in self.connected_clients:
                    for sensor in self.connected_clients[node]["sensors"]:
                        print("[ HEAD ] requesting value from node {node} on slot {slot}".format(
                            node=node, slot=sensor))
                        self.request_value(node, sensor)
            msg = self.bus.recv(timeout=.1)
            if msg is not None:
                self.parse_packet(msg.data)
        print("[ HEAD ] ending service loop, waiting for {count} clients to disconnect".format(
            count=len(self.connected_clients.keys())))
        while len(self.connected_clients.keys()) != 0:
            msg = self.bus.recv(1)
            if msg is not None:
                self.parse_packet(msg.data)
        print("[ HEAD ] ending loop")
