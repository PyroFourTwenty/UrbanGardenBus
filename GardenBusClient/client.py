import can
import sys
import math
from GardenBusClient.sensor import GardenBusSensor
from GardenBusClient.actor import GardenBusActor
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
    actors = {}
    tick_rate: float = None  # defines the rate at that the node sends alive packets
    # as well as other periodically timed packets (in seconds)
    running = False
    __last_alive = 0
    last_headstation_alive = None
    partial_transfer = None 

    ttn_dev_eui = None
    ttn_dev_id = None
    ttn_app_key = None
    ttn_join_eui = None

    lorawan_serial = "/dev/ttyS0"

    def __init__(self, bus: can.interface.Bus, node_id: int, ttn_dev_eui:str = "", ttn_dev_id:str="", ttn_app_key:str="", ttn_join_eui:str="",tick_rate: float = 30, start_looping: bool = True, print_tick_rate=True, lorawan_serial='"/dev/ttyS0"', forward_data_to_ttn: bool = True):
        self.bus = bus
        self.node_id = node_id
        self.tick_rate = tick_rate
        
        self.ttn_dev_eui = ttn_dev_eui 
        self.ttn_dev_id = ttn_dev_id 
        self.ttn_app_key = ttn_app_key 
        self.ttn_join_eui = ttn_join_eui
        self.lorawan_serial = lorawan_serial
        self.reset_partial_transfer()
        self.forward_data_to_ttn = forward_data_to_ttn
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

    def send_register_actor_packet(self, actor: GardenBusActor, resend_count: int = 6, response_timeout: float = 30):
        arbit_id = 100
        self.actors[actor.actor_slot] = actor
        bytes = [
            config.ACTOR_REGISTER,
            *utils.number_to_bytes(self.node_id, 2),
            *utils.number_to_bytes(actor.actor_slot),
        ]
        for _ in range(resend_count):
            self.send_packet(arbitration_id=arbit_id, bytes=bytes)
            timestamp = time()
            while (self.running and time()-timestamp < response_timeout):
                msg = self.bus.recv(timeout=0.01)
                if msg is not None:
                    targeted_node_id_of_packet = utils.bytes_to_number(
                        msg.data[1:3])
                    # check if the received packet is from the headstation that registered the actor
                    if msg.data[0] == config.ACTOR_REGISTER_ACK and targeted_node_id_of_packet == self.node_id and msg.data[3]==actor.actor_slot:
                        print("[ {node} ] actor registration successful: {actor}".format(
                            node=self.node_id, actor=actor.actor_slot))
                        return True  # actor was successfully registered at the headstation
                            
        print("[ {node} ] giving up actor registration slot {slot}".format(
            node=self.node_id, slot=actor.actor_slot))
        self.actors[actor.actor_slot] = actor # save the actor
        return False  # return False if the client was not able to register the actor


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
                        
                        print("[ {node} ] registration successful: {sensor}".format(
                            node=self.node_id, sensor=sensor.sensor_model_id))
                        return True  # sensor was successfully registered at the headstation
                            
        print("[ {node} ] giving up sensor registration of model {model} on slot {slot}".format(
            node=self.node_id, model=sensor.sensor_model_id, slot=sensor_slot))
        self.sensors[sensor_slot] = sensor  # save the sensor
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

    def send_actor_set_packet(self,node_id, actor_slot, value, wait_for_ack=True, ack_timeout=10):
        arbit_id=100
        actor_set_bytes = [
            config.ACTOR_SET,
            *utils.number_to_bytes(node_id, 2),
            *utils.number_to_bytes(actor_slot),
            *list(np.float32(value).tobytes())
        ]
        self.send_packet(arbitration_id=arbit_id, bytes=actor_set_bytes)
        if wait_for_ack:
            timestamp = time()
            while(time()-timestamp < ack_timeout):
                msg = self.bus.recv(timeout=0.01)
                if msg is not None:
                    if msg.data[0]==config.ACTOR_SET_ACK:
                        node_id_from_packet = utils.bytes_to_number(
                            msg.data[1:3])
                        slot_from_packet= utils.byte_to_number(msg.data[3])
                        value_bytes = msg.data[4:9]
                        set_value_from_packet = float(
                            np.frombuffer(value_bytes, dtype=np.float32))
                        if node_id_from_packet==node_id and set_value_from_packet==np.float32(value) and slot_from_packet==actor_slot:
                            print("[ {node_id} ] Node {target} set actor on slot {slot} to value {value}".format(
                                node_id=self.node_id,
                                target=node_id_from_packet,
                                slot=actor_slot,
                                value=value
                                )
                            )
                            return True
            return False
        else:
            return True

    def handle_value_request(self, sensor_slot):
        arbit_id = 100
        # send value request ACK packet
        print("[ {node_id} ] got value request for slot {sensor_slot}".format(
            node_id=self.node_id, sensor_slot=sensor_slot,
        ))
        print("[ {node_id} ] sending value request ack for slot {sensor_slot}".format(
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
        print("[ {node_id} ] sending value reponse for slot {sensor_slot} (value is {value})".format(
            node_id=self.node_id, sensor_slot=sensor_slot,value=sensor_value
        ))

        value_response_bytes = [
            config.VALUE_RESPONSE,
            *utils.number_to_bytes(self.node_id, 2),
            *utils.number_to_bytes(sensor_slot),
            *list(np.float32(sensor_value).tobytes())
        ]
        # send value response packet
        self.send_packet(arbitration_id=arbit_id, bytes=value_response_bytes)

    def handle_actor_set_packet(self, actor_slot, actor_value):
        if actor_slot in self.actors:
            print("[ {node_id} ] got value request for slot {actor_slot}".format(
                node_id=self.node_id, actor_slot=actor_slot,
            ))
            arbit_id = 100
            self.actors[actor_slot].set_value(actor_value)
            actor_set_ack_bytes = [
                config.ACTOR_SET_ACK,
                *utils.number_to_bytes(self.node_id, 2),
                *utils.number_to_bytes(actor_slot),
                *list(np.float32(actor_value).tobytes())
            ]
            print("[ {node_id} ] sending actor set ack for slot {actor_slot}".format(
                node_id=self.node_id, actor_slot=actor_slot,
            ))
            # send value response packet
            self.send_packet(arbitration_id=arbit_id, bytes=actor_set_ack_bytes)

    def register_sensor(self, sensor: GardenBusSensor, slot, resend_count: int = 6, response_timeout: float = 30):
        return self.send_register_sensor_packet(sensor=sensor, sensor_slot=slot, resend_count=resend_count, response_timeout=response_timeout)

    def unregister_sensor(self, slot):
        return self.send_unregister_sensor_packet(slot)
    
    def register_actor(self, actor: GardenBusActor):
        return self.send_register_actor_packet(actor)


    def join_network(self):
        return self.send_entry_packet()

    def leave_network(self):
        return self.send_leave_packet()

    def calibrate_sensor(self, sensor: GardenBusSensor, sensor_slot, resend_count= 6, response_timeout= 30):
        return self.send_calibration_request_packet(sensor_model_id=sensor.sensor_model_id, sensor_slot=sensor_slot, resend_count=resend_count, response_timeout=response_timeout)

    def set_actor_of_node(self, node_id, actor_slot, value, wait_for_ack=True, ack_timeout=10):
        return self.send_actor_set_packet(node_id=node_id, actor_slot=actor_slot, value=value, wait_for_ack=True, ack_timeout=ack_timeout)

    def send_lorawan_message(self):
        import numpy as np
        rak811 = RAK811(self.lorawan_serial)
        payload = ''
        for sensor_slot in sorted(self.sensors):
            sensor_value = self.sensors[sensor_slot].get_value()
            partial_payload = ''.join([str(hex(b)).replace('0x','') for b in np.float32(sensor_value).tobytes()])
            while len(partial_payload)<8:
                partial_payload="0"+partial_payload
            payload += partial_payload
        rak811.send_lorawan_message(message=payload,
            region='EU868',
            app_eui=self.ttn_join_eui, 
            app_key=self.ttn_app_key,
            dev_eui=self.ttn_dev_eui
        )
        self.__last_alive=time()

    def re_register_sensors(self):
        print("[ {node} ] Re-registering all sensors because headstation reconnected".format(node=self.node_id))
        copied = []
        for slot in self.sensors:
            copied.append((slot, self.sensors[slot]))
        for copied_tuple in copied:
            success = self.register_sensor(copied_tuple[1],copied_tuple[0])
            if success and copied_tuple[1].calibration_required:
                self.calibrate_sensor(copied_tuple[1], copied_tuple[0])

    def request_transfer_id(self, filename):
        data = []
        with open(filename, "rb") as f:
            while(byte:=f.read(1)):
                data.append(int.from_bytes(byte,"big"))
        count_of_bytes_per_part = 3
        length = math.ceil(len(data)/count_of_bytes_per_part)

        value_request_bytes = [
            config.PARTIAL_TRANSFER_ID_REQUEST, # packet identifier 
            *utils.number_to_bytes(self.node_id,2), # node id
            *utils.number_to_bytes(length, 3) #length
        ]
        self.partial_transfer["data"] = data
        self.partial_transfer["filename"] = filename
        self.partial_transfer["length"] = length


        self.send_packet(arbitration_id=99, bytes=value_request_bytes)
    
    def reset_partial_transfer(self):
        self.partial_transfer = {
            "transfer_id": None,
            "data": None,
            "filename": None,
            "length": None,
            "ready_for_tx": False,
            "last_index" : None,
            "finished": False,
            "last_part_timestamp": None
        }

    def handle_transfer_id(self, node_id, transfer_id):
        if node_id==self.node_id:
            self.partial_transfer["transfer_id"] = transfer_id
            print("[ {node_id} ] received transfer id {transfer_id} for data transfer ({filename}) ".format(
                        node_id=self.node_id,  transfer_id=transfer_id, filename=self.partial_transfer["filename"]))


    def send_partial_transfer_name_init(self):
        name_init_bytes =[
            config.PARTIAL_TRANSFER_NAME_INIT,
            self.partial_transfer["transfer_id"],
            len(self.partial_transfer["filename"])
        ]
        self.send_packet(arbitration_id=99,bytes=name_init_bytes)

    def handle_name_init_ack(self, transfer_id):
        if transfer_id == self.partial_transfer["transfer_id"]:
            name_bytes_per_part = 3
            filename = self.partial_transfer["filename"]
            pair_count = math.ceil(len(filename)/name_bytes_per_part)

            for x in range(pair_count):
                index_low = x*name_bytes_per_part
                index_high = x*name_bytes_per_part+name_bytes_per_part
                partial_name_part_bytes = [
                    config.PARTIAL_TRANSFER_NAME_PART,
                    transfer_id,
                    x,
                    *str.encode(filename[index_low:index_high])
                ]
                self.send_packet(arbitration_id=100, bytes=partial_name_part_bytes)
            self.partial_transfer["ready_for_tx"] = True

    def send_partial_data_packet(self):
        count_of_bytes_per_part = 3
        if self.partial_transfer["ready_for_tx"] and not self.partial_transfer["finished"]:
            if self.partial_transfer["last_index"] is None:
                self.partial_transfer["last_index"] = 0
            index_low = self.partial_transfer["last_index"]*count_of_bytes_per_part
            index_high = index_low+count_of_bytes_per_part
            part_identifier = self.partial_transfer["last_index"]
            
            partial_transfer_bytes = [
                config.PARTIAL_TRANSFER,
                self.partial_transfer["transfer_id"],
                *utils.number_to_bytes(self.partial_transfer["last_index"],3),
                *self.partial_transfer["data"][index_low:index_high]
            ]
            self.send_packet(arbitration_id=100, bytes=partial_transfer_bytes)
            #print("[{node}] [{transfer}] sending data part {part}".format(node=self.node_id, transfer=self.partial_transfer["transfer_id"], part=part_identifier))
            self.partial_transfer["last_part_timestamp"] = time()
            if self.partial_transfer["last_index"] == self.partial_transfer["length"]:
                self.partial_transfer["finished"] = True

    def handle_partial_transfer_ack(self, part_identifier):
        if part_identifier == self.partial_transfer["last_index"]:
            self.partial_transfer["last_index"]+=1
            #print("[{node}] next data part is  {part}".format(node=self.node_id, part=self.partial_transfer["last_index"]))
            #print("Recipient confirmed part number {part}".format(part=part_identifier))



    def send_part_transfer_finished_packet(self):
        partial_transfer_finished_bytes = [
            config.PARTIAL_TRANSFER_FINISHED,
            self.partial_transfer["transfer_id"]
        ]
        self.send_packet(arbitration_id=100, bytes=partial_transfer_finished_bytes)


    def handle_ongoing_partial_tranfer(self):
        if self.partial_transfer["transfer_id"] is not None:
            if not self.partial_transfer["ready_for_tx"]: # name transfer not finished
                self.send_partial_transfer_name_init()
            else:
                if not self.partial_transfer["finished"]:
                    if self.partial_transfer["last_part_timestamp"] is not None:
                        if time()-self.partial_transfer["last_part_timestamp"]>0.07:
                            self.send_partial_data_packet()
                    else: 
                        self.send_partial_data_packet()
                else:
                    self.send_part_transfer_finished_packet()
                    self.reset_partial_transfer()

    
    def loop(self):
        #sleep(self.tick_rate)
        self.join_network()
        headstation_timeout_detected = False
        while self.running:
            if time()-self.__last_alive >= self.tick_rate:  # if the last alive-packet is more than the tickrate ago
                if not headstation_timeout_detected:
                    self.send_alive_packet()
                else:

                    self.send_lorawan_message()
            

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
                            headstation_timeout_detected=False
                            self.send_leave_packet()
                            self.send_entry_packet()
                            self.re_register_sensors()
                        else:
                            print("[ {node_id} ] headstation is still connected".format(node_id=self.node_id))

                        self.last_headstation_alive = time()
                elif msg.data[0] == config.PARTIAL_TRANSFER_ID_RESPONSE:
                    node_id = utils.bytes_to_number(msg.data[1:3])
                    transfer_id = msg.data[3]

                    self.handle_transfer_id(node_id=node_id, transfer_id=transfer_id)
                elif msg.data[0] == config.PARTIAL_TRANSFER_NAME_INIT_ACK:
                    transfer_id=msg.data[1]
                    self.handle_name_init_ack(transfer_id=transfer_id)
                elif msg.data[0] == config.PARTIAL_TRANSFER_ACK:
                    transfer_id=msg.data[1]
                    if transfer_id == self.partial_transfer["transfer_id"]:
                        part_identifier = utils.bytes_to_number(msg.data[2:5])
                        self.handle_partial_transfer_ack(part_identifier)
                
                elif msg.data[0] == config.ACTOR_SET and utils.bytes_to_number(msg.data[1:3]) == self.node_id:
                    actor_slot= msg.data[3]
                    actor_value_bytes = msg.data[4:9]
                    actor_value = float(
                            np.frombuffer(actor_value_bytes, dtype=np.float32))
                    self.handle_actor_set_packet(actor_slot, actor_value)

                #print(str(self.node_id), "received a packet:", msg.data[0])
            if time()-self.last_headstation_alive >= config.HEADSTATION_TICK_RATE and not headstation_timeout_detected:  # if the last alive-packet is more than the tickrate ago
                headstation_timeout_detected = True
                print("[ {node_id} ] Headstation timeout detected!".format(node_id=self.node_id))
            
            self.handle_ongoing_partial_tranfer()

        print("[ {node_id} ] Goodbye".format(node_id=self.node_id))
        self.send_leave_packet()
        self.running = False