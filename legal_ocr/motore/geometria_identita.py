"""Candidato geometrico locale, solo con bordi e rette realmente riscontrati.

Non riconosce il titolare e non certifica il testo. Il chiamante deve ancora
confrontare la lettura del candidato con quella della fonte preservata.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class GeometriaIdentita:
    immagine: object
    applicata: bool
    audit: tuple[str, ...]
    quadrilatero: tuple[tuple[float, float], ...] = ()
    angolo_gradi: float | None = None

    @property
    def passaggi(self):
        return self.audit


def _angolo(line):
    x1, y1, x2, y2 = line
    return (math.degrees(math.atan2(y2 - y1, x2 - x1)) + 90) % 180 - 90


def _rette(edges, cv2, np):
    lines = cv2.HoughLinesP(edges, 1, np.pi / 720, threshold=40,
                           minLineLength=max(35, min(edges.shape) // 8), maxLineGap=3)
    found = []
    # I binding OpenCV restituiscono N×1×4 oppure N×4 a seconda del runtime.
    segments = () if lines is None else np.asarray(lines).reshape(-1, 4)
    for line in sorted(segments,
                       key=lambda row: -math.hypot(row[2] - row[0], row[3] - row[1])):
        angle = _angolo(line)
        if 20 < abs(angle) < 70:
            continue
        midpoint = ((line[0] + line[2]) / 2, (line[1] + line[3]) / 2)
        if any(math.dist(midpoint, item[1]) < 6 and abs(angle - item[2]) < 1 for item in found):
            continue
        found.append((line, midpoint, angle))
    return found


def _inclinazione(lines):
    # Almeno tre rette distribuite: non le due facce dello stesso bordo.
    horizontal = [(point, angle) for _, point, angle in lines if abs(angle) <= 20]
    if len(horizontal) < 3 or max(p[1] for p, _ in horizontal) - min(p[1] for p, _ in horizontal) < 30:
        return None
    angles = sorted(angle for _, angle in horizontal)
    if angles[-1] - angles[0] > 1.2:
        return None
    return round(angles[len(angles) // 2], 3)


def _quadrilateri(edges, cv2, np):
    contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    distance = cv2.distanceTransform(255 - edges, cv2.DIST_L2, 3)
    height, width = edges.shape
    candidates = []
    for contour in contours:
        area = cv2.contourArea(contour)
        if not .15 * width * height <= area <= .94 * width * height:
            continue
        polygon = cv2.approxPolyDP(contour, .012 * cv2.arcLength(contour, True), True)
        if len(polygon) != 4 or not cv2.isContourConvex(polygon):
            continue
        points = polygon[:, 0].astype('float32')
        center = points.mean(axis=0)
        points = points[np.argsort(np.arctan2(points[:, 1] - center[1], points[:, 0] - center[0]))]
        points = np.roll(points, -int(np.argmin(points.sum(axis=1))), axis=0)
        if any(x < 3 or y < 3 or x > width - 4 or y > height - 4 for x, y in points):
            continue
        lengths = [math.dist(points[i], points[(i + 1) % 4]) for i in range(4)]
        aspect = (lengths[0] + lengths[2]) / (lengths[1] + lengths[3])
        if not .4 <= aspect <= 2.5 or min(lengths) < 60:
            continue
        supported = True
        for index in range(4):
            sample = np.linspace(points[index], points[(index + 1) % 4], math.ceil(lengths[index]))
            values = distance[sample[:, 1].round().astype(int), sample[:, 0].round().astype(int)]
            # Nessuna ricostruzione di un lato mancante o interrotto.
            if np.mean(values <= 2.5) < .985 or np.max(values) > 4:
                supported = False
                break
        if supported:
            candidates.append((area, points))
    candidates.sort(key=lambda item: -item[0])
    distinct = []
    for _, polygon in candidates:
        if not any(all(cv2.pointPolygonTest(outer, tuple(map(float, point)), True) >= -4
                       for point in polygon) for outer in distinct):
            distinct.append(polygon)
    return distinct


def _rette_rettificate(lines, polygon, matrix, cv2, np):
    inner, residuals = [], []
    for line, midpoint, _ in lines:
        if cv2.pointPolygonTest(polygon, midpoint, True) <= 10:
            continue
        mapped = cv2.perspectiveTransform(np.asarray(line, dtype='float32').reshape(1, 2, 2), matrix)[0]
        angle = abs(_angolo(mapped.reshape(4)))
        residuals.append(min(angle, 90 - angle))
        inner.append(midpoint)
    return (len(inner) >= 3 and max(p[1] for p in inner) - min(p[1] for p in inner) >= 30
            and max(residuals) <= 1.5)


def prepara_geometria_identita(immagine) -> GeometriaIdentita:
    """Una diagnosi e al massimo una trasformazione, su copia dell'intera tela.

    Pieghe o pannelli non complanari restano invariati. L'assenza di bordi
    dimostrati non autorizza a inventare gli angoli o deformare la pagina.
    """
    def unchanged(reason, angle=None, points=()):
        return GeometriaIdentita(immagine.copy(), False, (reason,), points, angle)

    try:
        import cv2
        import numpy as np
        from PIL import Image
    except ImportError:
        return unchanged('Geometria: strumenti locali non disponibili; fonte preservata.')
    if immagine.width * immagine.height > 35_000_000 or min(immagine.size) < 80:
        return unchanged('Geometria: dimensioni fuori dal limite governato; fonte preservata.')
    gray = immagine.convert('L')
    try:
        pixels = np.asarray(gray)
        scale = min(1.0, 1400 / max(immagine.size))
        sample = cv2.resize(pixels, None, fx=scale, fy=scale) if scale < 1 else pixels
        edges = cv2.Canny(sample, 50, 150)
        lines = _rette(edges, cv2, np)
        angle = _inclinazione(lines)
        polygons = _quadrilateri(edges, cv2, np)
    finally:
        gray.close()
    if len(polygons) != 1:
        reason = 'più riquadri distinti' if polygons else 'quattro bordi completi non riscontrati'
        return unchanged(f'Geometria: {reason}; nessuna rettifica globale.', angle)
    polygon = polygons[0]
    points = tuple(tuple(round(float(v / scale), 3) for v in point) for point in polygon)
    lengths = [math.dist(polygon[i], polygon[(i + 1) % 4]) for i in range(4)]
    target = np.asarray(((0, 0), (max(lengths[0], lengths[2]), 0),
                         (max(lengths[0], lengths[2]), max(lengths[1], lengths[3])),
                         (0, max(lengths[1], lengths[3]))), dtype='float32')
    matrix = cv2.getPerspectiveTransform(polygon, target)
    if not _rette_rettificate(lines, polygon, matrix, cv2, np):
        return unchanged('Geometria: rette interne insufficienti o angoli discordanti; nessuna rettifica globale.', angle, points)
    distortion = max(abs(lengths[0] / lengths[2] - 1), abs(lengths[1] / lengths[3] - 1))
    edge_angles = [abs(_angolo((*polygon[i], *polygon[(i + 1) % 4]))) for i in (0, 2)]
    if distortion < .025 and max(edge_angles) < .5:
        return unchanged('Geometria: riquadro già allineato; nessuna trasformazione necessaria.', angle, points)
    matrix = cv2.getPerspectiveTransform(polygon / scale, target / scale)
    corners = np.asarray(((0, 0), (immagine.width, 0), (immagine.width, immagine.height),
                          (0, immagine.height)), dtype='float32')
    denominators = corners @ matrix[2, :2] + matrix[2, 2]
    if np.min(denominators) <= .25:
        return unchanged('Geometria: proiezione della tela instabile; fonte preservata.', angle, points)
    transformed = cv2.perspectiveTransform(corners.reshape(1, 4, 2), matrix)[0]
    low, high = np.floor(transformed.min(axis=0)) - 3, np.ceil(transformed.max(axis=0)) + 3
    size = high - low
    if size.prod() > min(35_000_000, immagine.width * immagine.height * 4):
        return unchanged('Geometria: espansione eccessiva della tela; fonte preservata.', angle, points)
    translation = np.asarray(((1, 0, -low[0]), (0, 1, -low[1]), (0, 0, 1)), dtype='float64')
    rgb = immagine.convert('RGB')
    try:
        result = cv2.warpPerspective(np.asarray(rgb), translation @ matrix, tuple(size.astype(int)),
                                     flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_CONSTANT,
                                     borderValue=(255, 255, 255))
    finally:
        rgb.close()
    return GeometriaIdentita(Image.fromarray(result), True,
        ('Geometria: quattro bordi e rette interne concordanti; candidato rettificato su tela intera, originale preservato.',),
        points, angle)
