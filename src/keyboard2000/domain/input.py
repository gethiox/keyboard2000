from abc import abstractmethod

from keyboard2000.app.instrument import MIDIDevice


class DeviceHandler:
    """Device Handler should handle keyboard device input as separated, non-blocking thread.
    Also it means that one keyboard device represent one instrument device.
    The main task of this class is to read device input data, convert to specified midi signals
    and put prepared midi events right on to midi_socket queue"""

    @abstractmethod
    def __init__(self, instrument: MIDIDevice, kbd_map: KeyboardMap):
        self.instrument = instrument
        self.kbd_map = kbd_map

    @abstractmethod
    def run(self):
        raise NotImplemented


class KeyboardMap:
    @abstractmethod
    def convert_to_event(self, key_data):
        pass
