/* Generate the two raster icons required by Android's PWA installer.
 * No third-party image dependency is needed, which keeps a clean static-site
 * checkout reproducible on the Windows build machine.
 */
const fs = require("fs");
const path = require("path");
const zlib = require("zlib");

function crc32(buffer) {
  let crc = 0xffffffff;
  for (const byte of buffer) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit += 1) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1));
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function chunk(type, data) {
  const name = Buffer.from(type, "ascii");
  const output = Buffer.alloc(data.length + 12);
  output.writeUInt32BE(data.length, 0);
  name.copy(output, 4);
  data.copy(output, 8);
  output.writeUInt32BE(crc32(Buffer.concat([name, data])), data.length + 8);
  return output;
}

function icon(size) {
  const pixels = Buffer.alloc((size * 4 + 1) * size);
  const set = (x, y, r, g, b, a = 255) => {
    const offset = y * (size * 4 + 1) + 1 + x * 4;
    pixels[offset] = r; pixels[offset + 1] = g; pixels[offset + 2] = b; pixels[offset + 3] = a;
  };
  const mid = size * 0.44;
  const outer = size * 0.32;
  const inner = size * 0.12;
  for (let y = 0; y < size; y += 1) {
    pixels[y * (size * 4 + 1)] = 0;
    for (let x = 0; x < size; x += 1) {
      const dx = x - mid, dy = y - mid, radius = Math.hypot(dx, dy);
      let color = [15, 23, 42];
      if (radius > outer - size * 0.018 && radius < outer + size * 0.018) color = [103, 232, 249];
      if (radius > inner - size * 0.016 && radius < inner + size * 0.016) color = [165, 243, 252];
      if (radius < size * 0.045) color = [236, 254, 255];
      const beam = Math.abs(dy - dx * 0.22) < size * 0.018 && dx > 0 && radius < outer;
      if (beam) color = [34, 211, 238];
      const handle = Math.abs(dy - dx) < size * 0.045 && dx > outer * 0.55 && dx < size * 0.52;
      if (handle) color = [236, 254, 255];
      set(x, y, ...color);
    }
  }
  const header = Buffer.alloc(13);
  header.writeUInt32BE(size, 0); header.writeUInt32BE(size, 4);
  header[8] = 8; header[9] = 6;
  return Buffer.concat([
    Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]),
    chunk("IHDR", header),
    chunk("IDAT", zlib.deflateSync(pixels, { level: 9 })),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const destination = path.resolve(__dirname, "..", "worker-console");
fs.mkdirSync(destination, { recursive: true });
for (const size of [192, 512]) fs.writeFileSync(path.join(destination, `icon-${size}.png`), icon(size));
