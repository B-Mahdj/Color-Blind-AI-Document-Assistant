"""A bounded palette editor for flat-color bitmap figures, never whole-page rasterization.

Only dominant chromatic colors are offered as targets. Photographs, gradients,
transparency and masks remain protected. Every occurrence of a selected color in
one image (including its legend) changes together. The vision reviewer must still
establish that these colors encode categories rather than physical measurements.
"""

import numpy as np
from PIL import Image
from pypdf.generic import DecodedStreamObject, NameObject, NumberObject


def palette(image):
    pixels = np.asarray(image.convert('RGB'))
    sample = pixels[::max(1, image.height // 900), ::max(1, image.width // 900)].reshape(-1, 3)
    chromatic = np.ptp(sample.astype(int), axis=1) > 24
    values = sample[chromatic]
    if len(values) < 30:
        return []
    # JPEG charts spread a solid ink over neighboring RGB values. Count coarse
    # bins, then use an actual representative color from each selected bin.
    bins = (values.astype(int) // 16).astype(np.uint8)
    colors, inverse, counts = np.unique(bins, axis=0, return_inverse=True, return_counts=True)
    order = np.argsort(-counts)
    selected = []
    for index in order:
        if counts[index] < max(8, len(values) * .003):
            break
        color = np.rint(np.median(values[inverse == index], axis=0)).astype(int)
        if not any(np.max(np.abs(color.astype(int) - c)) <= 12 for c in selected):
            selected.append(color.astype(int))
        if len(selected) == 24:
            break
    if not selected:
        return []
    distance = np.full(len(values), 1000)
    for color in selected:
        distance = np.minimum(distance, np.max(np.abs(values.astype(int) - color), axis=1))
    if np.mean(distance <= 12) < .8 or np.mean(distance <= 2) < .5:
        return []  # Continuous tones are not categorical palette targets.
    return [tuple(int(c) for c in color) for color in selected]


def inspect_image(page, obj, names, stream_path, index, matrix, bbox, data):
    from .pdf import Element
    space = obj.get('/ColorSpace')
    space = space.get_object() if hasattr(space, 'get_object') else space
    if isinstance(space, (list, tuple)) and str(space[0]) == '/Indexed':
        space = space[1]
    if str(space) not in {'/DeviceRGB', '/DeviceGray'}:
        return 'Bitmap color profile requires a dedicated color-managed conversion.'
    if obj.get('/ImageMask') or obj.get('/SMask') or obj.get('/Mask'):
        return 'Masked or transparent bitmap.'
    if int(obj['/Width']) * int(obj['/Height']) > 16_000_000:
        return 'Bitmap exceeds the 16 megapixel processing limit.'
    if min(bbox[2]-bbox[0], bbox[3]-bbox[1]) < 24:
        return 'Small bitmap or decorative image.'
    try:
        image = page.images[list(names)].image.convert('RGB')
        colors = palette(image)
    except (ValueError, OSError, KeyError, NotImplementedError):
        return 'Bitmap decoding is unsupported.'
    if not colors:
        return 'Bitmap has no stable flat-color palette (photo, gradient, or neutral image).'
    identifier = f'p{data.number}-i{len(data.images)+1:03d}'
    ids = []
    for i, color in enumerate(colors, 1):
        target = f'{identifier}-c{i:02d}'
        ids.append(target)
        data.elements.append(Element(target, index, bbox, [], tuple(c/255 for c in color), None, 0, 1,
                                     matrix, stream_path, kind='raster_palette', image_id=identifier))
    data.images[identifier] = {'id': identifier, 'bbox': bbox, 'width': image.width, 'height': image.height,
                               'palette_ids': ids, 'names': names, 'image': image, 'colors': colors,
                               'stream_path': stream_path, 'paint_index': index}
    return None


def recolor_image(image, mappings, source_palette):
    """Recolor disjoint source masks with white-edge antialiasing preserved.

    Classify every pixel from the original once, so replacements cannot cascade.
    Neutral pixels and all unmatched pixels remain byte-identical.
    """
    source = np.asarray(image.convert('RGB'))
    pixels = source.astype(np.float32)
    best = np.full(source.shape[:2], np.inf, dtype=np.float32)
    owner = np.full(source.shape[:2], -1, dtype=np.int16)
    # Nearest palette ownership includes unedited colors, protecting nearby series.
    for index, color in enumerate(source_palette):
        distance = np.max(np.abs(pixels - color), axis=2)
        win = distance < best
        best[win], owner[win] = distance[win], index
    chromatic = np.ptp(pixels, axis=2) > 16
    result = source.copy()
    changed = 0
    for old, new in mappings:
        index = source_palette.index(tuple(old))
        mask = (owner == index) & (best <= 12) & chromatic
        # Keep the small source texture/antialias offset rather than flattening it.
        adjusted = np.clip(pixels - np.asarray(old) + np.asarray(new), 0, 255).astype(np.uint8)
        result[mask] = adjusted[mask]
        changed += int(np.count_nonzero(mask))
    if not changed:
        raise ValueError('No bitmap pixels matched the selected palette.')
    return Image.fromarray(result), changed


def image_stream(image):
    """Lossless RGB replacement; dimensions and the original Do placement stay intact."""
    obj = DecodedStreamObject()
    obj.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                NameObject('/Width'): NumberObject(image.width), NameObject('/Height'): NumberObject(image.height),
                NameObject('/ColorSpace'): NameObject('/DeviceRGB'), NameObject('/BitsPerComponent'): NumberObject(8)})
    obj.set_data(image.convert('RGB').tobytes())
    return obj.flate_encode()
