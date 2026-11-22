import re


def part(parts, code):
    return [p for p in parts if p['code'] == code][0]


def first_dxf(files, needle):
    return [k for k in sorted(files) if needle in k][0]


def drop_first_circle(text, layer_prefix):
    """Remove the first CIRCLE entity on a layer starting with layer_prefix."""
    lines = text.split('\n')
    for i in range(0, len(lines) - 3, 2):
        if lines[i] == '0' and lines[i + 1] == 'CIRCLE' and lines[i + 2] == '8' and lines[i + 3].startswith(layer_prefix):
            j = i + 2
            while not (lines[j] == '0' and j % 2 == 0):
                j += 2
            return '\n'.join(lines[:i] + lines[j:])
    raise ValueError('no circle on ' + layer_prefix)


def shift_first_part(text, dx, dy):
    """Move the first contour polyline on the sheet (and nothing else) by (dx, dy)."""
    lines = text.split('\n')
    for i in range(0, len(lines) - 3, 2):
        if lines[i] == '0' and lines[i + 1] == 'POLYLINE' and lines[i + 3].startswith('10_KONTUR'):
            j = i
            while not (lines[j] == '0' and lines[j + 1] == 'SEQEND'):
                if lines[j] == '0' and lines[j + 1] == 'VERTEX':
                    k = j + 2
                    while lines[k] != '0':
                        if lines[k] == '10': lines[k + 1] = '%.3f' % (float(lines[k + 1]) + dx)
                        if lines[k] == '20': lines[k + 1] = '%.3f' % (float(lines[k + 1]) + dy)
                        k += 2
                    j = k
                else:
                    j += 2
            return '\n'.join(lines)
    raise ValueError('no contour')
