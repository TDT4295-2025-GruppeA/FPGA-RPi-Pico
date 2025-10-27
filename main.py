from machine import SPI, Pin
from time import sleep
import math

spi = SPI(0, baudrate=5000000)
print(spi)

class ChipSelect():
    """Context manager for chip select pin."""

    def __init__(self, pin_id: int):
        self.cs = Pin(pin_id, mode=Pin.OUT, value=1)

    def __enter__(self):
        self.cs(0)

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.cs(1)

DECIMAL_WIDTH = 14
TOTAL_WIDTH = 25

def to_fixed(value: float | int) -> int:
    """Converts a floating point number to a fixed point number."""
    return int(round((value * (1 << DECIMAL_WIDTH)))) & ((1 << TOTAL_WIDTH) - 1)

def to_fixed_list(values: list[float | int]) -> list[int]:
    """Converts a list of floating point numbers to fixed point numbers."""
    return [to_fixed(v) for v in values]

def flatten(obj) -> list:
    """Converts a list of nested lists into a single list."""
    l = []

    for x in obj:
        if isinstance(x, (list, tuple)):
            l.extend(flatten(x))
        else:
            l.append(x)

    return l

def pack(values: list[int], element_width: int = TOTAL_WIDTH) -> bytes:
    """Packs a list of integers into a byte array. MSB will be byte aligned."""
    # Mask to ensure no elements exceed the specified width
    width_mask = (1 << element_width) - 1

    # Pack all values together
    packed = 0
    for v in values:
        packed = (packed << element_width) | (v & width_mask)

    # Calculate length in bits and length in bytes
    total_bits = len(values) * element_width
    byte_len = math.ceil(total_bits / 8)

    # Shift so that MSB is byte aligned
    shift = byte_len * 8 - total_bits
    packed <<= shift

    return packed.to_bytes(byte_len, 'big')

tp = Pin(20, mode=Pin.IN)

FPS = 60

N = 512
M = 10000

SCALE = 1

for i in range(N*M):
    with ChipSelect(17):
        t = i / N * 2 * math.pi

        # Rotate around y axis
        rotation_matrix = [
            [math.cos(t),  0, -math.sin(t)],
            [          0, -1,            0],
            [math.sin(t),  0,  math.cos(t)],
        ]

        # Flip y and z, and rotate around y axis
        # rotation_matrix = [
        #     [-math.cos(t), math.sin(t), 0],
        #     [0,  0, -1],
        #     [math.sin(t),  math.cos(t), 0],
        # ]

        scale = SCALE * 2#* (1 + 0.5 * math.cos(0.1*t))
        rotation_matrix = [[scale * element for element in row] for row in rotation_matrix]

        # position_vector = [
        #     2.8*math.sin(2.92*t),
        #     2.4*math.cos(1.14*t),
        #     2*math.cos(1.26*t)**2+2,
        # ]

        position_vector = [
            0, 0.1, 2 # + 15*math.cos(t*0.5556424),
        ]

        transform = pack(to_fixed_list(position_vector + flatten(rotation_matrix)))

        spi.write(transform)
    
    sleep(1/FPS)