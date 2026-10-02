export type SignaturePoint = { x: number; y: number }
export type SignatureStroke = { points: SignaturePoint[]; width: number; color: string; pen: string }

// Smooth quadratic samples keep the exported stroke identical to its live preview.
function smooth(points: SignaturePoint[]): SignaturePoint[] {
  if (points.length < 3) return points
  const result = [points[0]]
  let from = points[0]
  for (let i = 1; i < points.length - 1; i++) {
    const control = points[i]
    const to = { x: (control.x + points[i + 1].x) / 2, y: (control.y + points[i + 1].y) / 2 }
    const count = Math.max(2, Math.min(64, Math.ceil((Math.hypot(control.x - from.x, control.y - from.y) + Math.hypot(to.x - control.x, to.y - control.y)) / 2)))
    for (let step = 1; step <= count; step++) {
      const t = step / count, u = 1 - t
      result.push({ x: u * u * from.x + 2 * u * t * control.x + t * t * to.x, y: u * u * from.y + 2 * u * t * control.y + t * t * to.y })
    }
    from = to
  }
  result.push(points[points.length - 1])
  return result
}

export function drawSignatureInk(context: CanvasRenderingContext2D, strokes: SignatureStroke[]) {
  context.lineCap = 'round'
  context.lineJoin = 'round'
  for (const stroke of strokes) {
    if (!stroke.points.length) continue
    context.strokeStyle = stroke.color
    context.fillStyle = stroke.color
    const points = smooth(stroke.points)
    if (points.length === 1) {
      context.beginPath()
      context.arc(points[0].x, points[0].y, stroke.width, 0, Math.PI * 2)
      context.fill()
      continue
    }
    if (stroke.pen === 'fountain') {
      // A fixed 45-degree nib gives thin upstrokes and broader crossing strokes.
      for (let i = 1; i < points.length; i++) {
        const from = points[i - 1], to = points[i]
        if (from.x === to.x && from.y === to.y) continue
        const angle = Math.atan2(to.y - from.y, to.x - from.x)
        context.lineWidth = stroke.width * 2 * (.3 + .7 * Math.abs(Math.sin(angle - Math.PI / 4)))
        context.beginPath()
        context.moveTo(from.x, from.y)
        context.lineTo(to.x, to.y)
        context.stroke()
      }
    } else {
      context.lineWidth = stroke.width * 2
      context.beginPath()
      context.moveTo(points[0].x, points[0].y)
      points.slice(1).forEach(point => context.lineTo(point.x, point.y))
      context.stroke()
    }
  }
}
