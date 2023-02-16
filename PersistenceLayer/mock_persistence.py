from .persistence import Persistence

class MockPersistence (Persistence):

    def __init__(self):
        pass

    def connect_to_db(self):
        pass
    
    def write_to_db(self, data: dict):
        pass