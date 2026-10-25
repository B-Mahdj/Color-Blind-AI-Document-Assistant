"""Run with python -m unittest discover -s colorblind-pdf-fixer/scripts."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from PIL import Image
from pypdf import PdfWriter
from pypdf.generic import ArrayObject, DictionaryObject, DecodedStreamObject, NameObject, NumberObject

from extract_images import extract_images, main


def image_object(writer, color_space, data):
    image = DecodedStreamObject()
    image.update({NameObject(key): value for key, value in {
        "/Type": NameObject("/XObject"), "/Subtype": NameObject("/Image"),
        "/Width": NumberObject(1), "/Height": NumberObject(1),
        "/BitsPerComponent": NumberObject(8), "/ColorSpace": NameObject(color_space),
    }.items()})
    image.set_data(data)
    return writer._add_object(image)


class ExtractionTests(unittest.TestCase):
    def test_nested_shared_mask_and_annotation_images(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "input.pdf"
            writer = PdfWriter()
            page = writer.add_blank_page(100, 100)
            rgb = image_object(writer, "/DeviceRGB", b"\xff\x00\x00")
            mask = image_object(writer, "/DeviceGray", b"\x80")
            rgb.get_object()[NameObject("/SMask")] = mask
            cmyk = image_object(writer, "/DeviceCMYK", b"\x00\xff\xff\x00")
            form = DecodedStreamObject()
            form.set_data(b"")
            form[NameObject("/Subtype")] = NameObject("/Form")
            form_ref = writer._add_object(form)
            form[NameObject("/Resources")] = DictionaryObject({
                NameObject("/XObject"): DictionaryObject({
                    NameObject("/Nested"): rgb, NameObject("/Cycle"): form_ref,
                }),
            })
            page[NameObject("/Resources")] = DictionaryObject({
                NameObject("/XObject"): DictionaryObject({
                    NameObject("/Form"): form_ref, NameObject("/Shared"): rgb,
                }),
            })
            annotation = DictionaryObject({
                NameObject("/Subtype"): NameObject("/Stamp"),
                NameObject("/AP"): DictionaryObject({NameObject("/N"): cmyk}),
            })
            page[NameObject("/Annots")] = ArrayObject([writer._add_object(annotation)])
            writer.write(source)
            original = source.read_bytes()
            paths = extract_images(source)
            self.assertEqual(len(paths), 3)
            self.assertEqual(len(set(paths)), 3)
            pixels = []
            for path in paths:
                with Image.open(path) as image:
                    self.assertEqual(image.size, (1, 1))
                    pixels.append(image.getpixel((0, 0)))
            self.assertIn((255, 0, 0, 128), pixels)
            self.assertIn(128, pixels)
            self.assertIn((255, 0, 0), pixels)
            self.assertEqual(source.read_bytes(), original)
            with self.assertRaises(FileExistsError):
                extract_images(source)

    def test_empty_encrypted_and_missing(self):
        with TemporaryDirectory() as directory:
            source = Path(directory) / "empty.pdf"
            writer = PdfWriter()
            writer.add_blank_page(100, 100)
            writer.write(source)
            self.assertEqual(extract_images(source), [])
            writer.encrypt("password")
            writer.write(source)
            with self.assertRaisesRegex(ValueError, "Encrypted"):
                extract_images(source, Path(directory) / "encrypted")
            self.assertEqual(main([str(source.with_name("missing.pdf"))]), 1)


if __name__ == "__main__":
    unittest.main()
