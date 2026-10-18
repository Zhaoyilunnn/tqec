from typing import Final

MEASUREMENT_SCHEDULE: Final[int] = 6

EXTENDED_PLAQUETTE_SCHEDULES: Final[dict[bool, tuple[int, int, int, int]]] = {
    False: (2, 4, 3, 5),
    True: (5, 3, 4, 2),
}
