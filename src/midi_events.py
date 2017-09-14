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
