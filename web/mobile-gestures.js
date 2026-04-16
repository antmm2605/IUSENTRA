/* ================================================================
   IUSENTRA — Mobile Enhancements & Figma-Quality Design
   Fixes strutturali + design premium per schermi < 768 px
   Versione: 1.0.0
   ================================================================ */

/* ----------------------------------------------------------------
   TOKEN MOBILE AGGIUNTIVI
   ---------------------------------------------------------------- */
:root {
  --mob-topbar-h: calc(var(--topbar-h, 58px) + env(safe-area-inset-top, 0px));
  --mob-botnav-h: calc(var(--bottomnav-h, 62px) + env(safe-area-inset-bottom, 0px));
  --mob-r:        14px;
  --mob-r-sm:     8px;
  --mob-r-lg:     20px;
  --mob-shadow:   0 2px 12px rgba(0,0,0,.08), 0 1px 4px rgba(0,0,0,.05);
  --mob-shadow-up: 0 -2px 24px rgba(0,0,0,.10), 0 -1px 0 rgba(0,0,0,.04);
  --mob-tap-size: 44px;
  --mob-transition: .22s cubic-bezier(.4,0,.2,1);
}

/* ================================================================
   FIX 1 — MODALI BOOTSTRAP: non finire sotto la topbar né dietro la bottom-nav
   Bootstrap di default usa margin-top: 0.5rem su mobile
   → il header della modale viene coperto dalla topbar fixed
   app.css imposta height:calc(100%-1rem) senza tenere conto dei margini
   → il footer (Annulla/Salva) usciva dal viewport e non era cliccabile
   ================================================================ */
