from io import BytesIO
import unittest

import numpy as np
from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter
from pypdf.generic import ArrayObject, ContentStream, DictionaryObject, FloatObject, NameObject, NumberObject
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from colorblind_assistant.editor import _mapping_note, _place, _segment_crosses, apply_plan
from colorblind_assistant.models import Action, CorrectionGroup, PagePlan
from colorblind_assistant.pdf import Element, IDENTITY, PageData, TextRun, assert_preserved, inspect_page, render, single_page_bytes
from colorblind_assistant.raster import palette, recolor_image


def chart(pdf):
    pdf.setFillColorRGB(.8, .1, .1)
    pdf.rect(50, 100, 50, 100, fill=1, stroke=0)
    pdf.rect(50, 60, 12, 12, fill=1, stroke=0)
    pdf.setFillColorRGB(0, 0, 0)
    pdf.drawString(70, 62, 'Group X')


def plan_for(data, targets, association='legend'):
    return PagePlan(groups=[CorrectionGroup(id='chart', reason='Existing source legend',
        evidence_text_ids=[data.text[0].id] if data.text else [], association=association,
        legend_ids=[targets[-1].id] if association == 'legend' else [], uncertain=False,
        actions=[Action(kind='recolor', target_ids=[e.id for e in targets], channel='fill', color='#005A9C')])], warnings=[])


