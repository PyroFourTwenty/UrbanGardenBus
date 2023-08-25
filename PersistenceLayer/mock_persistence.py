from .persistence import Persistence

class MockPersistence (Persistence):
    # This class defines a persistence object that does nothing. 
    # You can pass this to the headstation if you dont want to persist the sent/received CAN-Bus packets

    def __init__(self):
        pass

    def connect_to_db(self):
        pass
    
    def write_to_db(self, data: dict):
        pass