@media (max-width: 768px) {
  /* Modale normale: inizia sotto la topbar e finisce sopra la bottom-nav */
  .modal-dialog:not(.modal-fullscreen):not(.modal-fullscreen-sm-down) {
    margin-top: calc(var(--mob-topbar-h) + .5rem) !important;
    margin-bottom: calc(var(--mob-botnav-h) + .5rem) !important;
    /* Altezza corretta: 100% del viewport meno i due margini (topbar + botnav + gap) */
    height: calc(100% - var(--mob-topbar-h) - var(--mob-botnav-h) - 1rem) !important;
    max-height: calc(100% - var(--mob-topbar-h) - var(--mob-botnav-h) - 1rem) !important;
  }

  /* Modale fullscreen: padding-top per non essere coperta */
  .modal-fullscreen,
  .modal-fullscreen-sm-down {
    padding-top: var(--mob-topbar-h) !important;
    padding-bottom: var(--mob-botnav-h) !important;
  }

  /* Bottom-sheet pattern: modali che scivolano dal basso */
  .modal.modal-bottom .modal-dialog {
    margin: 0 !important;
    position: fixed !important;
    bottom: 0 !important;
    left: 0 !important;
    right: 0 !important;
    max-width: 100% !important;
    max-height: calc(92vh - var(--mob-topbar-h));
    transform: translateY(100%);
    transition: transform .35s cubic-bezier(.4,0,.2,1) !important;
  }
  .modal.modal-bottom.show .modal-dialog {
    transform: translateY(0) !important;
  }
  .modal.modal-bottom .modal-content {
    border-radius: var(--mob-r-lg) var(--mob-r-lg) 0 0 !important;
    border: none !important;
    max-height: calc(92vh - var(--mob-topbar-h));
    overflow: hidden;
  }
  /* Handle visivo bottom-sheet */
  .modal.modal-bottom .modal-content::before {
    content: '';
    display: block;
    width: 36px;
    height: 4px;
    background: var(--ds-gray-300, #cbd5e1);
    border-radius: 2px;
    margin: 10px auto 0;
    flex-shrink: 0;
  }
  .modal.modal-bottom .modal-header {
    padding-top: .5rem;
  }
  /* Backdrop opacità ottimizzata */
  .modal-backdrop.show {
    opacity: .45;
  }
}

/* ================================================================
   FIX 2 — TABELLE: scroll orizzontale su mobile
   .ds-table-wrap ha overflow:hidden → le tabelle vengono troncate
   ================================================================ */
@media (max-width: 768px) {
  .ds-table-wrap,
  .table-responsive,
  .table-responsive-sm {
    overflow-x: auto !important;
    -webkit-overflow-scrolling: touch;
    border-radius: var(--mob-r-sm) !important;
  }

  /* Indicatore visivo che la tabella è scrollabile */
  .ds-table-wrap {
    position: relative;
  }

  /* Fade-out sul bordo destro per suggerire scroll */
  .ds-table-wrap::after {
    content: '';
    position: absolute;
    top: 0; right: 0; bottom: 0;
    width: 24px;
    background: linear-gradient(to right, transparent, rgba(255,255,255,.9));
    pointer-events: none;
    border-radius: 0 var(--mob-r-sm) var(--mob-r-sm) 0;
    opacity: 0;
    transition: opacity .2s;
  }
  .ds-table-wrap.scrollable::after {
    opacity: 1;
  }
  [data-bs-theme="dark"] .ds-table-wrap::after {
    background: linear-gradient(to right, transparent, rgba(15,23,42,.9));
  }

  /* Celle tabella: padding ridotto su mobile */
  .ds-table tbody td,
  .ds-table thead th {
    padding: .55rem .6rem;
    font-size: .8rem;
  }

  /* Bootstrap tables */
  .table > tbody > tr > td,
  .table > thead > tr > th {
    white-space: nowrap;
  }
}

/* ================================================================
   FIX 3 — INPUT / SELECT / TEXTAREA: previeni zoom iOS
   iOS zooma automaticamente quando font-size < 16px
   ================================================================ */
@media (max-width: 768px) {
  input[type="text"],
  input[type="email"],
  input[type="tel"],
  input[type="password"],
  input[type="search"],
  input[type="number"],
  input[type="date"],
  input[type="time"],
  input[type="datetime-local"],
  input[type="url"],
  select,
  textarea {
    font-size: 16px !important;
  }

  /* Mantieni il design coerente nonostante il font 16px */
  .form-control,
  .form-select {
    font-size: 16px !important;
    padding: .55rem .85rem;
    border-radius: var(--mob-r-sm);
    min-height: var(--mob-tap-size);
  }

  /* ds-search-input */
  .ds-search-input {
    font-size: 16px !important;
    min-height: var(--mob-tap-size);
  }
}

/* ================================================================
   FIX 4 — STICKY FILTER BARS: offset corretto per topbar
   Elementi sticky nelle pagine di lista possono finire
   sotto la topbar fixed su mobile
   ================================================================ */
@media (max-width: 768px) {
  .sticky-top,
  [style*="position: sticky"],
  [style*="position:sticky"] {
    top: calc(var(--mob-topbar-h) + .5rem) !important;
  }

  /* Filter bar dedicata */
  .filter-sticky {
    position: sticky;
    top: 0;
    z-index: 10;
    background: var(--ds-surface, #fff);
    padding: .5rem 0;
    margin: 0 -1rem;
    padding-left: 1rem;
    padding-right: 1rem;
  }
  [data-bs-theme="dark"] .filter-sticky {
    background: var(--ds-gray-800, #1e293b);
  }
}

/* ================================================================
   FIX 5 — FORM BOTTOM PADDING: submit button visibile
   I form con pulsanti Salva/Annulla in fondo possono
   finire sotto la bottom navigation
   ================================================================ */
@media (max-width: 768px) {
  form:last-child,
  .form-actions {
    padding-bottom: .5rem;
  }

  /* Card form: bordo inferiore extra */
  .ds-form-card:last-child {
    margin-bottom: 1.5rem;
  }

  /* Bottoni azione in fondo al form */
  .form-footer-actions {
    position: sticky;
    bottom: 0;
    background: var(--ds-surface, #fff);
    border-top: 1px solid var(--ds-border, #e2e8f0);
    padding: .75rem 0;
    margin: 1rem -1rem -.5rem;
    padding-left: 1rem;
    padding-right: 1rem;
    z-index: 20;
    box-shadow: var(--mob-shadow-up);
  }
  [data-bs-theme="dark"] .form-footer-actions {
    background: var(--ds-gray-800, #1e293b);
    border-color: var(--ds-gray-700, #334155);
  }
}

/* ================================================================
   DESIGN 1 — PAGE HEADER MOBILE: compatto e leggibile
   ================================================================ */
@media (max-width: 575px) {
  .ds-ph {
    padding: .85rem 1rem;
    gap: .75rem;
    border-radius: var(--mob-r);
    margin-bottom: 1rem;
  }
  .ds-ph-icon {
    width: 38px; height: 38px;
    font-size: 1.1rem;
    border-radius: var(--mob-r-sm);
  }
  .ds-ph-title {
    font-size: 1.05rem;
    letter-spacing: -.02em;
  }
  .ds-ph-sub {
    font-size: .75rem;
  }
  .ds-ph-actions {
    gap: .4rem;
    width: 100%;
    margin-top: .1rem;
  }
  .ds-ph-actions .ds-btn,
  .ds-ph-actions .btn {
    flex: 1;
    justify-content: center;
    min-height: var(--mob-tap-size);
  }
}

/* ================================================================
   DESIGN 2 — CARD MOBILE: profondità e touch feedback
   ================================================================ */
@media (max-width: 768px) {
  /* Card generiche Bootstrap */
  .card {
    border-radius: var(--mob-r) !important;
    box-shadow: var(--mob-shadow) !important;
    border: 1px solid var(--ds-border, #e2e8f0) !important;
    transition: transform var(--mob-transition), box-shadow var(--mob-transition);
  }

  /* Entity card: touch feedback più pronunciato */
  .ds-entity-card {
    border-radius: var(--mob-r) !important;
    box-shadow: var(--mob-shadow) !important;
    transition: transform var(--mob-transition), box-shadow var(--mob-transition) !important;
  }
  .ds-entity-card:active {
    transform: scale(.98) !important;
    box-shadow: 0 1px 4px rgba(0,0,0,.06) !important;
  }

  /* Rimuovi hover elevation su touch (no mouse) */
  @media (hover: none) {
    .ds-entity-card:hover {
      transform: none !important;
      box-shadow: var(--mob-shadow) !important;
    }
  }

  /* Padding interno card più generoso su mobile */
  .card-body {
    padding: 1rem !important;
  }
  .card-header {
    padding: .75rem 1rem !important;
  }
}

/* ================================================================
   DESIGN 3 — LIST GROUP / VOCI LISTA: tap targets grandi
   ================================================================ */
@media (max-width: 768px) {
  .list-group-item {
    padding: .85rem 1rem;
    border-radius: 0 !important;
    min-height: var(--mob-tap-size);
    display: flex;
    align-items: center;
  }
  .list-group {
    border-radius: var(--mob-r) !important;
    overflow: hidden;
    box-shadow: var(--mob-shadow);
  }
  .list-group-item:active {
    background: var(--ds-gray-100, #f1f5f9) !important;
  }
  [data-bs-theme="dark"] .list-group-item:active {
    background: var(--ds-gray-700, #334155) !important;
  }

  /* Freccia indicatore per item navigabili */
  a.list-group-item::after,
  .list-group-item[data-href]::after {
    content: '\F285'; /* bi-chevron-right */
    font-family: 'bootstrap-icons';
    color: var(--ds-gray-300, #cbd5e1);
    margin-left: auto;
    padding-left: .5rem;
    font-size: .9rem;
  }
}

/* ================================================================
   DESIGN 4 — BADGE & STATO: leggibili su mobile
   ================================================================ */
@media (max-width: 768px) {
  .badge {
    font-size: .7rem;
    padding: .3em .6em;
    border-radius: 100px;
  }
  .ds-role {
    font-size: .65rem;
    padding: 2px 7px;
  }
}

/* ================================================================
   DESIGN 5 — STAT PILLS: compatte su mobile
   ================================================================ */
@media (max-width: 575px) {
  .ds-stats {
    gap: .35rem;
    margin-bottom: 1rem;
  }
  .ds-stat-pill {
    padding: .3rem .65rem;
    font-size: .75rem;
    border-radius: 100px;
  }
  .ds-stat-pill .num {
    font-size: .85rem;
  }
}

/* ================================================================
   DESIGN 6 — SEZIONE HEADER MOBILE
   ================================================================ */
@media (max-width: 768px) {
  .ds-section-hd {
    margin-bottom: .6rem;
    padding-bottom: .35rem;
  }
  .ds-section-hd-title {
    font-size: .72rem;
  }
}

/* ================================================================
   DESIGN 7 — FLOATING ACTION BUTTON (FAB)
   Pattern Figma/Material: pulsante primario mobile flottante
   Uso: <button class="mob-fab"><i class="bi bi-plus-lg"></i></button>
   ================================================================ */
@media (max-width: 768px) {
  .mob-fab {
    display: flex;
    align-items: center;
    justify-content: center;
    position: fixed;
    right: 1.1rem;
    bottom: calc(var(--mob-botnav-h) + 1rem);
    width: 52px;
    height: 52px;
    border-radius: 50%;
    background: linear-gradient(135deg, var(--ds-primary, #1a3a5c), #1565c0);
    color: #fff;
    font-size: 1.3rem;
    border: none;
    box-shadow: 0 4px 16px rgba(26,58,92,.38), 0 2px 6px rgba(26,58,92,.22);
    z-index: 990;
    cursor: pointer;
    transition: transform .2s cubic-bezier(.34,1.56,.64,1), box-shadow .2s;
    -webkit-tap-highlight-color: transparent;
    text-decoration: none;
  }
  .mob-fab:active {
    transform: scale(.92);
    box-shadow: 0 2px 8px rgba(26,58,92,.28);
  }
  .mob-fab:hover { color: #fff; text-decoration: none; }

  /* FAB scroll-hide: transizione gestita da mobile-gestures.js via style inline */
  .mob-fab, #pct-ai-fab {
    transition: transform .28s cubic-bezier(.4,0,.2,1),
                opacity   .28s ease,
                box-shadow .2s ease !important;
  }

  /* FAB extended (icon + testo) */
  .mob-fab.mob-fab-extended {
    width: auto;
    border-radius: 100px;
    padding: 0 1.25rem;
    gap: .5rem;
    font-size: .9rem;
    font-weight: 600;
    letter-spacing: .01em;
  }

  /* FAB accent (oro) */
  .mob-fab.mob-fab-accent {
    background: linear-gradient(135deg, var(--ds-accent, #c8972b), #e8b346);
    box-shadow: 0 4px 16px rgba(200,151,43,.38), 0 2px 6px rgba(200,151,43,.22);
  }

  /* FAB nascondi quando la pagina non è in stato "lista" */
  .mob-fab.d-none { display: none !important; }
}

/* ================================================================
   DESIGN 8 — ACCORDION MOBILE: bordi e spaziatura
   ================================================================ */
@media (max-width: 768px) {
  .accordion {
    border-radius: var(--mob-r) !important;
    overflow: hidden;
    box-shadow: var(--mob-shadow);
  }
  .accordion-item {
    border-left: none !important;
    border-right: none !important;
  }
  .accordion-button {
    padding: .9rem 1rem;
    font-size: .88rem;
    min-height: var(--mob-tap-size);
  }
  .accordion-body {
    padding: .85rem 1rem;
    font-size: .85rem;
  }
}

/* ================================================================
   DESIGN 9 — DROPDOWN / OFFCANVAS MOBILE
   ================================================================ */
@media (max-width: 768px) {
  /* Dropdown centrati e più leggibili */
  .dropdown-menu {
    border-radius: var(--mob-r) !important;
    box-shadow: 0 8px 32px rgba(0,0,0,.16), 0 2px 8px rgba(0,0,0,.08) !important;
    padding: .4rem !important;
    min-width: 200px;
  }
  .dropdown-item {
    border-radius: var(--mob-r-sm) !important;
    padding: .6rem .85rem !important;
    font-size: .87rem;
    min-height: var(--mob-tap-size);
    display: flex;
    align-items: center;
  }
  .dropdown-divider {
    margin: .3rem 0 !important;
  }

  /* Offcanvas: slide dal basso con handle */
  .offcanvas-bottom {
    border-radius: var(--mob-r-lg) var(--mob-r-lg) 0 0 !important;
    padding-bottom: env(safe-area-inset-bottom, 0px);
  }
  .offcanvas-bottom .offcanvas-header {
    padding-top: 1rem;
  }
  /* Handle visivo */
  .offcanvas-bottom .offcanvas-header::before {
    content: '';
    display: block;
    width: 36px; height: 4px;
    background: var(--ds-gray-300, #cbd5e1);
    border-radius: 2px;
    position: absolute;
    top: .6rem;
    left: 50%;
    transform: translateX(-50%);
  }
}

/* ================================================================
   DESIGN 10 — TOPBAR MOBILE: affinamenti Figma
   Migliora l'estetica della topbar già esistente
   ================================================================ */
@media (max-width: 768px) {
  /* Titolo pagina più leggibile */
  .topbar h1 {
    font-size: .88rem !important;
    font-weight: 700 !important;
    letter-spacing: -.01em !important;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  /* Pulsanti topbar: tap area minima garantita */
  .topbar .btn,
  .topbar button {
    min-width: var(--mob-tap-size);
    min-height: var(--mob-tap-size);
    display: inline-flex;
    align-items: center;
    justify-content: center;
  }

  /* Hamburger menu: design migliorato */
  #sb-open {
    width: 38px !important;
    height: 38px !important;
    border-radius: var(--mob-r-sm) !important;
    padding: 0 !important;
    flex-shrink: 0;
  }
}

/* ================================================================
   DESIGN 11 — BOTTOM NAV: affinamenti
   ================================================================ */
@media (max-width: 768px) {
  /* Label bottom nav più leggibile */
  .bn-item span {
    font-size: .62rem;
    letter-spacing: .05em;
    font-weight: 500;
  }
  .bn-item.active span {
    font-weight: 700;
  }
  /* Feedback visivo al tap */
  .bn-item:active {
    background: rgba(255,255,255,.06) !important;
  }
}

/* ================================================================
   DESIGN 12 — EMPTY STATE MOBILE
   ================================================================ */
@media (max-width: 575px) {
  .ds-empty {
    padding: 2.5rem 1rem;
  }
  .ds-empty-icon {
    font-size: 2.5rem;
  }
  .ds-empty-title {
    font-size: .9rem;
  }
  .ds-empty-sub {
    font-size: .78rem;
  }
}

/* ================================================================
   DESIGN 13 — NOTIFICHE / ALERT MOBILE
   ================================================================ */
@media (max-width: 768px) {
  .alert {
    border-radius: var(--mob-r) !important;
    font-size: .87rem;
    padding: .85rem 1rem !important;
  }
  /* Flash messages */
  #flash-messages .alert {
    box-shadow: var(--mob-shadow);
  }
}

/* ================================================================
   DESIGN 14 — PAGINATION MOBILE: solo prev/next
   ================================================================ */
@media (max-width: 575px) {
  .pagination .page-item:not(.active):not(:first-child):not(:last-child) {
    display: none;
  }
  .page-link {
    min-width: var(--mob-tap-size);
    min-height: var(--mob-tap-size); /* 44px — WCAG 2.5.5 tap target */
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: var(--mob-r-sm) !important;
  }
}

/* ================================================================
   DESIGN 15 — SCROLL INDICATOR & PULL HINT
   ================================================================ */
@media (max-width: 768px) {
  /* Fade-out in basso per suggerire contenuto scrollabile */
  .mob-scroll-hint {
    position: relative;
  }
  .mob-scroll-hint::after {
    content: '';
    position: absolute;
    bottom: 0; left: 0; right: 0;
    height: 32px;
    background: linear-gradient(to bottom, transparent, rgba(244,246,249,.9));
    pointer-events: none;
  }
  [data-bs-theme="dark"] .mob-scroll-hint::after {
    background: linear-gradient(to bottom, transparent, rgba(15,23,42,.9));
  }
}

/* ================================================================
   DESIGN 16 — CHIP/TAG MOBILE: wrapping corretto
   ================================================================ */
@media (max-width: 768px) {
  .mob-chips {
    display: flex;
    flex-wrap: wrap;
    gap: .4rem;
  }
  .mob-chip {
    display: inline-flex;
    align-items: center;
    gap: .3rem;
    padding: .3rem .7rem;
    background: var(--ds-gray-100, #f1f5f9);
    border: 1px solid var(--ds-border, #e2e8f0);
    border-radius: 100px;
    font-size: .78rem;
    font-weight: 500;
    color: var(--ds-gray-600, #475569);
    white-space: nowrap;
  }
  [data-bs-theme="dark"] .mob-chip {
    background: var(--ds-gray-700, #334155);
    border-color: var(--ds-gray-600, #475569);
    color: var(--ds-gray-400, #94a3b8);
  }
}

/* ================================================================
   DESIGN 17 — DETAIL PAGE: sezioni staccate su mobile
   Le pagine di dettaglio (fascicolo, cliente) su mobile
   mostrano le sezioni come card separate
   ================================================================ */
@media (max-width: 575px) {
  .ds-info {
    gap: 6px 12px;
    font-size: .84rem;
  }
  .ds-info-label {
    font-size: .73rem;
    white-space: normal;
    text-align: left;
  }
  .ds-form-card {
    border-radius: var(--mob-r) !important;
    box-shadow: var(--mob-shadow) !important;
    margin-bottom: 1rem;
  }
  .ds-form-card-header {
    padding: .65rem .9rem;
  }
  .ds-form-card-body {
    padding: .9rem;
  }
}

/* ================================================================
   DESIGN 18 — BREADCRUMB: nascosto su mobile o compatto
   ================================================================ */
@media (max-width: 575px) {
  .breadcrumb {
    font-size: .75rem;
    margin-bottom: .75rem !important;
  }
  /* Mostra solo l'ultimo elemento e il precedente */
  .breadcrumb-item:not(:nth-last-child(-n+2)) {
    display: none;
  }
  .breadcrumb-item:nth-last-child(2)::before {
    content: '‹ ';
  }
}

/* ================================================================
   DESIGN 19 — BUTTON GROUP: full-width su mobile
   ================================================================ */
@media (max-width: 575px) {
  .btn-group-mobile-stack {
    display: flex;
    flex-direction: column;
    width: 100%;
    gap: .5rem;
  }
  .btn-group-mobile-stack .btn,
  .btn-group-mobile-stack .ds-btn {
    width: 100%;
    justify-content: center;
    border-radius: var(--mob-r-sm) !important;
    min-height: var(--mob-tap-size);
  }
}

/* ================================================================
   DESIGN 20 — TABS MOBILE: scroll orizzontale
   ================================================================ */
@media (max-width: 768px) {
  .nav-tabs {
    flex-wrap: nowrap;
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    border-bottom: 2px solid var(--ds-border, #e2e8f0);
    gap: .1rem;
  }
  .nav-tabs::-webkit-scrollbar { display: none; }
  .nav-tabs .nav-link {
    white-space: nowrap;
    padding: .55rem .9rem;
    font-size: .83rem;
    border-radius: var(--mob-r-sm) var(--mob-r-sm) 0 0 !important;
    min-height: 40px;
    display: flex;
    align-items: center;
  }
  .nav-pills .nav-link {
    white-space: nowrap;
    padding: .4rem .85rem;
    font-size: .83rem;
    border-radius: 100px !important;
    min-height: 36px;
    display: flex;
    align-items: center;
  }
  .nav-pills {
    flex-wrap: nowrap;
    overflow-x: auto;
    overflow-y: hidden;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    gap: .35rem;
  }
  .nav-pills::-webkit-scrollbar { display: none; }
}

/* ================================================================
   DESIGN 21 — TOOLTIP / POPOVER: ottimizzati per touch
   ================================================================ */
@media (max-width: 768px) {
  .tooltip { display: none !important; }  /* tooltip non funzionano bene su touch */
  .popover {
    max-width: min(320px, calc(100vw - 2rem));
    border-radius: var(--mob-r) !important;
    box-shadow: 0 8px 32px rgba(0,0,0,.18) !important;
  }
}

/* ================================================================
   DESIGN 22 — SPINNER E LOADING: dimensioni touch-friendly
   ================================================================ */
@media (max-width: 768px) {
  .spinner-grow,
  .spinner-border {
    width: 1.25rem;
    height: 1.25rem;
    border-width: .18em;
  }
  .spinner-border-sm {
    width: .85rem;
    height: .85rem;
  }
}

/* ================================================================
   UTILITY CLASSI MOBILE
   ================================================================ */

/* Contenuto visibile solo su mobile */
.mob-only   { display: none; }
@media (max-width: 768px) {
  .mob-only   { display: block; }
  .mob-only.d-flex { display: flex !important; }
  .mob-only.d-inline-flex { display: inline-flex !important; }
  .desk-only  { display: none !important; }
}
@media (min-width: 769px) {
  .mob-only   { display: none !important; }
}

/* Margini safe-area */
.mob-pb-safe {
  padding-bottom: env(safe-area-inset-bottom, 0px);
}
.mob-pt-safe {
  padding-top: env(safe-area-inset-top, 0px);
}

/* Tap target minimo garantito */
.tap-target {
  min-width: var(--mob-tap-size);
  min-height: var(--mob-tap-size);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

/* Nasconde le scrollbar mantenendo funzionalità */
.scrollbar-none {
  scrollbar-width: none;
  -ms-overflow-style: none;
}
.scrollbar-none::-webkit-scrollbar { display: none; }

/* ================================================================
   GESTURE ENHANCEMENTS (mobile-gestures.js)
   ================================================================ */

/* Pull-to-Refresh indicator */
#pct-ptr-indicator {
  will-change: transform;
  user-select: none;
  -webkit-user-select: none;
}
#pct-ptr-indicator .bi {
  transition: transform .1s linear;
}

/* Agenda touch D&D — touch-action prevent scroll su pill trascinabili */
@media (pointer: coarse) {
  .dnd-pill[draggable] {
    /* touch-action: none è attivato via JS solo durante il drag (vedi mobile-gestures.js)
       per non bloccare lo scroll della pagina quando l'utente non sta trascinando */
    touch-action: manipulation;  /* consente tap e scroll, blocca solo zoom pinch */
    cursor: grab;
  }
}

/* ================================================================
   SCRIPT HELPER — tabelle scrollabili (rilevamento)
   ================================================================ */
