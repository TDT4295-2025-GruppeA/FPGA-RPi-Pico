from machine import SPI, Pin
from time import sleep
import math

TOTAL_WIDTH = 32
DECIMAL_WIDTH = 16

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

class ChipSelect():
    """Context manager for chip select pin."""

    def __init__(self, pin_id: int):
        self.cs = Pin(pin_id, mode=Pin.OUT, value=1)

    def __enter__(self):
        self.cs(0)

    def __exit__(self, exception_type, exception_value, exception_traceback):
        self.cs(1)

class FPGA:
    CMD_BEGIN_MODEL_UPLOAD = 0xa0
    CMD_UPLOAD_TRIANGLE = 0xa1
    CMD_ADD_MODEL_INSTANCE = 0xb0

    def __init__(self):
        self._pin = 17
        self._spi = SPI(0, baudrate=5000000)
        print(self._spi)
    
    def _send_cmd(self, cmd: int, data: bytes, dosleep=False):
        #print(f"Sending command: {cmd}, {len(data)} bytes")
        data = cmd.to_bytes(1, "big") + data
        # if b"\xa1" in data:
        #     print("A1 IN DATA!!")
        
        data1 = data[0:100]
        data2 = data[100:]
        #with ChipSelect(self._pin):
        if dosleep:
           sleep(0.1)
        #self._spi.write(b"\x00\x00\x00\x00")
        self._spi.write(data1)
        if dosleep:
            sleep(0.01)
        self._spi.write(data2)
        # self._spi.write(b"\x00\x00\x00\x00")
        

    def add_model(self, model_id: int):
        self._send_cmd(self.CMD_BEGIN_MODEL_UPLOAD, model_id.to_bytes(1, "big"))
    
    def upload_triagle(self, triangle: bytes):
        if len(triangle) != 42:
            raise RuntimeError(f"Incorrect tringle length: {len(triangle)}")
        self._send_cmd(self.CMD_UPLOAD_TRIANGLE, triangle)
    
    def upload_model(self, model_path: str, model_id: int):
        self.add_model(model_id)
        with open(model_path, "rb") as f:
            triangle = f.read(42)
            while triangle != b"":
                self.upload_triagle(triangle)
                triangle = f.read(42)
                #sleep(0.01)
    
    def add_model_instance(self, model_id: int, transform: bytes, last_in_scene: int):
        data = (
            last_in_scene.to_bytes(1, "big")
            + model_id.to_bytes(1, "big")
            + transform)
        self._send_cmd(self.CMD_ADD_MODEL_INSTANCE, data, dosleep=False)
    
    def read(self, size: int = 1) -> bytes:
        return self._spi.read(size)


def to_fixed(value: float | int) -> int:
    """Converts a floating point number to a fixed point number."""
    return int(round((value * (1 << DECIMAL_WIDTH)))) & ((1 << TOTAL_WIDTH) - 1)

def to_fixed_list(values) -> list[int]:
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

def euler_to_rotation_matrix(pitch: float, yaw: float, roll: float) -> list[list[float]]:
    """
    Convert Euler angles to rotation matrix.
    Rotation order: ZYX (yaw, pitch, roll)

    Courtesy of chat GPT!

    Args:
        roll: Rotation around X-axis in radians
        pitch: Rotation around Y-axis in radians
        yaw: Rotation around Z-axis in radians
    
    Returns:
        3x3 rotation matrix as a list of lists
    """
    # Precompute sines and cosines
    cos_x = math.cos(pitch)
    sin_x = math.sin(pitch)
    cos_y = math.cos(yaw)
    sin_y = math.sin(yaw)
    cos_z = math.cos(roll)
    sin_z = math.sin(roll)

    # Rotation matrix
    R = [
        [cos_z * cos_y, -cos_z * sin_y * sin_x - sin_z * cos_x, sin_z * sin_x + cos_z * sin_y * cos_x],
        [sin_z * cos_y, -sin_z * sin_y * sin_x + cos_z * cos_x, cos_z * sin_x + sin_z * sin_y * cos_x],
        [        sin_y,                          cos_y * sin_x,                        -cos_y * cos_x],
    ]
    
    return R

tp = Pin(20, mode=Pin.IN)

FPS = 30

N = 512
M = 10000

SCALE = 0.25

fpga = FPGA()

MODEL_CUBE = 0
MODEL_TEAPOT_LOWER_POLY = 1
MODEL_SUZANNE = 2

with ChipSelect(17):
    #fpga.upload_model("teapot-lower-poly.data", MODEL_TEAPOT_LOWER_POLY)
    fpga.upload_model("suzanne.data", MODEL_SUZANNE)
    fpga.upload_model("cube.data", MODEL_CUBE)
    fpga.upload_model("teapot-lower-poly.data", MODEL_TEAPOT_LOWER_POLY)
    # fpga.upload_model("suzanne.data", MODEL_SUZANNE)
    # fpga.upload_model("teapot-lower-poly.data", 1)
    #fpga.read(1)
    #fpga.upload_model("teapot.data", MODEL_TEAPOT)
    sleep(0.1)

for i in range(N*M):
    #i = int(input("ksdf.."))
    with ChipSelect(17):
        t = i / N * 2 * math.pi

        # Rotate around y axis
        rotation_matrix = euler_to_rotation_matrix(0, t, 0)
        scale = SCALE * 2#* (1 + 0.5 * math.cos(0.1*t))
        rotation_matrix = [[scale * element for element in row] for row in rotation_matrix]
        
        x0 = -1
        x1 = 1
        y0 = -1
        y1 = 1
        z = 2
        
        nx = 3
        ny = 3

        for i in range(nx):
            for j in range(ny):
                x = x0 + (x1 - x0) * i / (nx - 1)
                y = y0 + (y1 - y0) * j / (ny - 1)

                position_vector = [
                    x, y, z
                ]

                model = MODEL_CUBE if (i % 2 and j % 2) else MODEL_TEAPOT_LOWER_POLY

                transform = pack(to_fixed_list(position_vector + flatten(rotation_matrix)))
                fpga.add_model_instance(model, transform, last_in_scene=int(i >= nx - 1 and j >= ny - 1))

        fpga._spi.write(bytes([0x00]))
    sleep(1/FPS)
