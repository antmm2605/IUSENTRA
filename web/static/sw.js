/* ═══════════════════════════════════════════════════════════════
   EDITOR DOCUMENTI — STILE MICROSOFT WORD
   IUSENTRA - IUSENTRA
   ═══════════════════════════════════════════════════════════════ */

:root {
    --word-blue: #2b579a;
    --word-blue-dark: #1e3f6f;
    --word-blue-hover: #1e3a5f;
    --word-accent: #0078d4;
    --word-gray-50: #f3f2f1;
    --word-gray-100: #edebe9;
    --word-gray-200: #e1dfdd;
    --word-gray-300: #c8c6c4;
    --word-gray-400: #a19f9d;
    --word-gray-500: #605e5c;
    --word-gray-600: #323130;
    --word-surface: #ffffff;
    --word-ribbon-bg: #f3f2f1;
    --word-border: #e1dfdd;
    --word-shadow-sm: 0 1.6px 3.6px rgba(0,0,0,0.13);
    --word-shadow-md: 0 3.2px 7.2px rgba(0,0,0,0.13);
    --word-shadow-lg: 0 6.4px 14.4px rgba(0,0,0,0.13);
    --word-radius: 4px;
    --word-transition: 0.12s ease;
}

/* ───────────────────────────────────────────────────────────────
   LAYOUT PRINCIPALE
   ─────────────────────────────────────────────────────────────── */
#main {
    padding: 0 !important;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    height: 100vh;
    background: var(--word-gray-100);
}

/* ───────────────────────────────────────────────────────────────
   HEADER (Barra Blu Superiore)
   ─────────────────────────────────────────────────────────────── */
.ed-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 0.6rem 1.2rem;
    background: linear-gradient(180deg, var(--word-blue) 0%, var(--word-blue-dark) 100%);
    border-bottom: 1px solid rgba(0,0,0,0.2);
    box-shadow: var(--word-shadow-md);
    flex-shrink: 0;
    gap: 1rem;
    flex-wrap: wrap;
    position: sticky;
    top: 0;
    z-index: 100;
    color: white;
}

.ed-header-left {
    display: flex;
    align-items: center;
    gap: 0.85rem;
    min-width: 0;
}

.ed-header-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
}

.ed-filename {
    font-size: 0.92rem;
    font-weight: 600;
    color: white;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
    max-width: 35vw;
    display: flex;
    align-items: center;
    gap: 0.5rem;
}

.ed-filename i {
    color: white;
    font-size: 1.1rem;
    flex-shrink: 0;
}

.ed-status {
    font-size: 0.75rem;
    font-weight: 500;
    color: rgba(255,255,255,0.85);
    display: flex;
    align-items: center;
    gap: 0.4rem;
    background: rgba(255,255,255,0.12);
    padding: 0.3rem 0.8rem;
    border-radius: var(--word-radius);
    white-space: nowrap;
}

