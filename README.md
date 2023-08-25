# UrbanGardenBus

The UrbanGardenBus platform is a network that is designed to be used to control sensors in the Urban Garden of HTW Berlin. Its functionality is built around the data transfer via LoRaWAN to TheThingsNetwork which then forwards these values via an automatically generated payload decoder to OpenSenseMap. 

This system can be used to collect and monitor sensor values on OpenSenseMap. This Headstation is a special node that observes the CAN-Bus network and periodically requests values from registered sensors which are sent by client nodes. The Headstation which can be located distant to the beehives then forwards these packets via LoRaWAN using a RAK811 breakout module. This ensures a better protection of insects in the garden from high intensity radio waves by using a sub-GHz frequency (868 MHz), compared to using Bluetooth or WiFi at 2,4 GHz (or even 5 GHz).

In case of a Headstation failure, the client nodes detect the outage and start sending their sensor values via LoRaWAN. This behaviour will stop once the Headstation reconnects to the network. By falling back to their own LoRaWAN capabilities, users can ensure the monitoring of their node.  

# Hardware requirements
## Client
either
- an Arduino board 
    - with CAN-Bus capabilities
    - (optionally LoRa capabilities, if you want to make sure that your values are sent when the Headstation fails)
or
- a Raspberry Pi (Zero is more than enough)
    - with CAN interface (like this HAT i used: [RS485 CAN HAT by Waveshare](https://www.waveshare.com/wiki/RS485_CAN_HAT))
    - a LoRaWAN capable LoRa module (like the breakout module i used: [] )


## Headstation
- a Raspberry Pi 3
    - with CAN interface (like the one used in the project: )

# Installation
## Client
At the moment two implementations of UGB clients are available: 
- Arduino based client 
    - PlatformIO project available at [UrbanGardenBusClient_LoRa32](https://github.com/PyroFourTwenty/UrbanGardenBusClient_LoRa32)
    - PlatformIO library available at [PlatformIO registry](https://registry.platformio.org/libraries/pyrofourtwenty/UrbanGardenBus)
- Python client
    - available at [UrbanGardenBus/GardenBusClient](https://github.com/PyroFourTwenty/UrbanGardenBus/tree/main/GardenBusClient)


## Headstation
The Headstation is supposed to 