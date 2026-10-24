"""A bounded palette editor for flat-color bitmap figures, never whole-page rasterization.

Only dominant chromatic colors are offered as targets. Continuous palettes require
an explicitly ordered scale. Every occurrence of a selected color in one image
(including its legend) changes together. Unmatched and neutral pixels are retained.
"""

import numpy as np
from io import BytesIO
from PIL import Image, ImageCms, ImageFilter
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


def image_palette(image):
    """Estimate compressed ink colors without filtering the exported image."""
    colors = palette(image)
    if colors:
        return colors, 'flat'
    filtered = image.filter(ImageFilter.MedianFilter(3))
    colors = palette(filtered)
    if colors:
        return colors, 'flat'
    pixels = np.asarray(filtered)[::max(1, image.height//600), ::max(1, image.width//600)].reshape(-1, 3)
    values = pixels[np.ptp(pixels.astype(int), axis=1) > 24]
    if len(values) < 30:
        return [], 'protected'
    quantized = Image.fromarray(values.reshape(-1, 1, 3)).quantize(colors=24, method=Image.Quantize.MEDIANCUT, kmeans=3)
    candidates = np.asarray(quantized.getpalette()).reshape(-1, 3)
    counts = np.bincount(np.asarray(quantized).reshape(-1), minlength=len(candidates))
    candidates = candidates[counts >= max(8, len(values)*.003)]
    if len(candidates) < 2:
        return [], 'protected'
    distances = np.full(len(values), 1000)
    for color in candidates:
        distances = np.minimum(distances, np.max(np.abs(values.astype(int)-color), axis=1))
    if np.mean(distances <= 12) < .8:
        return [], 'protected'
    mode = 'flat' if np.mean(distances <= 2) >= .5 else 'ordered_only'
    return [tuple(map(int, color)) for color in candidates], mode


def inspect_image(page, obj, names, stream_path, index, matrix, bbox, data):
    from .pdf import Element
    space = obj.get('/ColorSpace')
    space = space.get_object() if hasattr(space, 'get_object') else space
    profile = None
    indexed = isinstance(space, (list, tuple)) and str(space[0]) == '/Indexed'
    if indexed:
        if str(space[1]) not in {'/DeviceRGB', '/DeviceGray'}:
            return 'Unsupported indexed bitmap color space.'
        space = NameObject('/DeviceRGB')
    if isinstance(space, (list, tuple)) and str(space[0]) == '/ICCBased':
        profile = space[1].get_object().get_data()
    elif str(space) not in {'/DeviceRGB', '/DeviceGray', '/DeviceCMYK'}:
        return 'Unsupported bitmap color space.'
    if obj.get('/ImageMask') or obj.get('/SMask') or obj.get('/Mask'):
        return 'Masked or transparent bitmap.'
    if int(obj['/Width']) * int(obj['/Height']) > 16_000_000:
        return 'Bitmap exceeds the 16 megapixel processing limit.'
    if min(bbox[2]-bbox[0], bbox[3]-bbox[1]) < 24:
        return 'Small bitmap or decorative image.'
    try:
        native = page.images[list(names)].image.copy()
        if indexed:
            native = native.convert('RGB')
        image = (ImageCms.profileToProfile(native, ImageCms.ImageCmsProfile(BytesIO(profile)),
                                          ImageCms.createProfile('sRGB'), outputMode='RGB')
                 if profile else native.convert('RGB'))
        colors, mode = image_palette(image)
    except (ValueError, OSError, KeyError, NotImplementedError, ImageCms.PyCMSError):
        return 'Bitmap decoding is unsupported.'
    if not colors:
        return 'Bitmap lacks a sufficiently covered palette; photographic mixtures or dense scan noise remain protected.'
    identifier = f'p{data.number}-i{len(data.images)+1:03d}'
    ids = []
    for i, color in enumerate(colors, 1):
        target = f'{identifier}-c{i:02d}'
        ids.append(target)
        data.elements.append(Element(target, index, bbox, [], tuple(c/255 for c in color), None, 0, 1,
                                     matrix, stream_path, kind='raster_palette', image_id=identifier))
    data.images[identifier] = {'id': identifier, 'bbox': bbox, 'width': image.width, 'height': image.height,
                               'palette_ids': ids, 'names': names, 'image': image, 'colors': colors,
                               'native_image': native, 'profile': profile, 'color_space': space, 'palette_mode': mode,
                               'stream_path': stream_path, 'paint_index': index}
    return None


def recolor_image(image, mappings, source_palette, ordered=False):
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
    if ordered:
        # Interpolate along the source key, including its continuous colorbar.
        error = np.full(source.shape[:2], np.inf, dtype=np.float32)
        selected = np.isin(owner, [source_palette.index(tuple(old)) for old, _ in mappings])
        for (old_a, new_a), (old_b, new_b) in zip(mappings, mappings[1:]):
            vector = np.asarray(old_b, dtype=np.float32)-old_a
            length = float(vector @ vector)
            if length == 0:
                raise ValueError('Ordered palette contains duplicate source colors.')
            fraction = np.clip(np.sum((pixels-old_a)*vector, axis=2)/length, 0, 1)
            projected = np.asarray(old_a)+fraction[..., None]*vector
            distance = np.max(np.abs(pixels-projected), axis=2)
            mask = (distance < error) & (distance <= 12) & chromatic & selected
            transformed = np.asarray(new_a)+fraction[..., None]*(np.asarray(new_b)-new_a)
            result[mask] = np.rint(np.clip(transformed[mask], 0, 255)).astype(np.uint8)
            error[mask] = distance[mask]
        changed = int(np.count_nonzero(np.isfinite(error)))
        if not changed:
            raise ValueError('No bitmap pixels matched the ordered scale.')
        return Image.fromarray(result), changed
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


def image_stream(image, color_space=None):
    """Lossless RGB replacement; dimensions and the original Do placement stay intact."""
    obj = DecodedStreamObject()
    obj.update({NameObject('/Type'): NameObject('/XObject'), NameObject('/Subtype'): NameObject('/Image'),
                NameObject('/Width'): NumberObject(image.width), NameObject('/Height'): NumberObject(image.height),
                NameObject('/ColorSpace'): color_space if color_space is not None else NameObject('/DeviceRGB'),
                NameObject('/BitsPerComponent'): NumberObject(8)})
    obj.set_data((image if color_space is not None else image.convert('RGB')).tobytes())
    return obj.flate_encode()


def native_replacement(figure, recolored):
    """Keep unmatched pixels byte-identical in the original image color space."""
    native = figure['native_image']
    changed = np.any(np.asarray(figure['image']) != np.asarray(recolored), axis=2)
    converted = (ImageCms.profileToProfile(recolored, ImageCms.createProfile('sRGB'),
                     ImageCms.ImageCmsProfile(BytesIO(figure['profile'])), outputMode=native.mode)
                 if figure['profile'] else recolored.convert(native.mode))
    pixels = np.array(native)
    pixels[changed] = np.asarray(converted)[changed]
    return Image.fromarray(pixels, mode=native.mode)
