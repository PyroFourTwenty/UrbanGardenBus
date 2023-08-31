class GardenBusActor():
    actor_slot = None
    set_value_function = None

    def __init__(self, actor_slot: int, set_value_function):
        self.actor_slot=actor_slot
        self.set_value_function=set_value_function

    def set_value(self, actor_value):
        return self.set_value_function(actor_value)