(() => {
  'use strict'

  const pages = document.querySelector('[data-document-pages]')
  const zoomOut = document.querySelector('[data-zoom-out]')
  const zoomReset = document.querySelector('[data-zoom-reset]')
  const zoomIn = document.querySelector('[data-zoom-in]')
  const zoomValue = document.querySelector('[data-zoom-value]')
  const downloadLink = document.querySelector('[data-document-download]')
  const downloadStatus = document.querySelector('[data-download-status]')
  const printButton = document.querySelector('[data-document-print]')
  const rotateLeft = document.querySelector('[data-rotate-left]')
  const rotateRight = document.querySelector('[data-rotate-right]')
  const rotationValue = document.querySelector('[data-rotation-value]')
  const saveRotation = document.querySelector('[data-document-save-rotation]')
  if (!(pages instanceof HTMLElement) || !(zoomValue instanceof HTMLOutputElement)) return

  const copyButton = document.querySelector('[data-document-copy]')
  const highlightButton = document.querySelector('[data-document-highlight]')
  const clearButton = document.querySelector('[data-document-clear]')
  let selectedRange = null
  let selectedText = ''
  const status = (message) => { if (downloadStatus) downloadStatus.textContent = message }
  const updateSelection = () => {
    const selection = window.getSelection()
    if (selection && selection.rangeCount && !selection.isCollapsed
      && pages.contains(selection.anchorNode) && pages.contains(selection.focusNode)) {
      selectedRange = selection.getRangeAt(0).cloneRange()
      selectedText = selection.toString().trim()
    } else if (!document.activeElement?.closest('.reader-toolbar')) {
      selectedRange = null
      selectedText = ''
    }
    if (copyButton) copyButton.disabled = !selectedText
    if (highlightButton) highlightButton.disabled = !selectedText
  }
  document.addEventListener('selectionchange', updateSelection)
  for (const button of [copyButton, highlightButton]) {
    button?.addEventListener('mousedown', (event) => event.preventDefault())
  }
  copyButton?.addEventListener('click', async () => {
    if (!selectedText) return
    try {
      await navigator.clipboard.writeText(selectedText)
      status('Testo copiato. Puoi incollarlo dove desideri.')
    } catch (_) {
      status('Il browser non ha consentito la copia. La selezione resta attiva: premi Ctrl+C o usa Copia nel menu del dispositivo.')
    }
  })
  highlightButton?.addEventListener('click', () => {
    if (!selectedRange) return
    for (const word of pages.querySelectorAll('.reader-word')) {
      if (selectedRange.intersectsNode(word)) word.classList.add('is-highlighted')
    }
    if (clearButton) clearButton.disabled = !pages.querySelector('.is-highlighted')
    status('Brano evidenziato per questa sessione di lettura. Il documento originale resta invariato.')
  })
  clearButton?.addEventListener('click', () => {
    pages.querySelectorAll('.is-highlighted').forEach((word) => word.classList.remove('is-highlighted'))
    clearButton.disabled = true
    status('Evidenziazioni rimosse.')
  })
  const measure = document.createElement('canvas').getContext('2d')
  let rotation = 0
  const normalizedRotation = (value) => ((Number(value) % 360) + 360) % 360
  const rotationSaveUrl = saveRotation instanceof HTMLButtonElement ? String(saveRotation.dataset.documentSaveRotation || '') : ''
  const updateRotationControls = () => {
    if (rotationValue instanceof HTMLOutputElement) rotationValue.value = `${rotation}°`
    if (saveRotation instanceof HTMLButtonElement) {
      saveRotation.disabled = !rotation || !rotationSaveUrl || saveRotation.dataset.busy === 'true'
      saveRotation.title = rotationSaveUrl
        ? 'Salva una copia ruotata nel fascicolo'
        : 'Salvataggio disponibile solo per documenti del fascicolo'
    }
  }
  const layoutRotation = () => {
    pages.style.setProperty('--reader-rotation', `${rotation}deg`)
    pages.dataset.rotation = String(rotation)
    for (const surface of pages.querySelectorAll('.reader-page-surface')) {
      if (!(surface instanceof HTMLElement)) continue
      const rotator = surface.querySelector('.reader-page-rotator')
      const image = surface.querySelector('img')
      if (!(rotator instanceof HTMLElement) || !(image instanceof HTMLImageElement)) continue
      const imageWidth = image.naturalWidth || image.width || 595
      const imageHeight = image.naturalHeight || image.height || 842
      const aspect = imageWidth > 0 && imageHeight > 0 ? imageWidth / imageHeight : 1 / 1.414
      if (rotation % 180 === 0) {
        surface.style.aspectRatio = `${imageWidth} / ${imageHeight}`
        rotator.style.width = '100%'
        rotator.style.height = '100%'
        rotator.style.left = '0'
        rotator.style.top = '0'
      } else {
        surface.style.aspectRatio = `${imageHeight} / ${imageWidth}`
        const rect = surface.getBoundingClientRect()
        rotator.style.width = `${Math.max(1, rect.height)}px`
        rotator.style.height = `${Math.max(1, rect.width)}px`
        rotator.style.left = `${(rect.width - rect.height) / 2}px`
        rotator.style.top = `${(rect.height - rect.width) / 2}px`
      }
    }
    fitWords()
    updateRotationControls()
  }
  const fitWords = () => {
    if (!measure) return
    for (const word of pages.querySelectorAll('.reader-word')) {
      const text = word.firstElementChild
      if (!text) continue
      const height = word.clientHeight
      const size = Math.max(1, height * 0.83)
      word.style.fontSize = `${size}px`
      word.style.fontFamily = 'Arial, sans-serif'
      measure.font = `${size}px Arial`
      const textWidth = measure.measureText(text.textContent.trimEnd()).width
      text.style.transform = `scaleX(${textWidth ? word.clientWidth / textWidth : 1})`
    }
  }
  const resize = new ResizeObserver(fitWords)
  pages.querySelectorAll('.reader-page-surface').forEach((surface) => resize.observe(surface))
  const layoutResize = new ResizeObserver(layoutRotation)
  pages.querySelectorAll('.reader-page-surface').forEach((surface) => layoutResize.observe(surface))
  pages.querySelectorAll('img').forEach((image) => {
    if (image instanceof HTMLImageElement) {
      image.addEventListener('load', layoutRotation, { once: true })
      if (image.complete) window.requestAnimationFrame(layoutRotation)
    }
  })
  fitWords()
  layoutRotation()

  // Native text appears immediately. Scanned pages obtain OCR only when visible.
  const ocrQueue = []
  let ocrActive = 0
  const runOcr = () => {
    if (ocrActive >= 2 || !ocrQueue.length) return
    const surface = ocrQueue.shift()
    const note = surface.querySelector('.reader-no-text')
    const img = surface.querySelector('img')
    if (!note || !img) { runOcr(); return }
    ocrActive += 1
    note.textContent = 'Lettura OCR della pagina in corso…'
    const url = new URL(img.src, window.location.href)
    url.searchParams.set('reader_text', '1')
    fetch(url, { credentials: 'same-origin' }).then(async (response) => {
      if (!response.ok) throw new Error('OCR non disponibile')
      const payload = await response.json()
      const layer = document.createElement('div')
      layer.className = 'reader-text-layer'
      for (const word of payload.words || []) {
        const box = document.createElement('span')
        box.className = 'reader-word'
        for (const [property, field] of [['left', 'x'], ['top', 'y'], ['width', 'w'], ['height', 'h']]) {
          box.style[property] = `${Number(word[field]) || 0}%`
        }
        const text = document.createElement('span')
        text.textContent = `${word.text} `
        box.appendChild(text)
        layer.appendChild(box)
      }
      surface.appendChild(layer)
      note.textContent = payload.message || 'Testo OCR disponibile.'
      fitWords()
    }).catch(() => { note.textContent = 'Lettura OCR della pagina non riuscita. Riapri il documento per riprovare.' })
      .finally(() => { ocrActive -= 1; runOcr() })
    runOcr()
  }
  const ocrObserver = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue
      ocrObserver.unobserve(entry.target)
      ocrQueue.push(entry.target)
    }
    runOcr()
  }, { root: pages, rootMargin: '100px' })
  pages.querySelectorAll('.reader-page-surface').forEach((surface) => {
    if (surface.querySelector('.reader-no-text')) ocrObserver.observe(surface)
  })

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
    layoutRotation()
    window.requestAnimationFrame(() => {
      pages.scrollLeft = Math.max(0, contentX * zoom - anchorX)
      pages.scrollTop = Math.max(0, contentY * zoom - anchorY)
    })
  }

  zoomOut?.addEventListener('click', () => render(zoom - STEP))
  zoomReset?.addEventListener('click', () => render(1))
  zoomIn?.addEventListener('click', () => render(zoom + STEP))
  rotateLeft?.addEventListener('click', () => {
    rotation = normalizedRotation(rotation - 90)
    layoutRotation()
    status(`Documento ruotato a ${rotation} gradi. Premi “Salva rotazione” per registrare una copia nel fascicolo.`)
  })
  rotateRight?.addEventListener('click', () => {
    rotation = normalizedRotation(rotation + 90)
    layoutRotation()
    status(`Documento ruotato a ${rotation} gradi. Premi “Salva rotazione” per registrare una copia nel fascicolo.`)
  })

  saveRotation?.addEventListener('click', async () => {
    if (!(saveRotation instanceof HTMLButtonElement) || !rotationSaveUrl || !rotation) return
    saveRotation.dataset.busy = 'true'
    saveRotation.disabled = true
    const previousText = saveRotation.textContent
    saveRotation.textContent = 'Salvo…'
    status('Salvataggio della copia ruotata nel fascicolo…')
    try {
      const requestUrl = new URL(rotationSaveUrl, window.location.href)
      const csrf = document.querySelector('meta[name="csrf-token"]')?.getAttribute('content') || ''
      const response = await fetch(requestUrl.toString(), {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          Accept: 'application/json',
          'Content-Type': 'application/json',
          'X-Requested-With': 'XMLHttpRequest',
          ...(csrf ? { 'X-CSRFToken': csrf, 'X-CSRF-Token': csrf } : {}),
        },
        body: JSON.stringify({ rotation }),
      })
      const payload = await response.json().catch(() => ({}))
      if (!response.ok || payload.ok === false) {
        throw new Error(String(payload.messaggio || payload.errore || 'Salvataggio non completato.'))
      }
      status(String(payload.messaggio || 'Copia ruotata salvata nel fascicolo.'))
      if (payload.preview_url) {
        window.setTimeout(() => { window.location.href = String(payload.preview_url) }, 550)
      } else {
        rotation = 0
        layoutRotation()
      }
    } catch (error) {
      status(error instanceof Error ? (error.message === 'Failed to fetch' ? 'Salvataggio bloccato dal browser. Riapri il documento e riprova.' : error.message) : 'Salvataggio non completato.')
    } finally {
      saveRotation.dataset.busy = 'false'
      saveRotation.textContent = previousText || 'Salva rotazione'
      updateRotationControls()
    }
  })

  window.addEventListener('message', (event) => {
    if (event.origin !== window.location.origin || !event.data || typeof event.data !== 'object') return
    if (event.data.type !== 'iusentra.document.setRotation') return
    rotation = normalizedRotation(event.data.rotation)
    layoutRotation()
    if (rotation) {
      status(`Documento ruotato a ${rotation} gradi. Premi “Salva rotazione” per registrare una copia nel fascicolo.`)
    }
  })

  const setDownloadStatus = (message) => {
    if (downloadStatus instanceof HTMLElement) downloadStatus.textContent = message
  }

  printButton?.addEventListener('click', async () => {
    if (!(printButton instanceof HTMLButtonElement) || printButton.disabled) return
    const images = [...pages.querySelectorAll('img')]
    if (!images.length) {
      setDownloadStatus('Il documento non contiene pagine stampabili.')
      return
    }
    printButton.disabled = true
    printButton.textContent = 'Preparo…'
    setDownloadStatus('Caricamento di tutte le pagine per la stampa…')
    let timeout
    try {
      await Promise.race([
        Promise.all(images.map(async (image) => {
          image.loading = 'eager'
          await image.decode()
          if (!image.naturalWidth) throw new Error('Pagina non disponibile')
        })),
        new Promise((_, reject) => { timeout = window.setTimeout(() => reject(new Error('Attesa terminata')), 60000) }),
      ])
      setDownloadStatus(`${images.length} pagine pronte per la stampa.`)
      window.print()
    } catch (_) {
      setDownloadStatus('Non tutte le pagine sono disponibili. Riprova la stampa dopo il caricamento del documento.')
    } finally {
      window.clearTimeout(timeout)
      printButton.disabled = false
      printButton.textContent = 'Stampa'
    }
  })

  window.addEventListener('message', (event) => {
    if (event.origin !== window.location.origin || !event.data || typeof event.data !== 'object') return
    if (event.data.type !== 'iusentra.document.download.result') return
    setDownloadStatus(String(event.data.message || (event.data.ok ? 'Download avviato dal lettore IUSENTRA.' : 'Download non riuscito.')))
  })

  downloadLink?.addEventListener('click', (event) => {
    if (!(downloadLink instanceof HTMLAnchorElement) || downloadLink.dataset.busy === 'true') return
    if (window.parent === window) return
    event.preventDefault()
    downloadLink.dataset.busy = 'true'
    downloadLink.setAttribute('aria-disabled', 'true')
    downloadLink.textContent = 'Preparo…'
    setDownloadStatus('Richiesta inviata al lettore IUSENTRA…')
    window.parent.postMessage({
      type: 'iusentra.document.download',
      url: downloadLink.href,
      filename: document.querySelector('header strong')?.textContent?.trim() || 'documento',
    }, window.location.origin)
    window.setTimeout(() => {
      if (downloadLink.dataset.busy !== 'true') return
      downloadLink.dataset.busy = 'false'
      downloadLink.removeAttribute('aria-disabled')
      downloadLink.textContent = 'Scarica'
    }, 1000)
  })

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
