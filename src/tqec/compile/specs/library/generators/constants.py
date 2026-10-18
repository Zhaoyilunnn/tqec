from typing import Final

# Keep the original import location available to callers.
from tqec.plaquette.constants import EXTENDED_PLAQUETTE_SCHEDULES  # noqa: F401

VERTICAL_HOOK_SCHEDULES: Final[dict[bool, tuple[int, int, int, int]]] = {
    False: (1, 4, 3, 5),
    True: (5, 3, 4, 1),
}
HORIZONTAL_HOOK_SCHEDULES: Final[dict[bool, tuple[int, int, int, int]]] = {
    False: (1, 2, 3, 5),
    True: (5, 3, 2, 1),
}