class ExtendedPDFTests(unittest.TestCase):
    def test_nested_reused_form_is_edited_per_invocation(self):
        out = BytesIO()
        pdf = canvas.Canvas(out, pagesize=(850, 400))
        pdf.beginForm('inner', 0, 0, 400, 400)
        chart(pdf)
        pdf.endForm()
        pdf.beginForm('outer', 0, 0, 400, 400)
        pdf.doForm('inner')
        pdf.endForm()
        pdf.doForm('outer')
        pdf.saveState()
        pdf.translate(420, 0)
        pdf.doForm('outer')
        pdf.restoreState()
        pdf.save()
        original = out.getvalue()
        page = PdfReader(BytesIO(original)).pages[0]
        data = inspect_page(page, 1)
        self.assertEqual(len(data.targets), 4)
        self.assertEqual(len(data.targets[0].stream_path), 2)
        source_snapshot = single_page_bytes(page)
        result = apply_plan(page, data, plan_for(data, data.targets[:2]))
        self.assertTrue(result.groups, result.warnings)
        before, after = np.array(render(original)), np.array(render(result.pdf))
        self.assertTrue(np.array_equal(before[:, 630:], after[:, 630:]))
        self.assertFalse(np.array_equal(before[:, :600], after[:, :600]))
        self.assertEqual(single_page_bytes(page), source_snapshot)
        assert_preserved(page, PdfReader(BytesIO(result.pdf)).pages[0])

    def test_links_and_clipping_are_preserved_during_edit(self):
        out = BytesIO()
        pdf = canvas.Canvas(out, pagesize=(400, 400))
        pdf.linkURL('https://example.org/source', (20, 350, 100, 370))
        path = pdf.beginPath()
        path.rect(0, 0, 80, 300)
        pdf.saveState()
        pdf.clipPath(path, stroke=0)
        chart(pdf)
        pdf.restoreState()
        pdf.save()
        page = PdfReader(BytesIO(out.getvalue())).pages[0]
        data = inspect_page(page, 1)
        self.assertTrue(data.supported, data.warnings)
        self.assertEqual(data.targets[0].bbox, (50, 100, 80, 200))
        result = apply_plan(page, data, plan_for(data, data.targets))
        self.assertTrue(result.groups, result.warnings)
        after = PdfReader(BytesIO(result.pdf)).pages[0]
        assert_preserved(page, after)
        pixels = np.array(render(result.pdf))
        self.assertTrue(np.all(pixels[300:450, 122:150] == 255))
        self.assertEqual(after['/Annots'][0].get_object()['/A']['/URI'], 'https://example.org/source')

    def test_opaque_graphics_state_allowed_transparency_scoped(self):
        out = BytesIO()
        pdf = canvas.Canvas(out, pagesize=(400, 400))
        chart(pdf)
        pdf.saveState()
        pdf.setFillAlpha(.4)
        pdf.setFillColorRGB(0, 1, 0)
        pdf.rect(250, 200, 50, 50, fill=1, stroke=0)
        pdf.restoreState()
        pdf.save()
        page = PdfReader(BytesIO(out.getvalue())).pages[0]
        data = inspect_page(page, 1)
        self.assertTrue(data.supported)
        self.assertEqual(len(data.targets), 2)
        self.assertEqual(len(data.protected), 1)
        result = apply_plan(page, data, plan_for(data, data.targets))
        self.assertTrue(result.groups, result.warnings)
        a, b = np.array(render(out.getvalue())), np.array(render(result.pdf))
        self.assertTrue(np.array_equal(a[220:310, 370:460], b[220:310, 370:460]))

    def test_hidden_paints_are_filtered_and_fragments_compacted(self):
        out = BytesIO()
        pdf = canvas.Canvas(out, pagesize=(400, 400))
        pdf.drawString(20, 350, 'Series')
        pdf.setStrokeColorRGB(.8, .1, .1)
        for i in range(1500):
            x = 40 + (i % 75) * 4
            y = 60 + (i // 75) * 8
            pdf.line(x, y, x+2, y+1)
        pdf.rect(600, 600, 20, 20, fill=1)
        pdf.save()
        data = inspect_page(PdfReader(BytesIO(out.getvalue())).pages[0], 1)
        self.assertLess(len(data.targets), 50)
        self.assertEqual(sum(len(e.members) or 1 for e in data.targets), 1500)
        self.assertIn('path_samples', data.targets[0].inventory())

    def test_bitmap_palette_edit_is_lossless_and_instance_local(self):
        image = Image.new('RGB', (240, 160), 'white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((10, 20, 65, 110), fill=(204, 26, 26))
        draw.rectangle((90, 50, 145, 110), fill=(26, 153, 38))
        draw.rectangle((10, 130, 20, 140), fill=(204, 26, 26))
        draw.text((25, 130), 'Group X', fill='black')
        draw.line((0, 115, 240, 115), fill='black', width=2)
        out = BytesIO()
        pdf = canvas.Canvas(out, pagesize=(550, 230))
        pdf.drawString(20, 210, 'Category comparison')
        pdf.drawImage(ImageReader(image), 10, 20, width=240, height=160)
        pdf.drawImage(ImageReader(image), 290, 20, width=240, height=160)
        pdf.save()
        page = PdfReader(BytesIO(out.getvalue())).pages[0]
        data = inspect_page(page, 1)
        self.assertEqual(len(data.images), 2, data.warnings)
        first = next(iter(data.images))
        targets = [e for e in data.targets if e.image_id == first and e.fill[0] > .7]
        result = apply_plan(page, data, plan_for(data, targets, 'image_palette'))
        self.assertTrue(result.groups, result.warnings)
        after = PdfReader(BytesIO(result.pdf)).pages[0]
        assert_preserved(page, after)
        a, b = np.array(render(out.getvalue())), np.array(render(result.pdf))
        self.assertTrue(np.array_equal(a[:, 435:], b[:, 435:]))
        self.assertFalse(np.array_equal(a[:, :400], b[:, :400]))
        changed, _ = recolor_image(image, [((204,26,26), (0,90,156))], [(204,26,26), (26,153,38)])
        old, new = np.array(image), np.array(changed)
        untouched = np.any(old != (204,26,26), axis=2)
        self.assertTrue(np.array_equal(old[untouched], new[untouched]))
        self.assertTrue(np.all(new[130:140, 10:20] == (0,90,156)))

    def test_gradients_are_not_offered_as_categorical_bitmaps(self):
        x = np.arange(256, dtype=np.uint8)
        gradient = np.stack(np.broadcast_arrays(x, 255-x, np.zeros((100, 256), dtype=np.uint8)), axis=-1)
        self.assertEqual(palette(Image.fromarray(gradient)), [])

    def test_placement_uses_curve_paths_and_accepts_french_labels(self):
        self.assertFalse(_segment_crosses((20, 70, 40, 90), (0,0), (100,100), 2))
        self.assertTrue(_segment_crosses((20, 20, 40, 40), (0,0), (100,100), 2))
        curve = Element('curve', 0, (20,20,380,380), [('m',(20,20)), ('l',(380,380))],
                        None, (1,0,0), 1, 1, IDENTITY)
        data = PageData(1,400,400,[curve],[])
        label = _place('Drosophiles étudiées', (100,200,180,220), data, [])
        self.assertLess(label['bbox'][3], 380)

    def test_overlapping_curve_boxes_do_not_claim_same_label(self):
        curves = [Element(str(i),i,(20,20,380,380),[],None,color,1,1,IDENTITY)
                  for i,color in enumerate(((1,0,0),(0,0,1)))]
        texts = [TextRun('t1','bleue',(80,80,120,90),(0,0,0)), TextRun('t2','rouge',(150,80,190,90),(0,0,0))]
        data = PageData(1,400,400,curves,texts)
        group = CorrectionGroup(id='curves',reason='Source labels',evidence_text_ids=['t1','t2'],
            association='direct_labels',legend_ids=[],uncertain=False,
            actions=[Action(kind='recolor', target_ids=['0'],channel='stroke',color='#A84400')])
        changes = [{'kind':'recolor','target_id':'0','before':'#FF0000','after':'#A84400'},
                   {'kind':'recolor','target_id':'1','before':'#0000FF','after':'#6B3C91'}]
        note = _mapping_note(group,changes,data,{e.id:e for e in curves})
        self.assertIn('red -> orange',note)
        self.assertIn('blue -> purple',note)
        self.assertNotIn('bleue =',note)

    def test_nested_geometry_tampering_is_detected(self):
        out = BytesIO()
        pdf = canvas.Canvas(out)
        pdf.beginForm('plot')
        chart(pdf)
        pdf.endForm()
        pdf.doForm('plot')
        pdf.save()
        before = PdfReader(BytesIO(out.getvalue())).pages[0]
        writer = PdfWriter()
        after = writer.add_page(before)
        form = next(iter(after['/Resources']['/XObject'].values())).get_object()
        stream = ContentStream(form, writer)
        for args, op in stream.operations:
            if op == b're':
                args[0] = NumberObject(999)
                break
        replacement = stream
        for k,v in form.items():
            if k not in {'/Length','/Filter','/DecodeParms'}:
                replacement[k] = v
        name = next(iter(after['/Resources']['/XObject']))
        after['/Resources']['/XObject'][name] = writer._add_object(replacement)
        with self.assertRaisesRegex(ValueError, 'geometry changed'):
            assert_preserved(before, after)

    def test_32_curves_and_legends_accept_distinct_encodings(self):
        import math
        out = BytesIO()
        pdf = canvas.Canvas(out, pagesize=(850, 650))
        for i in range(32):
            pdf.setStrokeColorRGB(.55 + i*.01, .08, .12)
            path = pdf.beginPath()
            for j in range(40):
                x, y = 70+j*18, 300+i*3+70*math.sin(j*.12+i*.07)
                (path.moveTo if j == 0 else path.lineTo)(x, y)
            pdf.drawPath(path)
            x, y = 40+(i % 8)*100, 180-(i // 8)*25
            pdf.line(x, y, x+20, y)
            pdf.drawString(x+25, y-3, f'Sample {i+1}')
        pdf.save()
        page = PdfReader(BytesIO(out.getvalue())).pages[0]
        data = inspect_page(page, 1)
        colors = ['#005A9C','#A84400','#6B3C91','#303030','#365E30','#754B00','#007070','#733A60']
        styles = [None,'dashed','dotted','dashdot']
        actions, legends = [], []
        for i in range(32):
            ids = [e.id for e in data.targets[2*i:2*i+2]]
            legends.append(ids[-1])
            actions.append(Action(kind='recolor', target_ids=ids, channel='stroke', color=colors[i % 8]))
            if styles[i // 8]:
                actions.append(Action(kind='dash', target_ids=ids, style=styles[i // 8]))
        plan = PagePlan(groups=[CorrectionGroup(id='32-series', reason='Match the existing 32-item legend',
             evidence_text_ids=[t.id for t in data.text], association='legend', legend_ids=legends,
             uncertain=False, actions=actions)], warnings=[])
        result = apply_plan(page, data, plan)
        self.assertTrue(result.groups, result.warnings)
        self.assertEqual(sum(c['kind']=='recolor' for c in result.groups[0]['changes']), 64)
        self.assertEqual(sum(c['kind']=='dash' for c in result.groups[0]['changes']), 48)
        assert_preserved(page, PdfReader(BytesIO(result.pdf)).pages[0])


if __name__ == '__main__':
    unittest.main()
