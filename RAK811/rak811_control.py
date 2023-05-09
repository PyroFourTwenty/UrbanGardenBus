class RAK811():
    ser = None
    def __init__(self, port, baudrate=115200, timeout=3):
        import serial
        self.ser = serial.Serial(port, baudrate, timeout=timeout)
        self.ser.reset_input_buffer()

    def __send_at_command(self, command):
        print('sending command:',command)
        self.ser.write(str.encode(command+'\r\n'))
        if command=='at+join' or 'at+send' in command:
            print('waiting longer for join/send')
            self.print_response(120)
        else:
            self.print_response()

    def print_response(self, time_to_read = 2, return_on_ok = True):
        from time import time
        t = time()
        while time()-t<time_to_read:
            response = self.ser.readline().decode('utf-8').strip()
            print('Response:',response)
            if ('OK' in response or "ERROR" in response) and return_on_ok:
                return

    def send_lorawan_message(self, message, region, app_eui, app_key, dev_eui):
        self.__send_at_command('at+set_config=device:sleep:0')
        self.__send_at_command('at+set_config=device:restart')
        self.__send_at_command('at+version')
        self.__send_at_command('at+set_config=lora:join_mode:0')
        self.__send_at_command('at+set_config=lora:class:0')
        self.__send_at_command('at+set_config=lora:region:'+region)
        self.__send_at_command('at+set_config=lora:app_eui:'+app_eui)
        self.__send_at_command('at+set_config=lora:app_key:'+app_key)
        self.__send_at_command('at+set_config=lora:dev_eui:'+dev_eui)
        self.__send_at_command('at+set_config=lora:dr:'+str(5)) # datarate for long payloads

        self.__send_at_command('at+set_config=device:restart')
        self.__send_at_command('at+join')
        self.__send_at_command('at+send=lora:2:'+message)

