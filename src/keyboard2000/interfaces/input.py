import yaml

from keyboard2000.app.instrument import MIDIDevice, MidiEvent, ControlEvent, Ctrl
from keyboard2000.domain.input import DeviceHandler, KeyboardMap


class LinuxHandler(DeviceHandler):
    def __init__(self, instrument: MIDIDevice, kbd_map: KeyboardMap, device_path: str):
        super().__init__(instrument, kbd_map)
        self.instrument = instrument
        self.kbd_map = kbd_map
        self.device_path = device_path

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
                    self.instrument.handle_event(self.kbd_map.convert_to_event(key))
                    # self.events_queue.put([key['key'], key['status']])
        except Exception as err:
            # print('Reading \'{dev}\' device failed ({err}).'.format(
            #     dev=self.device_path,
            #     err=err)
            # )
            device.close()
            return


class LinuxKeyboardMap(KeyboardMap):
    def __init__(self, map_path: str):
        self.dict_map = yaml.load(open(map_path))

    def convert_to_event(self, key_data):
        if key_data[0] in self.dict_map:
            mapped = self.dict_map[key_data[0]]
            if isinstance(mapped, int):
                return MidiEvent(
                    note=mapped,
                    pressed_down=not key_data[1],
                )
            elif isinstance(mapped, str):
                return ControlEvent(
                    code=getattr(Ctrl, mapped),
                    pressed_down=not key_data[1],
                )


class LinuxEventDevice:
    def __init__(self, name: str, event_name: str, event_path: str):
        self.name = name
        self.event_name = event_name
        self.event_path = event_path
