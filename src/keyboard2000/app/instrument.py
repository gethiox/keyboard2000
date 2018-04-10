import logging
from multiprocessing import Queue
from random import randint
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


class NoteEvent:
    def __init__(self, note: int, pressed_down: bool):
        self.note = note
        self.pressed_down = pressed_down

    def __repr__(self):
        return "<NoteEvent, note: '{note}', state: '{state}'>".format(
            note=self.note, state='pressed' if self.pressed_down else 'released'
        )


class ControlEvent:
    def __init__(self, code: int, code_name: str, pressed_down: bool):
        self.code = code
        self.code_name = code_name
        self.pressed_down = pressed_down

    def __repr__(self):
        return "ControlEvent, code: '{code}', state: '{state}'>".format(
            code=self.code_name, state='pressed' if self.pressed_down else 'released'
        )


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

        self.pressed = []

    def handle_event(self, event: Union[NoteEvent, ControlEvent]):
        if event:
            if event.pressed_down or not event.pressed_down:
                logging.info('HardwareEvent [%s]: %s', self.event_name, event)
            if isinstance(event, NoteEvent):
                self._handle_midi_event(event)
            elif isinstance(event, ControlEvent):
                self._handle_control_event(event)

    def _handle_midi_event(self, event: NoteEvent):
        note = event.note + self.octaves + self.semitones
        if 0 > note or note > 127:  # note value above valid range
            logging.warning("note above valid range (0-127 allowed, %d received)", note)
            return

        if event.pressed_down:
            midi_data = note_on(
                channel=self.channel,
                note=note,
                velocity=randint(64, 127),
            )
        else:
            midi_data = note_off(
                channel=self.channel,
                note=note,
            )

        for octave in range(0, self.addition_octaves + 1):
            additional_note = midi_data[1] + (12 * (octave + 1))
            if 0 > additional_note or additional_note > 127:  # note value above valid range
                logging.warning("note above valid range (0-127 allowed, %d received)", additional_note)
                return

            if event.pressed_down:
                self.pressed.append(additional_note )
            elif self.pressed:
                try:
                    self.pressed.remove(additional_note )
                except ValueError:
                    pass

            if event.pressed_down or additional_note  not in self.pressed:
                self.event_queue.put({
                    "event": (0, (midi_data[0], additional_note , midi_data[2])),
                    "socket": self.event_name  # Can't put midi_socket onto Queue
                })

    def _handle_control_event(self, event: ControlEvent):
        if event.code == Ctrl.octave_down and event.pressed_down:
            self.octaves -= 12
            self._send_event((0, panic()))
        elif event.code == Ctrl.octave_up and event.pressed_down:
            self.octaves += 12
            self._send_event((0, panic()))

        elif event.code == Ctrl.semitone_down and event.pressed_down:
            self.semitones -= 1
            self._send_event((0, panic()))
        elif event.code == Ctrl.semitone_up and event.pressed_down:
            self.semitones += 1
            self._send_event((0, panic()))

        elif event.code == Ctrl.octave_del and event.pressed_down and self.addition_octaves > 0:
            self.addition_octaves -= 1
            self._send_event((0, panic()))
        elif event.code == Ctrl.octave_add and event.pressed_down:
            self.addition_octaves += 1
            self._send_event((0, panic()))

        elif event.code == Ctrl.channel_down and event.pressed_down:
            self.channel -= 1
            self._send_event((0, panic()))
            self.pressed = []
        elif event.code == Ctrl.channel_up and event.pressed_down:
            self.channel += 1
            self._send_event((0, panic()))
            self.pressed = []

        elif event.code == Ctrl.program_down and event.pressed_down:
            if self.programm > 0:
                self.programm -= 1
                self._send_event((0, (192, self.programm)))

        elif event.code == Ctrl.program_up and event.pressed_down:
            if self.programm < 127:
                self.programm += 1
                self._send_event((0, (192, self.programm)))
            else:
                pass

        elif event.code == Ctrl.panic and event.pressed_down:
            self._send_event((0, panic()))
            self.pressed = []

        elif event.code == Ctrl.reset and event.pressed_down:
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
