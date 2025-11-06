from stl import mesh
import sys
import os
import numpy as np

# We store the models with Q16.16 independently of what the FPGA
# uses internally for the sake of simplicity. The FPGA will
# convert to its own format as needed.
DECIMAL_WIDTH = 16


def float_to_fixed(value: float, fractional_bits: int) -> int:
    """Convert float to fixed-point representation with given fractional bits."""
    return int(round(value * (1 << fractional_bits)))


def pseudo_random_16_bit_color(v: np.ndarray) -> int:
    s = np.sin(v[0] * 12.9898 + v[1] * 78.2323 + v[2] * 37.1719)
    t = np.sin(v[0] * 93.1234 + v[1] * 67.3435 + v[2] * 54.1623)
    u = np.sin(v[0] * 23.5621 + v[1] * 11.5234 + v[2] * 98.7650)

    r = int(((s * 43758.5453) % 1.0) * 31) & 0x1F
    g = int(((t * 24654.6543) % 1.0) * 63) & 0x3F
    b = int(((u * 13579.2468) % 1.0) * 31) & 0x1F

    return (r << 11) | (g << 5) | (b << 0)


def triangle_normal(v0, v1, v2):
    return np.cross(v1 - v0, v2 - v0)


def ensure_winding(vs, stl_normal):
    """Ensure the triangle vertices are ordered consistently with the STL normal."""
    n = triangle_normal(vs[0], vs[1], vs[2])
    if np.dot(n, stl_normal) < 0:
        return np.array([vs[0], vs[2], vs[1]])
    return vs


def write_sv_mem_triangles(stl_path: str, output_path: str):
    model = mesh.Mesh.from_file(stl_path)
    vertices = model.vectors.copy()
    normals = model.normals

    # min-max normalization to [-1, 1] across all vertices
    all_vertices = vertices.reshape(-1, 3)
    v_min = all_vertices.min(axis=0)
    v_max = all_vertices.max(axis=0)
    center = (v_min + v_max) / 2
    scale = (v_max - v_min).max() / 2
    vertices = (vertices - center) / scale

    with open(output_path, "wb") as f:
        for tri_idx in range(vertices.shape[0]):
            triangle_vertices = vertices[tri_idx]
            stl_normal = normals[tri_idx]
            triangle_vertices = ensure_winding(triangle_vertices, stl_normal)

            output = bytearray()
            for v in triangle_vertices:
                color = pseudo_random_16_bit_color(v)
                x, y, z = v
                qx = float_to_fixed(x, DECIMAL_WIDTH)
                qy = float_to_fixed(y, DECIMAL_WIDTH)
                qz = float_to_fixed(z, DECIMAL_WIDTH)
                output.extend(color.to_bytes(2, "big"))
                output.extend((qx & 0xFFFFFFFF).to_bytes(4, "big"))
                output.extend((qy & 0xFFFFFFFF).to_bytes(4, "big"))
                output.extend((qz & 0xFFFFFFFF).to_bytes(4, "big"))
            f.write(output)

    print(f"Wrote {vertices.shape[0]} triangles to {output_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python convert_model.py input.stl output.mem")
        sys.exit(1)

    stl_path = sys.argv[1]
    output_path = sys.argv[2]

    if not os.path.exists(stl_path):
        print(f"Error: {stl_path} not found")
        sys.exit(1)

    write_sv_mem_triangles(stl_path, output_path)
