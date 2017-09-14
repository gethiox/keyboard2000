#!/usr/bin/env python3
import datetime
import re
import time
from queue import Queue, Empty
from random import randint
from threading import Thread

import jack
import yaml

from src.midi_events import note_off, note_on


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
    def __init__(self, midi_sockets):
        self.devices = {}
        self.midi_sockets = midi_sockets

    def run(self):
        while True:
            devices = get_devices()
            for device in devices:
                if device['event'] not in self.devices:
                    socket = client.midi_outports.register(device['name'])
                    self.midi_sockets.update({device['event']: socket})

                    dev_handler = DeviceHandler('/dev/input/' + device['event'], socket)

                    capture_thread = Thread(target=dev_handler.capture_dev)
                    capture_thread.start()
                    events_thread = Thread(target=dev_handler.handle_event, args=(capture_thread,))
                    events_thread.start()

                    self.devices.update({device['event']: {'capture': capture_thread,
                                                           'events': events_thread}})

                    timestamp = get_timestamp()
                    print('%s: opened midi port: %s' % (timestamp,
                                                        device['name']))

            devices_to_remove = []
            for event, threads in self.devices.items():
                if not any([threads['capture'].is_alive(),
                            threads['events'].is_alive()]):
                    devices_to_remove.append(event)

            for event in devices_to_remove:
                event_name = self.midi_sockets[event].name.split(':')[1]
                self.midi_sockets[event].unregister()
                self.midi_sockets.pop(event)

                timestamp = get_timestamp()
                print('%s: closed midi port: %s' % (timestamp,
                                                    event_name))
                self.devices.pop(event)

            time.sleep(1)


class DeviceHandler:
    def __init__(self, path, midi_socket):
        self.path = path
        self.midi_socket = midi_socket
        self.octaves = 0
        self.semitones = 0
        self.addition_octaves = 0
        self.channel = 1
        self.events_queue = Queue()
        self.programm = 0

    def capture_dev(self):
        try:
            device = open(self.path, 'rb')
        except:
            print('opening device failed, try again')
            return

        try:
            while True:
                collected_events = []
                segment = [device.read(8), device.read(8), device.read(8)]

                while b'\x00\x00\x00\x00\x00\x00\x00\x00' not in segment[2] and \
                                b'\x00\x00\x00\x00\x01\x00\x00\x00' not in segment[2]:

                    data = segment[2]

                    if (data[0], data[1], data[3], data[5], data[6], data[7]) == (1, 0, 0, 0, 0, 0):
                        key, status = data[2], data[4]

                        if status in [0, 1]:
                            collected_events.append({'key': key, 'status': status, 'timestamp': None})

                    segment = [device.read(8), device.read(8), device.read(8)]

                for key in collected_events:
                    self.events_queue.put([key['key'], key['status']])
        except:
            device.close()

    def handle_event(self, capture_thread):
        while capture_thread.is_alive():
            try:
                char, state = self.events_queue.get(timeout=1)
            except Empty:
                continue

            midi_event = None
            if char in keyboard_map:
                if state == 1:
                    midi_event = note_on(self.channel,
                                         keyboard_map[char] + self.octaves + self.semitones,
                                         randint(64, 127))
                elif state == 0:
                    midi_event = note_off(self.channel,
                                          keyboard_map[char] + self.octaves + self.semitones)
            else:
                if char == 59 and state == 1:
                    self.octaves -= 12
                    print('octave down, %s semitones' % self.octaves)
                    events_queue.put({'socket': self.midi_socket, 'event': (0, [176, 123, 0])})
                elif char == 60 and state == 1:
                    self.octaves += 12
                    print('octave up, %s semitones' % self.octaves)
                    events_queue.put({'socket': self.midi_socket, 'event': (0, [176, 123, 0])})

                elif char == 61 and state == 1:
                    self.semitones -= 1
                    print('semitone down, %s semitones' % self.semitones)
                    events_queue.put({'socket': self.midi_socket, 'event': (0, [176, 123, 0])})
                elif char == 62 and state == 1:
                    self.semitones += 1
                    print('semitone up, %s semitones' % self.semitones)
                    events_queue.put({'socket': self.midi_socket, 'event': (0, [176, 123, 0])})

                elif char == 63 and state == 1:
                    self.addition_octaves -= 1
                    print('remove additional ovtave, %s octaves' % self.addition_octaves)
                    events_queue.put({'socket': self.midi_socket, 'event': (0, [176, 123, 0])})
                elif char == 64 and state == 1:
                    self.addition_octaves += 1
                    print('add additional octave, %s octaves' % self.addition_octaves)
                    events_queue.put({'socket': self.midi_socket, 'event': (0, [176, 123, 0])})

                elif char == 65 and state == 1:
                    self.channel -= 1
                    print('channel down, %s channel' % self.channel)
                    events_queue.put({'socket': self.midi_socket, 'event': (0, [176, 123, 0])})
                elif char == 66 and state == 1:
                    self.channel += 1
                    print('channel up, %s channel' % self.channel)
                    events_queue.put({'socket': self.midi_socket, 'event': (0, [176, 123, 0])})

                elif char == 67 and state == 1:
                    if self.programm > 0:
                        self.programm -= 1
                        print('program down, %s program' % self.channel)
                        events_queue.put({'socket': self.midi_socket, 'event': (0, [192, self.programm])})
                    else:
                        print('program set to 0, no lower is possible')
                elif char == 68 and state == 1:
                    if self.programm < 127:
                        self.programm += 1
                        print('program up, %s program' % self.channel)
                        events_queue.put({'socket': self.midi_socket, 'event': (0, [192, self.programm])})
                    else:
                        print('program set to 127, no higher is possible')
                elif char == 1 and state == 1:
                    print('panic!')
                    events_queue.put({'socket': self.midi_socket, 'event': (0, [176, 123, 0])})

            if midi_event:
                for octave in range(0, self.addition_octaves + 1):
                    events_queue.put({'socket': self.midi_socket, 'event': (
                    0, (midi_event[0], midi_event[1] + (12 * (octave + 1)), midi_event[2]))})


if __name__ == '__main__':
    midi_sockets = {}
    events_queue = Queue()


    def process(frames):
        for event, socket in midi_sockets.items():
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
                    for dev, socket in midi_sockets.items():
                        socket.write_midi_event(
                            event['event'][0], event['event'][1]
                        )
                else:
                    event['socket'].write_midi_event(
                        event['event'][0], event['event'][1]
                    )
                    print('send midi event:', event['event'][1])


    keyboard_map = yaml.load(open('keyboard-map.yaml'))

    client = jack.Client("GxKeyboard9000")
    client.set_process_callback(process)
    client.activate()

    device_watcher = DevicesWatcher(midi_sockets=midi_sockets)
    watcher_thread = Thread(target=device_watcher.run)
    watcher_thread.start()
