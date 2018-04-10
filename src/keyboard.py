#!/usr/bin/env python3
import datetime
import logging
import os
import re
import sys
import threading
import time
from multiprocessing import Queue
from queue import Empty
from threading import Thread
from typing import List

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
    def __init__(self, midi_sockets, events_queue: Queue, signal_queue: threading.Event, map_directory: str = './maps'):
        self.devices = {}
        self.midi_sockets = midi_sockets
        self.events_queue = events_queue
        self.signal_queue = signal_queue
        self.map_direcotry = map_directory

    def run(self):
        while True:
            if self.signal_queue.is_set():
                for event, captures in self.devices.items():
                    logging.info('waiting to join: %s', event)
                    captures['capture'].join()
                    logging.info('joined capture: %s', event)
                return

            devices = get_devices()
            for device in devices:
                if device['event'] not in self.devices:
                    maps = self.load_maps()

                    choosen_map = None
                    for map in maps:
                        if map.device_name == device['name']:
                            choosen_map = map
                            break

                    if not choosen_map:
                        choosen_map = LinuxKeyboardMap(os.path.join(self.map_direcotry, 'default.yaml'))

                    socket = client.midi_outports.register(choosen_map.nice_name)

                    for port in choosen_map.auto_connect:
                        client.connect(socket, port)
                    self.midi_sockets.update({device['event']: socket})

                    instrument = MIDIDevice(midi_socket=socket,
                                            event_queue=self.events_queue,
                                            event_name=device['event'])

                    dev_handler = LinuxHandler(
                        instrument=instrument,
                        kbd_map=choosen_map,
                        device_path='/dev/input/' + device['event'],
                        signal_queue=self.signal_queue
                    )

                    time.sleep(0.01)
                    capture_thread = Thread(target=dev_handler.run)
                    capture_thread.start()

                    self.devices.update({device['event']: {'capture': capture_thread}})

                    logging.info('opened midi port: %s ["%s"]', choosen_map.nice_name, device['name'])

            devices_to_remove = []
            for event, threads in self.devices.items():
                if not threads['capture'].is_alive():
                    devices_to_remove.append(event)

            for event in devices_to_remove:
                event_name = self.midi_sockets[event]
                self.midi_sockets[event].unregister()
                self.midi_sockets.pop(event)

                logging.info('closed midi port: %s', event_name)
                self.devices.pop(event)

            time.sleep(0.01)

    def load_maps(self) -> List[LinuxKeyboardMap]:
        maps = []
        for map_path in os.listdir(self.map_direcotry):
            maps.append(LinuxKeyboardMap(map_path=os.path.join(self.map_direcotry, map_path)))
        return maps


def set_logger():
    console = logging.StreamHandler(stream=sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(filename)s: %(message)s'))

    root = logging.getLogger('')
    root.setLevel(logging.DEBUG)
    root.addHandler(console)


if __name__ == '__main__':
    set_logger()

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

                    # print('{:7s}: sent midi event: {:3d} {:3d} {:3d}  [0x{:02x} 0x{:02x} 0x{:02x}] {:.4f}'.format(
                    #     event['socket'],
                    #
                    #     event['event'][1][0],
                    #     event['event'][1][1],
                    #     event['event'][1][2],
                    #
                    #     event['event'][1][0],
                    #     event['event'][1][1],
                    #     event['event'][1][2],
                    #
                    #     time.time()
                    # ))


    client = jack.Client("keyboard2000")
    client.set_process_callback(process)
    client.activate()

    # signal_queue = Queue()
    # close_signal = multiprocessing.Event()
    close_signal = threading.Event()

    device_watcher = DevicesWatcher(midi_sockets=midi_sockets,
                                    events_queue=events_queue,
                                    signal_queue=close_signal)
    watcher_thread = Thread(target=device_watcher.run)
    watcher_thread.start()

    try:
        while True:
            time.sleep(0.01)
    except KeyboardInterrupt:
        logging.info('interupt')
        # signal_queue.put(True)
        close_signal.set()
        logging.info('sended signal')
        logging.info('waiting thread to join')
        watcher_thread.join()
        logging.info('joined')
        time.sleep(0.01)
        client.deactivate()
        client.close()
        logging.info('client deactivated')
        exit(0)