.ed-status.saving { color: #4a7ab5; }
.ed-status.saved { color: #90ee90; }
.ed-status.error { color: #ff9999; }

.ed-wordcount {
    font-size: 0.75rem;
    color: rgba(255,255,255,0.75);
    white-space: nowrap;
    padding: 0 0.6rem;
    border-left: 1px solid rgba(255,255,255,0.2);
    margin-left: 0.5rem;
}

/* ───────────────────────────────────────────────────────────────
   TOOLBAR (Ribbon Orizzontale) - CORRETTO!
   ─────────────────────────────────────────────────────────────── */
.ed-toolbar {
    display: flex;
    flex-direction: row;          /* ← IMPORTANTE: orizzontale! */
    flex-wrap: wrap;              /* ← Va a capo se non c'è spazio */
    align-items: center;
    gap: 4px;
    padding: 0.5rem 1rem;
    background: #ff0000 !important;
    background: var(--word-ribbon-bg);
    border-bottom: 1px solid var(--word-border);
    flex-shrink: 0;
    overflow-x: auto;
    overflow-y: hidden;
}

.ed-toolbar::-webkit-scrollbar {
    height: 4px;
}

.ed-toolbar::-webkit-scrollbar-thumb {
    background: var(--word-gray-300);
    border-radius: 2px;
}

/* Gruppi toolbar (separati da linee verticali) */
.ed-toolbar-group {
    display: flex;
    flex-direction: row;          /* ← Orizzontale! */
    align-items: center;
    gap: 2px;
    padding: 0 6px;
    border-right: 1px solid var(--word-gray-300);
    flex-shrink: 0;
}

.ed-toolbar-group:last-child {
    border-right: none;
}

/* Bottoni toolbar */
.ed-tb-btn {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 30px;
    height: 30px;
    padding: 0 6px;
    border: 1px solid transparent;
    background: transparent;
    border-radius: var(--word-radius);
    cursor: pointer;
    color: var(--word-gray-600);
    font-size: 0.85rem;
    transition: all var(--word-transition);
    flex-shrink: 0;
    position: relative;
}

.ed-tb-btn:hover {
    background: var(--word-gray-200);
    color: var(--word-gray-700);
    border-color: var(--word-gray-300);
}

.ed-tb-btn.is-active {
    background: var(--word-accent);
    color: white;
    border-color: var(--word-accent);
}

.ed-tb-btn i {
    font-size: 1rem;
    line-height: 1;
}

/* Select toolbar */
.ed-tb-select {
    height: 30px;
    padding: 0 0.5rem;
    border: 1px solid var(--word-gray-300);
    border-radius: var(--word-radius);
    background: var(--word-surface);
    color: var(--word-gray-600);
    font-size: 0.8rem;
    cursor: pointer;
    flex-shrink: 0;
    outline: none;
}

.ed-tb-select:hover {
    border-color: var(--word-accent);
}

.ed-tb-select:focus {
    border-color: var(--word-accent);
    box-shadow: 0 0 0 2px rgba(0,120,212,0.15);
}

/* Input colore */
.ed-tb-color {
    width: 30px;
    height: 30px;
    padding: 2px;
    border: 1px solid var(--word-gray-300);
    border-radius: var(--word-radius);
    cursor: pointer;
    flex-shrink: 0;
    background: var(--word-surface);
}

.ed-tb-color:hover {
    border-color: var(--word-accent);
}

/* Etichette */
.ed-tb-label {
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--word-gray-500);
    padding: 0 4px;
    white-space: nowrap;
    flex-shrink: 0;
    display: flex;
    align-items: center;
}

/* Separatore verticale */
.ed-tb-sep {
    width: 1px;
    height: 24px;
    background: var(--word-gray-300);
    margin: 0 4px;
    flex-shrink: 0;
}

/* Tooltip */
.ed-tb-btn[title]:hover::after {
    content: attr(title);
    position: absolute;
    bottom: -32px;
    left: 50%;
    transform: translateX(-50%);
    background: var(--word-gray-600);
    color: white;
    font-size: 0.7rem;
    padding: 4px 8px;
    border-radius: var(--word-radius);
    white-space: nowrap;
    pointer-events: none;
    z-index: 1000;
}

/* ───────────────────────────────────────────────────────────────
   CANVAS / FOGLIO A4
   ─────────────────────────────────────────────────────────────── */
.ed-canvas {
    flex: 1;
    overflow-y: auto;
    background: var(--word-gray-100);
    display: flex;
    justify-content: center;
    padding: 2rem 1.5rem 4rem;
}

.ed-paper {
    width: 100%;
    max-width: 210mm;
    min-height: 297mm;
    background: #ffffff;
    border-radius: var(--word-radius);
    box-shadow: var(--word-shadow-lg);
    padding: 25mm;
    font-family: 'Times New Roman', Times, serif;
    font-size: 12pt;
    line-height: 1.6;
    color: #000000;
    outline: none;
    position: relative;
    margin: 0.5rem 0;
}

.ed-paper .ProseMirror {
    outline: none;
    min-height: 600px;
}

.ed-paper .ProseMirror p.is-editor-empty:first-child::before {
    content: attr(data-placeholder);
    float: left;
    pointer-events: none;
    height: 0;
    color: var(--word-gray-400);
}

.ed-paper img {
    max-width: 100%;
    height: auto;
    border-radius: var(--word-radius);
    margin: 0.5rem 0;
}

.ed-paper img.ProseMirror-selectednode {
    outline: 2px solid var(--word-accent);
}

/* ───────────────────────────────────────────────────────────────
   STILI DOCUMENTO
   ─────────────────────────────────────────────────────────────── */
.ed-paper h1 { font-size: 18pt; font-weight: 700; margin-top: 1.5rem; margin-bottom: 0.75rem; }
.ed-paper h2 { font-size: 15pt; font-weight: 700; margin-top: 1.2rem; margin-bottom: 0.5rem; }
.ed-paper h3 { font-size: 13pt; font-weight: 600; margin-top: 1rem; margin-bottom: 0.5rem; }
.ed-paper h4 { font-size: 12pt; font-weight: 600; text-decoration: underline; }
.ed-paper p { margin-bottom: 0.75rem; text-align: justify; }
.ed-paper ul, .ed-paper ol { padding-left: 2rem; margin-bottom: 0.75rem; }
.ed-paper table { border-collapse: collapse; width: 100%; margin-bottom: 1rem; }
.ed-paper td, .ed-paper th { border: 1px solid #000; padding: 0.5rem 0.75rem; }
.ed-paper th { background: #f0f0f0; font-weight: 600; }
.ed-paper blockquote {
    border-left: 4px solid var(--word-accent);
    padding-left: 1rem;
    color: var(--word-gray-600);
    font-style: italic;
    margin: 1rem 0;
    background: var(--word-gray-50);
}

/* ───────────────────────────────────────────────────────────────
   LOADING
   ─────────────────────────────────────────────────────────────── */
.ed-loading {
    position: absolute;
    inset: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(255,255,255,0.95);
    z-index: 10;
    border-radius: var(--word-radius);
    gap: 1rem;
}

.ed-loading .spinner-border {
    color: var(--word-accent);
    width: 3rem;
    height: 3rem;
}

.ed-loading p {
    color: var(--word-gray-500);
    font-size: 0.9rem;
}

/* ───────────────────────────────────────────────────────────────
   BANNER PDF
   ─────────────────────────────────────────────────────────────── */
.ed-pdf-banner {
    background: linear-gradient(90deg, #fff3cd 0%, #ffe69c 100%);
    border-bottom: 1px solid #4a7ab5;
    padding: 0.75rem 1.25rem;
    display: flex;
    align-items: center;
    gap: 0.75rem;
    font-size: 0.85rem;
    color: #856404;
    flex-shrink: 0;
}

/* ───────────────────────────────────────────────────────────────
   MOBILE ACTIONS
   ─────────────────────────────────────────────────────────────── */
.ed-mobile-actions {
    position: fixed;
    bottom: calc(62px + env(safe-area-inset-bottom, 0px));
    left: 0;
    right: 0;
    z-index: 200;
    display: flex;
    gap: 0.5rem;
    padding: 0.75rem 1rem;
    background: var(--word-surface);
    border-top: 1px solid var(--word-border);
    box-shadow: 0 -4px 12px rgba(0,0,0,0.1);
}

.ed-mobile-actions .ds-btn {
    flex: 1;
    justify-content: center;
}

/* ───────────────────────────────────────────────────────────────
   MODAL
   ─────────────────────────────────────────────────────────────── */
.ed-image-modal {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,0.5);
    z-index: 10000;
    align-items: center;
    justify-content: center;
    backdrop-filter: blur(4px);
}

.ed-image-modal.active {
    display: flex;
}

.ed-image-modal-content {
    background: var(--word-surface);
    padding: 1.5rem;
    border-radius: 8px;
    max-width: 450px;
    width: 90%;
    box-shadow: var(--word-shadow-lg);
}

/* ───────────────────────────────────────────────────────────────
   TOAST
   ─────────────────────────────────────────────────────────────── */
.ed-toast {
    position: fixed;
    bottom: 100px;
    right: 20px;
    padding: 14px 20px;
    border-radius: 8px;
    color: white;
    font-size: 0.85rem;
    z-index: 9999;
    animation: edSlideIn 0.3s ease;
    display: flex;
    align-items: center;
    gap: 10px;
    box-shadow: var(--word-shadow-lg);
}

.ed-toast.success { background: #107c10; }
.ed-toast.error { background: #d13438; }
.ed-toast.info { background: #0078d4; }

@keyframes edSlideIn {
    from { transform: translateX(100%); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
}

/* ───────────────────────────────────────────────────────────────
   RESPONSIVE
   ─────────────────────────────────────────────────────────────── */
@media (max-width: 768px) {
    .ed-paper {
        padding: 1.5rem 1.25rem;
        min-height: 400px;
    }
    
    .ed-canvas {
        padding: 1rem 0.25rem 5rem;
    }
    
    .ed-filename {
        max-width: 45vw;
    }
    
    .ed-tb-label {
        display: none;
    }
    
    .ed-header-right .ed-desktop-only {
        display: none;
    }
}

@media (min-width: 769px) {
    .ed-mobile-actions {
        display: none;
    }
}

/* ───────────────────────────────────────────────────────────────
   FULLSCREEN
   ─────────────────────────────────────────────────────────────── */
.ed-paper.fullscreen {
    position: fixed;
    inset: 0;
    max-width: none;
    border-radius: 0;
    z-index: 9000;
    overflow-y: auto;
    margin: 0;
}

.ed-canvas.fullscreen {
    padding: 0;
    background: #ffffff;
}

/* ───────────────────────────────────────────────────────────────
   STAMPA
   ─────────────────────────────────────────────────────────────── */
@media print {
    .ed-header,
    .ed-toolbar,
    .ed-mobile-actions,
    .ed-pdf-banner,
    .ed-loading {
        display: none !important;
    }
    
    .ed-canvas {
        padding: 0;
        background: white;
    }
    
    .ed-paper {
        box-shadow: none;
        max-width: 100%;
        padding: 0;
        margin: 0;
    }
    
    @page {
        margin: 2.5cm;
        size: A4;
    }
}