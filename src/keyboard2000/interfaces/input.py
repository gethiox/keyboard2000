import logging
import multiprocessing
import threading
from queue import Empty
from typing import List

import yaml

from keyboard2000.app.instrument import MIDIDevice, NoteEvent, ControlEvent, Ctrl
from keyboard2000.domain.input import DeviceHandler, KeyboardMap


class LinuxHandler(DeviceHandler):
    def __init__(self, instrument: MIDIDevice, kbd_map: KeyboardMap, device_path: str,
                 signal_queue: threading.Event):
        super().__init__(instrument, kbd_map)
        self.instrument = instrument
        self.kbd_map = kbd_map
        self.device_path = device_path
        self.signal_queue = signal_queue

    def run(self):
        try:
            device = open(self.device_path, 'rb')
        except Exception as err:
            # print('Opening \'{dev}\' device failed ({err}).'.format(
            #     dev=self.device_path,
            #     err=err)
            # )
            return

        try:
            while True:
                if self.signal_queue.is_set():
                    self.instrument.handle_event(
                        ControlEvent(code=Ctrl.panic, code_name='exit panic', pressed_down=True)
                    )
                    self.instrument.handle_event(
                        ControlEvent(code=Ctrl.panic, code_name='exit panic', pressed_down=False)
                    )
                    return

                collected_events = []
                segment = [device.read(8), device.read(8), device.read(8)]

                while b'\x00\x00\x00\x00\x00\x00\x00\x00' not in segment[2] \
                        and b'\x00\x00\x00\x00\x01\x00\x00\x00' not in segment[2]:

                    data = segment[2]

                    if (data[0], data[1], data[3], data[5], data[6], data[7]) == (1, 0, 0, 0, 0, 0):
                        key, status = data[2], data[4]

                        if status in [0, 1]:
                            collected_events.append((key, status))

                    segment = [device.read(8), device.read(8), device.read(8)]

                for key in collected_events:
                    # print('pressed key %s' % key[0])
                    ''
                    self.instrument.handle_event(self.kbd_map.convert_to_event(key))
                    # self.events_queue.put([key['key'], key['status']])
        except Exception as err:
            # print('Reading \'{dev}\' device failed ({err}).'.format(
            #     dev=self.device_path,
            #     err=err)
            # )
            logging.exception('shiet')
            device.close()
            return


class LinuxKeyboardMap(KeyboardMap):
    def __init__(self, map_path: str):
        self.dict_map_raw: dict = yaml.load(open(map_path))

        self.nice_name: str = self.dict_map_raw['nice_name']
        self.device_name: str = self.dict_map_raw['device_name']
        self.auto_connect: List[str] = self.dict_map_raw['auto_connect']
        self.note_map: dict = self.dict_map_raw['notes']
        self.control_map: dict = self.dict_map_raw['control']

        self.merged_map: dict = self.note_map
        self.merged_map.update(self.control_map)

    def convert_to_event(self, key_data):
        if key_data[0] in self.merged_map:
            mapped = self.merged_map[key_data[0]]

            if isinstance(mapped, int):
                return NoteEvent(
                    note=mapped,
                    pressed_down=key_data[1],
                )
            elif isinstance(mapped, str):
                return ControlEvent(
                    code=getattr(Ctrl, mapped),
                    code_name=mapped,
                    pressed_down=key_data[1],
                )


class LinuxEventDevice:
    def __init__(self, name: str, event_name: str, event_path: str):
        self.name = name
        self.event_name = event_name
        self.event_path = event_path
