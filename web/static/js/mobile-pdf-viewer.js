(() => {
  'use strict'

  const pages = document.querySelector('[data-document-pages]')
  const zoomOut = document.querySelector('[data-zoom-out]')
  const zoomReset = document.querySelector('[data-zoom-reset]')
  const zoomIn = document.querySelector('[data-zoom-in]')
  const zoomValue = document.querySelector('[data-zoom-value]')
  if (!(pages instanceof HTMLElement) || !(zoomValue instanceof HTMLOutputElement)) return

  const MIN_ZOOM = 0.75
  const MAX_ZOOM = 3
  const STEP = 0.25
  let zoom = 1
  let pinchDistance = 0
  let pinchZoom = 1

  const clamp = (value) => Math.min(MAX_ZOOM, Math.max(MIN_ZOOM, value))
  const distance = (touches) => Math.hypot(
    touches[0].clientX - touches[1].clientX,
    touches[0].clientY - touches[1].clientY,
  )

  const render = (nextZoom, anchorX = pages.clientWidth / 2, anchorY = pages.clientHeight / 2) => {
    const previousZoom = zoom
    const contentX = (pages.scrollLeft + anchorX) / previousZoom
    const contentY = (pages.scrollTop + anchorY) / previousZoom
    zoom = Math.round(clamp(nextZoom) * 100) / 100
    pages.style.setProperty('--zoom', String(zoom))
    zoomValue.value = `${Math.round(zoom * 100)}%`
    if (zoomOut instanceof HTMLButtonElement) zoomOut.disabled = zoom <= MIN_ZOOM
    if (zoomIn instanceof HTMLButtonElement) zoomIn.disabled = zoom >= MAX_ZOOM
    window.requestAnimationFrame(() => {
      pages.scrollLeft = Math.max(0, contentX * zoom - anchorX)
      pages.scrollTop = Math.max(0, contentY * zoom - anchorY)
    })
  }

  zoomOut?.addEventListener('click', () => render(zoom - STEP))
  zoomReset?.addEventListener('click', () => render(1))
  zoomIn?.addEventListener('click', () => render(zoom + STEP))

  pages.addEventListener('touchstart', (event) => {
    if (event.touches.length !== 2) return
    pinchDistance = distance(event.touches)
    pinchZoom = zoom
  }, { passive: true })

  pages.addEventListener('touchmove', (event) => {
    if (event.touches.length !== 2 || pinchDistance <= 0) return
    event.preventDefault()
    const centerX = (event.touches[0].clientX + event.touches[1].clientX) / 2
    const centerY = (event.touches[0].clientY + event.touches[1].clientY) / 2
    render(pinchZoom * (distance(event.touches) / pinchDistance), centerX, centerY)
  }, { passive: false })

  pages.addEventListener('touchend', (event) => {
    if (event.touches.length < 2) pinchDistance = 0
  }, { passive: true })

  render(1, 0, 0)
})()
