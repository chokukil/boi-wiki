// The kit writes a stored ZIP, so source bytes remain slices of the selected
// local file. No extraction, network request or decompression happens here.
async function selectedBundleFiles(input) {
  const selected = Array.from(input.files);
  if (selected.length !== 1 || !selected[0].name.toLowerCase().endsWith('.boi-bundle.zip')) return selected;
  const file = selected[0], fail = () => {throw new Error('준비한 묶음을 읽을 수 없습니다. 연결한 AI에서 묶음을 다시 검사해 주세요.');};
  const read = async (offset, length) => {
    if (offset < 0 || length < 0 || offset + length > file.size) fail();
    return new DataView(await file.slice(offset, offset + length).arrayBuffer());
  };
  if (file.size < 22 || file.size > 2 * 1024 ** 3 + 32 * 1024 ** 2) fail();
  const end = await read(file.size - 22, 22);
  if (end.getUint32(0, true) !== 0x06054b50 || end.getUint16(4, true) || end.getUint16(6, true) ||
      end.getUint16(20, true) || end.getUint16(8, true) !== end.getUint16(10, true)) fail();
  const count = end.getUint16(10, true), length = end.getUint32(12, true), start = end.getUint32(16, true);
  if (!count || count > 10001 || length > 4 * 1024 ** 2 || start + length !== file.size - 22) fail();
  const central = await read(start, length), decoder = new TextDecoder('utf-8', {fatal: true});
  const entries = new Map(); let pos = 0, previousEnd = 0;
  for (let i = 0; i < count; i++) {
    if (pos + 46 > length || central.getUint32(pos, true) !== 0x02014b50) fail();
    const flags = central.getUint16(pos + 8, true), method = central.getUint16(pos + 10, true);
    const crc = central.getUint32(pos + 16, true), compressed = central.getUint32(pos + 20, true);
    const size = central.getUint32(pos + 24, true), nameLength = central.getUint16(pos + 28, true);
    const extra = central.getUint16(pos + 30, true), comment = central.getUint16(pos + 32, true);
    const offset = central.getUint32(pos + 42, true);
    if (flags || method || extra || comment || central.getUint16(pos + 34, true) ||
        compressed !== size || pos + 46 + nameLength > length || size > 256 * 1024 ** 2) fail();
    const name = decoder.decode(new Uint8Array(central.buffer, pos + 46, nameLength));
    if (entries.has(name) || (name !== 'manifest.json' && !/^objects\/[A-Za-z0-9][A-Za-z0-9._-]{0,95}\.blob$/.test(name))) fail();
    if (offset !== previousEnd) fail();
    const local = await read(offset, 30 + nameLength);
    if (local.getUint32(0, true) !== 0x04034b50 || local.getUint16(6, true) !== flags ||
        local.getUint16(8, true) !== method || local.getUint32(14, true) !== crc ||
        local.getUint32(18, true) !== size || local.getUint32(22, true) !== size ||
        local.getUint16(26, true) !== nameLength || local.getUint16(28, true) ||
        decoder.decode(new Uint8Array(local.buffer, 30, nameLength)) !== name) fail();
    const dataStart = offset + 30 + nameLength;
    previousEnd = dataStart + size;
    if (previousEnd > start) fail();
    const blob = file.slice(dataStart, previousEnd);
    // File construction from a Blob retains browser-managed slices.
    entries.set(name, new File([blob], name, {type: 'application/octet-stream'}));
    pos += 46 + nameLength;
  }
  if (pos !== length || previousEnd !== start || !entries.has('manifest.json') || entries.size !== reviewData.objects.length + 1) fail();
  const manifestFile = entries.get('manifest.json');
  if (manifestFile.size > 16 * 1024 ** 2) fail();
  const manifest = localDocument(decoder.decode(await manifestFile.arrayBuffer())).value('');
  const canonical = value => {
    if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
    if (value !== null && typeof value === 'object') return '{' + Object.keys(value).sort().map(k => JSON.stringify(k) + ':' + canonical(value[k])).join(',') + '}';
    if (typeof value === 'number' && !Number.isSafeInteger(value)) fail();
    return JSON.stringify(value);
  };
  if (await digest(new TextEncoder().encode(canonical(manifest))) !== intent.manifest_digest)
    throw new Error('이 묶음은 현재 확인할 변경·공유 범위와 다릅니다. 연결한 AI에서 확인 링크를 다시 열어 주세요.');
  return reviewData.objects.map(obj => {
    const value = entries.get('objects/' + obj.object_id + '.blob');
    if (!value || value.size !== obj.byte_length) fail();
    return value;
  });
}
