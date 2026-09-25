"""Exact JSON token edits for declared local references, with bounded parsing.

Only selected string value tokens change. Whitespace, number spelling, body and
unknown extension bytes outside those positions survive native import unchanged.
This parser recognizes JSON structure; it never recognizes domain terminology.
"""
from decimal import Decimal
import json
import re


def pointer_tokens(pointer):
    if not isinstance(pointer, str) or not pointer.startswith('/') or re.search(r'~(?![01])', pointer):
        raise ValueError('LOCAL_BUNDLE_JSON_POINTER_INVALID')
    return tuple(s.replace('~1', '/').replace('~0', '~') for s in pointer[1:].split('/'))


class LocalJsonDocument:
    def __init__(self, raw, pointers=(), *, require_content=True):
        self.text = raw.decode('utf-8')
        self.wanted = {pointer_tokens(p) for p in pointers} | ({('content',)} if require_content else set())
        self.ranges, self.values, self.nodes = {}, {}, 0
        def invalid(_):
            raise ValueError('LOCAL_BUNDLE_JSON_NONFINITE')
        self.decoder = json.JSONDecoder(parse_float=Decimal, parse_constant=invalid)
        try:
            self.value, end = self._value(self._space(0), (), 0)
            if self._space(end) != len(self.text):
                raise ValueError('LOCAL_BUNDLE_JSON_TRAILING_DATA')
        except (RecursionError, json.JSONDecodeError, IndexError, UnicodeError):
            raise ValueError('LOCAL_BUNDLE_JSON_INVALID') from None
        if any(p not in self.ranges for p in self.wanted):
            raise ValueError('LOCAL_BUNDLE_JSON_POINTER_MISSING')

    def _space(self, position):
        while position < len(self.text) and self.text[position] in ' \t\r\n':
            position += 1
        return position

    def _value(self, start, path, depth):
        self.nodes += 1
        if depth > 128 or self.nodes > 250000:
            raise ValueError('LOCAL_BUNDLE_JSON_STRUCTURE_LIMIT')
        token = self.text[start]
        if token in '{[':
            obj = token == '{'
            value, end, closing = ({} if obj else []), self._space(start + 1), ('}' if obj else ']')
            if self.text[end] != closing:
                while True:
                    if obj:
                        key, end = self.decoder.raw_decode(self.text, end)
                        if not isinstance(key, str) or key in value:
                            raise ValueError('LOCAL_BUNDLE_JSON_DUPLICATE_OR_INVALID_KEY')
                        end = self._space(end)
                        if self.text[end] != ':':
                            raise ValueError('LOCAL_BUNDLE_JSON_INVALID')
                        end = self._space(end + 1)
                    else:
                        key = str(len(value))
                    child, end = self._value(end, (*path, key), depth + 1)
                    if obj:
                        value[key] = child
                    else:
                        value.append(child)
                    end = self._space(end)
                    if self.text[end] == closing:
                        break
                    if self.text[end] != ',':
                        raise ValueError('LOCAL_BUNDLE_JSON_INVALID')
                    end = self._space(end + 1)
            end += 1
        else:
            value, end = self.decoder.raw_decode(self.text, start)
        if path in self.wanted:
            self.ranges[path] = (start, end)
            self.values[path] = value
        return value, end

    def check_bindings(self, bindings):
        paths = [pointer_tokens(b.pointer) for b in bindings]
        for path, binding in zip(paths, bindings):
            if path not in self.ranges or self.values[path] != binding.placeholder:
                raise ValueError('LOCAL_BUNDLE_REFERENCE_PLACEHOLDER_MISMATCH')
            if any(other != path and other[:len(path)] == path for other in paths):
                raise ValueError('LOCAL_BUNDLE_REFERENCE_POSITION_OVERLAP')

    def rewrite(self, bindings, resolve):
        self.check_bindings(bindings)
        edits, receipts = [], []
        for binding in bindings:
            start, end = self.ranges[pointer_tokens(binding.pointer)]
            replacement = resolve(binding)
            encoded = json.dumps(replacement, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
            edits.append((start, end, encoded))
            receipts.append({'binding':binding.model_dump(mode='json'), 'replacement':replacement,
                             'original_token':self.text[start:end]})
        text = self.text
        for start, end, replacement in sorted(edits, reverse=True):
            text = text[:start] + replacement + text[end:]
        transformed = LocalJsonDocument(text.encode('utf-8'))
        start, end = transformed.ranges[('content',)]
        return transformed.value, text[start:end], receipts
