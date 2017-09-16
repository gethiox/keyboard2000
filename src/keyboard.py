#!/usr/bin/env python3
import datetime
import re
import time
from multiprocessing import Queue
from queue import Empty
from threading import Thread

import jack

from keyboard2000.app.instrument import MIDIDevice
from keyboard2000.interfaces.input import LinuxHandler, LinuxKeyboardMap


def get_timestamp():
    now = datetime.datetime.now()
    compiled_time = now.strftime('%H:%M:%S') + now.strftime('.%f')[:4]
    return compiled_time


def get_devices():
    re_name = re.compile(r'Name="(.*)"')
    re_event = re.compile(r'event[0-9]+')

    with open('/proc/bus/input/devices') as state_file:
        file_data = ''
        for line in state_file:
            file_data += line

    all_devices = file_data.split('\n\n')

    founded_devices = []
    for dev in all_devices:
        if 'EV=120013' in dev:
            dev_name = re_name.search(dev).group(1)
            dev_event = re_event.search(dev).group(0)
            founded_devices.append({'name': dev_name,
                                    'event': dev_event})

    return founded_devices


class DevicesWatcher:
    def __init__(self, midi_sockets, events_queue: Queue()):
        self.devices = {}
        self.midi_sockets = midi_sockets
        self.events_queue = events_queue

    def run(self):
        while True:
            devices = get_devices()
            for device in devices:
                if device['event'] not in self.devices:
                    socket = client.midi_outports.register(device['name'])
                    self.midi_sockets.update({device['event']: socket})

                    instrument = MIDIDevice(midi_socket=socket,
                                            event_queue=self.events_queue,
                                            event_name=device['event'])
                    dev_handler = LinuxHandler(
                        instrument=instrument,
                        kbd_map=LinuxKeyboardMap('keyboard-map.yaml'),
                        device_path='/dev/input/' + device['event'],
                    )

                    capture_thread = Thread(target=dev_handler.run)
                    capture_thread.start()
                    # events_thread = Thread(target=dev_handler.handle_event, args=(capture_thread,))
                    # events_thread.start()

                    self.devices.update({device['event']: {'capture': capture_thread}})
                    # self.devices.update({device['event']: {'capture': capture_thread,
                    #                                        'events': events_thread}})

                    timestamp = get_timestamp()
                    print('%s: opened midi port: %s' % (timestamp,
                                                        device['name']))

            devices_to_remove = []
            for event, threads in self.devices.items():
                # if not any([threads['capture'].is_alive(),
                #             threads['events'].is_alive()]):
                if not any([threads['capture'].is_alive()]):
                    devices_to_remove.append(event)

            for event in devices_to_remove:
                event_name = self.midi_sockets[event].name.split(':')[1]
                self.midi_sockets[event].unregister()
                self.midi_sockets.pop(event)

                timestamp = get_timestamp()
                print('%s: closed midi port: %s' % (timestamp,
                                                    event_name))
                self.devices.pop(event)

            time.sleep(0.1)


if __name__ == '__main__':
    midi_sockets = {}
    events_queue = Queue()


    def process(frames):
        for event_name, socket in midi_sockets.items():
            socket.clear_buffer()

        events = []
        try:
            event = events_queue.get_nowait()
            events.append(event)
        except Empty:
            pass
        else:
            for event in events:
                if isinstance(event['socket'], str):
                    midi_sockets[event['socket']].write_midi_event(
                        event['event'][0], event['event'][1]
                    )
                    print('%s: sent midi event: %3d %3d %3d' % (
                        event['socket'], event['event'][1][0], event['event'][1][1], event['event'][1][2],
                    ))
                    # for dev, socket in midi_sockets.items():
                    #     socket.write_midi_event(
                    #         event['event'][0], event['event'][1]
                    #     )
                # else:
                #     event['socket'].write_midi_event(
                #         event['event'][0], event['event'][1]
                #     )


    client = jack.Client("keyboard2000")
    client.set_process_callback(process)
    client.activate()

    device_watcher = DevicesWatcher(midi_sockets=midi_sockets,
                                    events_queue=events_queue)
    watcher_thread = Thread(target=device_watcher.run)
    watcher_thread.start()
