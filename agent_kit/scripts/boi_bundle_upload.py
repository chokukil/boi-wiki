"""Exact binary transport for an already admitted bundle; no admission or retries.

Only missing server offsets are sent. Every invocation reads current status;
any unknown PUT outcome stops this invocation before a second PUT is attempted.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import zipfile


class UploadError(ValueError):
    pass


def digest(raw):
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise UploadError('BOI_BUNDLE_DUPLICATE_JSON_KEY')
        value[key] = item
    return value


def _status(client, bundle_ref, manifest, manifest_digest):
    status = client.publication('status', {'bundle_ref': bundle_ref})
    if (status.get('bundle_ref') != bundle_ref or status.get('manifest_digest') != manifest_digest
            or status.get('manifest') != manifest or status.get('basis_current') is not True
            or not (status.get('admission_recorded') is True or status.get('confirmation_recorded') is True)
            or status.get('state') in ('stopped', 'aborted')):
        raise UploadError('BOI_BUNDLE_STATUS_BINDING_OR_ADMISSION_CHANGED')
    chunk = status.get('upload_limits', {}).get('chunk_bytes')
    if type(chunk) is not int or not 65536 <= chunk <= 4 * 1024 * 1024:
        raise UploadError('BOI_BUNDLE_CHUNK_LIMIT_INVALID')
    rows = status.get('uploads')
    if (not isinstance(rows, list) or len(rows) != len(manifest['objects'])
            or any(not isinstance(row, dict) for row in rows)):
        raise UploadError('BOI_BUNDLE_STATUS_OBJECT_SET_CHANGED')
    by_id = {row.get('object_id'): row for row in rows}
    if set(by_id) != {obj['object_id'] for obj in manifest['objects']}:
        raise UploadError('BOI_BUNDLE_STATUS_OBJECT_SET_CHANGED')
    for obj in manifest['objects']:
        row = by_id[obj['object_id']]
        offsets = row.get('received_offsets')
        if (row.get('byte_length') != obj['byte_length'] or not isinstance(offsets, list)
                or any(type(n) is not int or n < 0 or n >= obj['byte_length'] or n % chunk for n in offsets)
                or len(set(offsets)) != len(offsets)
                or row.get('received_bytes') != sum(min(chunk, obj['byte_length']-n) for n in offsets)
                or type(row.get('complete')) is not bool
                or row['complete'] != (row['received_bytes'] == obj['byte_length'])):
            raise UploadError('BOI_BUNDLE_STATUS_OFFSETS_INVALID')
    return status, chunk, by_id


def upload_bundle(client, archive_path, bundle_ref):
    if not isinstance(bundle_ref, str) or not re.fullmatch(r'local-bundle:sha256:[a-f0-9]{64}', bundle_ref):
        raise UploadError('BOI_BUNDLE_REFERENCE_INVALID')
    path = Path(archive_path)
    if path.is_symlink() or not path.is_file():
        raise UploadError('BOI_BUNDLE_ARCHIVE_UNAVAILABLE')
    try:
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo('manifest.json')
            if info.file_size > 16 * 1024 * 1024:
                raise UploadError('BOI_BUNDLE_MANIFEST_TOO_LARGE')
            manifest = json.loads(archive.read(info), object_pairs_hook=_object)
            if not isinstance(manifest, dict):
                raise UploadError('BOI_BUNDLE_ARCHIVE_OBJECTS_INVALID')
            objects = manifest.get('objects')
            if not isinstance(objects, list) or not 1 <= len(objects) <= 1100:
                raise UploadError('BOI_BUNDLE_ARCHIVE_OBJECTS_INVALID')
            names = ['manifest.json']
            for obj in objects:
                if (not isinstance(obj, dict)
                        or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,95}', obj.get('object_id', ''))
                        or type(obj.get('byte_length')) is not int or obj['byte_length'] < 1
                        or not re.fullmatch(r'sha256:[a-f0-9]{64}', obj.get('byte_digest', ''))):
                    raise UploadError('BOI_BUNDLE_ARCHIVE_OBJECTS_INVALID')
                name = 'objects/' + obj['object_id'] + '.blob'
                if name in names or archive.getinfo(name).file_size != obj['byte_length']:
                    raise UploadError('BOI_BUNDLE_ARCHIVE_OBJECTS_INVALID')
                names.append(name)
            if (len(archive.namelist()) != len(names) or set(archive.namelist()) != set(names)
                    or sum(o['byte_length'] for o in objects) > 2 * 1024 * 1024 * 1024
                    or any(i.compress_type != zipfile.ZIP_STORED or i.flag_bits & 1 for i in archive.infolist())):
                raise UploadError('BOI_BUNDLE_ARCHIVE_LAYOUT_INVALID')
            manifest_digest = digest(canonical(manifest))
            status, chunk_size, received = _status(client, bundle_ref, manifest, manifest_digest)
            # Verify every full object before any PUT, preserving per-chunk
            # digests so later local edits cannot introduce different bytes.
            chunks = {}
            for obj in objects:
                full = hashlib.sha256()
                with archive.open('objects/' + obj['object_id'] + '.blob') as stream:
                    for offset in range(0, obj['byte_length'], chunk_size):
                        raw = stream.read(chunk_size)
                        full.update(raw)
                        chunks[obj['object_id'], offset] = digest(raw)
                if 'sha256:' + full.hexdigest() != obj['byte_digest']:
                    raise UploadError('BOI_BUNDLE_ARCHIVE_BYTES_CHANGED')
            sent = 0
            for obj in objects:
                with archive.open('objects/' + obj['object_id'] + '.blob') as stream:
                    for offset in range(0, obj['byte_length'], chunk_size):
                        raw = stream.read(chunk_size)
                        if digest(raw) != chunks[obj['object_id'], offset]:
                            raise UploadError('BOI_BUNDLE_ARCHIVE_BYTES_CHANGED')
                        if offset in received[obj['object_id']]['received_offsets']:
                            continue
                        url = ('/api/v2/local-bundles/' + bundle_ref.split(':')[-1]
                               + '/objects/' + obj['object_id'] + '?offset=' + str(offset))
                        result = client.put_chunk(url, raw, bundle_ref=bundle_ref,
                                                  object_id=obj['object_id'], offset=offset)
                        if (result.get('bundle_ref') != bundle_ref or result.get('object_id') != obj['object_id']
                                or type(result.get('accepted_offset')) is not int
                                or result['accepted_offset'] != offset or result.get('byte_digest') != obj['byte_digest']):
                            raise UploadError('BOI_BUNDLE_CHUNK_RESPONSE_UNKNOWN_READ_STATUS')
                        sent += 1
            final, _, _ = _status(client, bundle_ref, manifest, manifest_digest)
            if not all(row['complete'] for row in final['uploads']):
                raise UploadError('BOI_BUNDLE_UPLOAD_INCOMPLETE_READ_STATUS')
            return {'contract_version': 'boi/bundle-upload-result@1', 'bundle_ref': bundle_ref,
                    'manifest_digest': manifest_digest, 'sent_chunks': sent,
                    'complete': True, 'status': final, 'publication_performed': False}
    except (KeyError, TypeError, json.JSONDecodeError, zipfile.BadZipFile, RuntimeError, OSError):
        raise UploadError('BOI_BUNDLE_ARCHIVE_OR_LOCAL_IO_INVALID') from None
