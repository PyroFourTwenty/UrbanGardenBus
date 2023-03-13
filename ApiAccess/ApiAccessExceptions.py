class NoInternetConnection(Exception):
    pass

class InvalidCredentials(Exception):
    def __init__(self):
        super().__init__("OsemAccess: OpenSenseMap login credentials seem to be invalid")

class NotSignedIn(Exception):
    pass