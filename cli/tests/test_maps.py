from io import BytesIO
import unittest

import numpy as np
from PIL import Image, ImageDraw
from pypdf import PdfReader
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from colorblind_assistant.agent import categorical_color_guidance
from colorblind_assistant.colors import luminance
from colorblind_assistant.editor import apply_plan
from colorblind_assistant.models import Action, CorrectionGroup, PagePlan
from colorblind_assistant.pdf import Element, IDENTITY, PageData, TextRun, assert_preserved, fill_intersects, inspect_page, render
from colorblind_assistant.raster import image_palette, native_replacement, recolor_image
from tests.test_extended_pdf import chart, plan_for


class MapTests(unittest.TestCase):
    def test_form_trailing_save_does_not_leak_into_caller(self):
        out = BytesIO()
        pdf = canvas.Canvas(out, pagesize=(850,400))
        pdf.beginForm('map',0,0,400,400)
        pdf.saveState()
        chart(pdf)
        pdf.endForm()
        pdf.doForm('map')
        pdf.translate(420,0)
        chart(pdf)
        pdf.save()
        before = out.getvalue()
        page = PdfReader(BytesIO(before)).pages[0]
        data = inspect_page(page,1)
        self.assertEqual(len(data.targets),4)
        result = apply_plan(page,data,plan_for(data,data.targets[:2]))
        self.assertTrue(result.groups,result.warnings)
        self.assertTrue(np.array_equal(np.asarray(render(before))[:,630:],np.asarray(render(result.pdf))[:,630:]))
        assert_preserved(page,PdfReader(BytesIO(result.pdf)).pages[0])

    def test_restore_underflow_still_fails(self):
        out = BytesIO()
        pdf = canvas.Canvas(out)
        pdf._code.append('Q')
        chart(pdf)
        pdf.save()
        with self.assertRaisesRegex(ValueError,'Unbalanced'):
            inspect_page(PdfReader(BytesIO(out.getvalue())).pages[0],1)

    def test_fill_overlap_excludes_empty_bbox_space_and_holes(self):
        triangle = Element('a',0,(0,0,100,100),[('m',(0,0)),('l',(100,0)),('l',(0,100)),('h',())],
                           (1,0,0),None,0,1,IDENTITY)
        self.assertFalse(fill_intersects(triangle,(75,75,85,85)))
        self.assertTrue(fill_intersects(triangle,(10,10,20,20)))
        ring = Element('b',1,(0,0,100,100),
            [('m',(0,0)),('l',(100,0)),('l',(100,100)),('l',(0,100)),('h',()),
             ('m',(20,20)),('l',(80,20)),('l',(80,80)),('l',(20,80)),('h',())],(1,0,0),None,0,0,IDENTITY)
        self.assertFalse(fill_intersects(ring,(40,40,60,60)))
        self.assertTrue(fill_intersects(ring,(10,10,30,30)))

    def test_fragment_gaps_do_not_claim_text_or_allow_hatches(self):
        pieces = [Element(str(i),i,box,[],(1,0,0),None,0,1,IDENTITY)
                  for i,box in enumerate(((0,0,10,10),(90,90,100,100)))]
        bundle = Element('map',0,(0,0,100,100),[],(1,0,0),None,0,1,IDENTITY,members=pieces)
        self.assertFalse(fill_intersects(bundle,(40,40,60,60)))
        self.assertTrue(fill_intersects(bundle,(2,2,4,4)))
        self.assertFalse(bundle.inventory()['hatch_size_eligible'])

    def test_compressed_map_palette_and_noisy_image_gate(self):
        image = Image.new('RGB',(360,240),'white')
        draw = ImageDraw.Draw(image)
        for i,c in enumerate(((200,20,30),(30,150,50),(60,70,180))):
            draw.rectangle((i*120+5,10,i*120+110,210),fill=c)
            draw.text((i*120+20,70),'Region',fill='black')
        buf=BytesIO()
        image.save(buf,format='JPEG',quality=60)
        colors,mode=image_palette(Image.open(BytesIO(buf.getvalue())).convert('RGB'))
        self.assertEqual(mode,'flat')
        self.assertGreaterEqual(len(colors),3)
        noise=Image.fromarray(np.random.default_rng(4).integers(0,256,(180,180,3),dtype=np.uint8))
        self.assertEqual(image_palette(noise)[0],[])

    def test_ordered_interpolation_preserves_gradient_and_neutral_labels(self):
        gradient=np.zeros((20,101,3),dtype=np.uint8)
        gradient[:]=np.array([(200-i,20+i,30) for i in range(101)])
        gradient[5:8,40:50]=0
        image=Image.fromarray(gradient)
        mappings=[((200,20,30),(220,240,255)),((100,120,30),(10,30,70))]
        changed,count=recolor_image(image,mappings,[(200,20,30),(100,120,30)],ordered=True)
        self.assertGreater(count,1000)
        pixels=np.asarray(changed)
        self.assertTrue(np.array_equal(pixels[5:8,40:50],gradient[5:8,40:50]))
        levels=[luminance(c/255) for c in pixels[0]]
        self.assertTrue(all(a>b for a,b in zip(levels,levels[1:])))
        self.assertGreater(len(np.unique(pixels[0],axis=0)),90)

    def test_ordered_scale_requires_monotonic_target_palette(self):
        image=Image.new('RGB',(240,150),(200,20,30))
        ImageDraw.Draw(image).rectangle((120,0,239,149),fill=(20,180,40))
        out=BytesIO();pdf=canvas.Canvas(out,pagesize=(400,400))
        pdf.drawImage(ImageReader(image),40,50,width=240,height=150)
        pdf.save();page=PdfReader(BytesIO(out.getvalue())).pages[0];data=inspect_page(page,1)
        ids=[e.id for e in data.targets]
        group=CorrectionGroup(id='scale',reason='Existing ascending numeric key',evidence_text_ids=[],
            association='image_ordered',palette_order=ids,legend_ids=[],uncertain=False,
            actions=[Action(kind='recolor',target_ids=[ids[0]],channel='fill',color='#DCEFFF'),
                     Action(kind='recolor',target_ids=[ids[1]],channel='fill',color='#102050')])
        result=apply_plan(page,data,PagePlan(groups=[group],warnings=[]))
        self.assertTrue(result.groups,result.warnings)
        assert_preserved(page,PdfReader(BytesIO(result.pdf)).pages[0])
        group.palette_order=ids[::-1]
        rejected=apply_plan(page,data,PagePlan(groups=[group],warnings=[]))
        self.assertFalse(rejected.groups)
        self.assertTrue(any('strictly darker' in w for w in rejected.warnings))

    def test_native_cmyk_untouched_pixels_remain_identical(self):
        native=Image.new('CMYK',(100,80),(0,190,200,10))
        ImageDraw.Draw(native).rectangle((0,0,20,79),fill=(0,0,0,255))
        display=native.convert('RGB');recolored=display.copy()
        ImageDraw.Draw(recolored).rectangle((50,0,99,79),fill=(0,90,156))
        result=native_replacement({'native_image':native,'image':display,'profile':None},recolored)
        self.assertEqual(result.mode,'CMYK')
        self.assertTrue(np.array_equal(np.asarray(result)[:,:50],np.asarray(native)[:,:50]))
        self.assertFalse(np.array_equal(np.asarray(result)[:,50:],np.asarray(native)[:,50:]))

    def test_external_vector_legend_and_bitmap_change_together(self):
        image=Image.new('RGB',(120,100),(200,20,20))
        out=BytesIO();pdf=canvas.Canvas(out,pagesize=(400,400))
        pdf.drawImage(ImageReader(image),40,100,width=120,height=100)
        pdf.setFillColorRGB(200/255,20/255,20/255);pdf.rect(40,50,12,12,fill=1,stroke=0)
        pdf.setFillColorRGB(0,0,0);pdf.drawString(60,50,'Category A');pdf.save()
        page=PdfReader(BytesIO(out.getvalue())).pages[0];data=inspect_page(page,1)
        result=apply_plan(page,data,plan_for(data,data.targets))
        self.assertTrue(result.groups,result.warnings)
        self.assertEqual(len(result.groups[0]['changes']),2)
        assert_preserved(page,PdfReader(BytesIO(result.pdf)).pages[0])

    def test_large_palette_guidance_respects_black_labels_and_small_swatches(self):
        elements=[];texts=[]
        for i in range(9):
            e=Element(str(i),i,(i*25,0,i*25+20,20),[],(.8,.1+i*.06,.1),None,0,1,IDENTITY)
            elements.append(e);texts.append(TextRun('t'+str(i),'A',(i*25+3,5,i*25+10,10),(0,0,0)))
        data=PageData(1,400,400,elements,texts)
        guide=categorical_color_guidance(data)
        self.assertEqual(len(guide),9)
        self.assertTrue(all(g['suggested_hatch'] is None for g in guide))

