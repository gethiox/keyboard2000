from abc import abstractmethod
from typing import Union

from keyboard2000.app.instrument import MIDIDevice, NoteEvent, ControlEvent


class KeyboardMap:
    """keyboard map handler, not very formed right now, object that is able to convert specified keyboard raw input
    onto prepared output as MidiEvent or ControlEvent objects (midi signals or device control signals like midi-channel
    change). Also object should be able to read mapping from yaml configuration file
    TODO: prepare tool for convenient key mapping into file"""

    @abstractmethod
    def convert_to_event(self, key_data) -> Union[NoteEvent, ControlEvent]:
        pass


class DeviceHandler:
    """Device Handler should handle keyboard device input as separated, non-blocking thread.
    Also it means that one keyboard device represent one instrument device.
    The main task of this class is to read device input data, convert to specified Events through KeyboardMap
    and put prepared midi events directly into attached instrument object under .handle_event method"""

    @abstractmethod
    def __init__(self, instrument: MIDIDevice, kbd_map: KeyboardMap):
        self.instrument = instrument
        self.kbd_map = kbd_map

    @abstractmethod
    def run(self):
        raise NotImplemented
