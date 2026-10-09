"""Diagnosi geometrica su carte sintetiche: nessun dato personale."""

import unittest

from PIL import Image, ImageDraw

from legal_ocr.motore.geometria_identita import prepara_geometria_identita

try:
    import cv2
    import numpy as np
except ImportError:
    cv2 = np = None


@unittest.skipIf(cv2 is None, 'OpenCV richiesto per il riscontro geometrico')
class IdentityGeometryTest(unittest.TestCase):
    def card(self):
        image = Image.new('RGB', (800, 600), 'white')
        draw = ImageDraw.Draw(image)
        draw.rectangle((110, 130, 690, 470), outline='black', width=4)
        for y in range(185, 420, 45):
            draw.line((145, y, 625, y), fill='black', width=3)
        for x, y in ((8, 8), (780, 8), (8, 580), (780, 580)):
            draw.rectangle((x, y, x + 9, y + 9), fill='red')
        return image

    def project(self, image):
        source = np.asarray(((110, 130), (690, 130), (690, 470), (110, 470)), dtype='float32')
        destination = np.asarray(((170, 95), (650, 150), (710, 495), (80, 455)), dtype='float32')
        matrix = cv2.getPerspectiveTransform(source, destination)
        return Image.fromarray(cv2.warpPerspective(np.asarray(image), matrix, image.size,
                                                  borderValue=(255, 255, 255)))

    def test_straight_card_remains_byte_identical(self):
        with self.card() as source:
            original = source.tobytes()
            result = prepara_geometria_identita(source)
            try:
                self.assertFalse(result.applicata)
                self.assertIsNot(result.immagine, source)
                self.assertEqual(result.immagine.tobytes(), original)
                self.assertEqual(source.tobytes(), original)
            finally:
                result.immagine.close()

    def test_complete_perspective_is_corrected_without_cropping_canvas(self):
        with self.card() as original:
            source = self.project(original)
        # Segni fuori dalla carta: anche questi devono rimanere visibili.
        draw = ImageDraw.Draw(source)
        for x, y in ((12, 12), (775, 12), (12, 575), (775, 575)):
            draw.rectangle((x, y, x + 10, y + 10), fill='red')
        before = source.tobytes()
        result = prepara_geometria_identita(source)
        try:
            self.assertTrue(result.applicata, result.audit)
            self.assertEqual(len(result.quadrilatero), 4)
            self.assertEqual(source.tobytes(), before)
            pixels = np.asarray(result.immagine)
            red = ((pixels[:, :, 0] > 200) & (pixels[:, :, 1] < 80) & (pixels[:, :, 2] < 80)).astype('uint8')
            count, _, stats, _ = cv2.connectedComponentsWithStats(red)
            self.assertGreaterEqual(sum(area >= 15 for *_, area in stats[1:count]), 4)
        finally:
            result.immagine.close()
            source.close()

    def test_missing_border_is_not_reconstructed(self):
        with self.card() as source:
            ImageDraw.Draw(source).rectangle((680, 125, 699, 477), fill='white')
            before = source.tobytes()
            result = prepara_geometria_identita(source)
            try:
                self.assertFalse(result.applicata)
                self.assertEqual(result.immagine.tobytes(), before)
            finally:
                result.immagine.close()

    def test_different_panel_angles_forbid_global_warp(self):
        with self.card() as source:
            draw = ImageDraw.Draw(source)
            draw.rectangle((130, 150, 670, 448), fill='white')
            for y in range(190, 420, 45):
                draw.line((140, y, 370, y + 16), fill='black', width=3)
                draw.line((420, y + 15, 650, y), fill='black', width=3)
            projected = self.project(source)
        before = projected.tobytes()
        result = prepara_geometria_identita(projected)
        try:
            self.assertFalse(result.applicata)
            self.assertIsNone(result.angolo_gradi)
            self.assertEqual(result.immagine.tobytes(), before)
        finally:
            result.immagine.close()
            projected.close()

    def test_two_cards_are_not_rectified_as_one(self):
        source = Image.new('RGB', (800, 600), 'white')
        draw = ImageDraw.Draw(source)
        for top in (40, 340):
            draw.rectangle((160, top, 640, top + 230), outline='black', width=4)
            for y in range(top + 35, top + 200, 40):
                draw.line((195, y, 600, y + 8), fill='black', width=3)
        result = prepara_geometria_identita(source)
        try:
            self.assertFalse(result.applicata)
            self.assertIn('più riquadri distinti', result.passaggi[0])
            self.assertEqual(result.immagine.tobytes(), source.tobytes())
        finally:
            result.immagine.close()
            source.close()

    def test_missing_corner_is_not_invented(self):
        with self.card() as source:
            ImageDraw.Draw(source).rectangle((98, 120, 155, 175), fill='white')
            result = prepara_geometria_identita(source)
            try:
                self.assertFalse(result.applicata)
                self.assertEqual(result.immagine.tobytes(), source.tobytes())
            finally:
                result.immagine.close()

    def test_measured_common_inclination_is_corrected_once(self):
        with self.card() as original:
            source = original.rotate(6, resample=Image.Resampling.BICUBIC, expand=True, fillcolor='white')
        before = source.tobytes()
        first = prepara_geometria_identita(source)
        second = prepara_geometria_identita(source)
        try:
            self.assertTrue(first.applicata, first.audit)
            self.assertAlmostEqual(abs(first.angolo_gradi), 6, delta=.5)
            self.assertEqual(first.immagine.tobytes(), second.immagine.tobytes())
            self.assertEqual(source.tobytes(), before)
        finally:
            first.immagine.close()
            second.immagine.close()
            source.close()

    def test_uniform_source_has_no_geometry_to_invent(self):
        with Image.new('RGB', (800, 600), 'white') as source:
            result = prepara_geometria_identita(source)
            try:
                self.assertFalse(result.applicata)
                self.assertEqual(result.quadrilatero, ())
                self.assertEqual(result.immagine.tobytes(), source.tobytes())
            finally:
                result.immagine.close()


if __name__ == '__main__':
    unittest.main()
