from multiprocessing import Queue
from typing import Union

from jack import OwnMidiPort


class Ctrl:
    octave_up = 0
    octave_down = 1
    semitone_up = 2
    semitone_down = 3
    channel_up = 4
    channel_down = 5
    program_up = 6
    program_down = 7
    octave_add = 8
    octave_del = 9
    panic = 10
    reset = 11


def note_on(channel: int, note: int, velocity: int = 127):
    if not 1 <= channel <= 16:
        raise ValueError('Channel not in range 1-16')
    if not 0 <= velocity <= 127:
        raise ValueError('Velocity not in range 0-127')
    if not 0 <= note <= 127:
        raise ValueError('Note not in range 0-127')
    channel -= 1

    midi_bytes = (0b1001 << 4) + channel, note, velocity
    return midi_bytes


def note_off(channel: int, note: int, velocity: int = 0):
    if not 1 <= channel <= 16:
        raise ValueError('Channel not in range 1-16')
    if not 0 <= velocity <= 127:
        raise ValueError('Velocity not in range 0-127')
    if not 0 <= note <= 127:
        raise ValueError('Note not in range 0-127')
    channel -= 1

    midi_bytes = (0b1000 << 4) + channel, note, velocity
    return midi_bytes


def panic():
    return 176, 123, 0


class MidiEvent:
    def __init__(self, note: int, pressed_down: bool):
        self.note = note
        self.pressed_down = pressed_down


class ControlEvent:
    def __init__(self, code: int, pressed_down: bool):
        self.code = code
        self.pressed_down = pressed_down


class MIDIDevice:
    def __init__(self, midi_socket: OwnMidiPort, event_queue: Queue, event_name: str):
        """
        MIDIDevice is an Instrument object which is managing self state and putting midi event onto queue
        :param midi_socket: Midi socket, currently not used
        :param event_queue: main multiprocessing.Queue of midi events
        :param event_name: name to recognize connected device
        """
        self.midi_socket = midi_socket
        self.event_queue = event_queue
        self.event_name = event_name

        self.octaves = 0
        self.semitones = 0
        self.addition_octaves = 0
        self.channel = 1
        self.programm = 0

    def handle_event(self, event: Union[MidiEvent, ControlEvent]):
        if isinstance(event, MidiEvent):
            self._handle_midi_event(event)
        elif isinstance(event, ControlEvent):
            self._handle_control_event(event)

    def _handle_midi_event(self, event: MidiEvent):
        if not event.pressed_down:
            midi_data = note_on(
                channel=self.channel,
                note=event.note + self.octaves + self.semitones,
                # velocity=randint(64, 127)
            )
        else:
            midi_data = note_off(
                channel=self.channel,
                note=event.note + self.octaves + self.semitones
            )

        for octave in range(0, self.addition_octaves + 1):
            self.event_queue.put({
                "event": (0, (midi_data[0], midi_data[1] + (12 * (octave + 1)), midi_data[2])),
                "socket": self.event_name  # Can't put midi_socket onto Queue
            })

    def _handle_control_event(self, event: ControlEvent):
        if event.code == Ctrl.octave_down and event.pressed_down:
            self.octaves -= 12
            self._send_event((0, panic()))
            print('octave down, %s semitones' % self.octaves)
        elif event.code == Ctrl.octave_up and event.pressed_down:
            self.octaves += 12
            self._send_event((0, panic()))
            print('octave up, %s semitones' % self.octaves)

        elif event.code == Ctrl.semitone_down and event.pressed_down:
            self.semitones -= 1
            self._send_event((0, panic()))
            print('semitone down, %s semitones' % self.semitones)
        elif event.code == Ctrl.semitone_up and event.pressed_down:
            self.semitones += 1
            self._send_event((0, panic()))
            print('semitone up, %s semitones' % self.semitones)

        elif event.code == Ctrl.octave_del and event.pressed_down:
            self.addition_octaves -= 1
            self._send_event((0, panic()))
            print('remove additional ovtave, %s octaves' % self.addition_octaves)
        elif event.code == Ctrl.octave_add and event.pressed_down:
            self.addition_octaves += 1
            self._send_event((0, panic()))
            print('add additional octave, %s octaves' % self.addition_octaves)

        elif event.code == Ctrl.channel_down and event.pressed_down:
            self.channel -= 1
            self._send_event((0, panic()))
            print('channel down, %s channel' % self.channel)
        elif event.code == Ctrl.channel_up and event.pressed_down:
            self.channel += 1
            self._send_event((0, panic()))
            print('channel up, %s channel' % self.channel)

        elif event.code == Ctrl.program_down and event.pressed_down:
            if self.programm > 0:
                self.programm -= 1
                self._send_event((0, (192, self.programm)))
                print('program down, %s program' % self.channel)
            else:
                print('program set to 0, no lower is possible')
        elif event.code == Ctrl.program_up and event.pressed_down:
            if self.programm < 127:
                self.programm += 1
                self._send_event((0, (192, self.programm)))
                print('program up, %s program' % self.channel)
            else:
                print('program set to 127, no higher is possible')

        elif event.code == Ctrl.panic and event.pressed_down:
            self._send_event((0, panic()))
            print('panic!')

        elif event.code == Ctrl.reset and event.pressed_down:
            print('reset')
            self.octaves = 0
            self.semitones = 0
            self.addition_octaves = 0
            self.channel = 1
            self.programm = 0

    def _send_event(self, event):
        self.event_queue.put({
            'socket': self.event_name,
            'event': event
        })
