/**
 * PCT Studio — Mobile Gesture Enhancements
 *
 * Funzionalità aggiunte:
 *  1. Edge-swipe destra → apre sidebar (dall'area ≤30px dal bordo sx)
 *  2. Swipe sinistra su sidebar aperta → chiude sidebar
 *  3. FAB auto-hide su scroll verso il basso, mostra su scroll verso l'alto
 *  4. Haptic feedback leggero su azioni chiave (navigator.vibrate)
 *  5. Long-press su elementi con [title] → popover Bootstrap invece di tooltip
 *  6. Pull-to-refresh visivo su #main (richiede ≥80px pull verso il basso)
 */

(function () {
  'use strict';

  var MOBILE_BP   = 768;
  var EDGE_ZONE   = 30;   // px dalla sinistra per inizio edge-swipe
  var SWIPE_MIN   = 60;   // px minimi per registrare lo swipe come intento
  var SWIPE_RATIO = 2.0;  // dx/dy minimo per swipe orizzontale
  var PTR_PULL    = 80;   // px pull verso il basso per pull-to-refresh

  function isMobile() { return window.innerWidth <= MOBILE_BP; }

  /* ─── Haptic feedback ─────────────────────────────────────────────────── */
  function vibrate(ms) {
    try { if (navigator.vibrate) navigator.vibrate(ms || 8); } catch (_) {}
  }
  // Esponi globalmente per poterla usare da swipe-delete in base.html
  window.pctVibrate = vibrate;

  /* ─── 1. Edge-swipe → apre/chiude sidebar ────────────────────────────── */
  (function initSidebarSwipe() {
    var sb      = document.getElementById('sidebar');
    var ov      = document.getElementById('sb-overlay');
    var bn      = document.getElementById('bottom-nav');
    var bnh     = document.getElementById('bn-handle');
    if (!sb) return;

    var startX, startY, tracking = false, swipeSource = null;

    function openDrawer() {
      sb.classList.add('sb-open');
      if (ov) ov.classList.add('sb-open');
      if (isMobile() && bn)  bn.classList.add('bn-hidden');
      if (isMobile() && bnh) bnh.classList.add('bn-hidden');
      vibrate(6);
    }
    function closeDrawer() {
      sb.classList.remove('sb-open');
      if (ov) ov.classList.remove('sb-open');
      if (isMobile() && bn  && localStorage.getItem('pct-bn-hidden') !== '1') bn.classList.remove('bn-hidden');
      if (isMobile() && bnh && localStorage.getItem('pct-bn-hidden') !== '1') bnh.classList.remove('bn-hidden');
      vibrate(6);
    }

    document.addEventListener('touchstart', function (e) {
      if (!isMobile()) return;
      var t = e.touches[0];
      startX = t.clientX;
      startY = t.clientY;
      tracking = false;
      // Swipe da bordo sinistro: area ≤ EDGE_ZONE
      if (startX <= EDGE_ZONE && !sb.classList.contains('sb-open')) {
        swipeSource = 'edge';
      }
      // Swipe sinistro quando sidebar è aperta
      else if (sb.classList.contains('sb-open')) {
        swipeSource = 'close';
      } else {
        swipeSource = null;
      }
    }, { passive: true });

    document.addEventListener('touchmove', function (e) {
      if (!isMobile() || !swipeSource) return;
      var t = e.touches[0];
      var dx = t.clientX - startX;
      var dy = t.clientY - startY;

      // Verifica che sia prevalentemente orizzontale
      if (!tracking) {
        if (Math.abs(dx) < 6 && Math.abs(dy) < 6) return;
        if (Math.abs(dy) > Math.abs(dx) * (1 / SWIPE_RATIO)) {
          swipeSource = null; // scroll verticale prevale
          return;
        }
        tracking = true;
      }

      if (swipeSource === 'edge' && dx > 0) {
        // Trascina il drawer proporzionalmente durante il gesto
        var progress = Math.min(1, dx / 240);
        sb.style.transform = 'translateX(' + (-240 + progress * 240) + 'px)';
        sb.style.transition = 'none';
      } else if (swipeSource === 'close' && dx < 0) {
        var pClose = Math.min(1, Math.abs(dx) / 240);
        sb.style.transform = 'translateX(' + (-pClose * 240) + 'px)';
        sb.style.transition = 'none';
      }
    }, { passive: true });

    document.addEventListener('touchend', function (e) {
      if (!isMobile() || !swipeSource || !tracking) {
        sb.style.transform = '';
        sb.style.transition = '';
        swipeSource = null;
        return;
      }
      var t = e.changedTouches[0];
      var dx = t.clientX - startX;
      sb.style.transform = '';
      sb.style.transition = '';

      if (swipeSource === 'edge' && dx >= SWIPE_MIN) {
        openDrawer();
      } else if (swipeSource === 'close' && dx <= -SWIPE_MIN) {
        closeDrawer();
      }
      swipeSource = null;
      tracking = false;
    }, { passive: true });
  })();

  /* ─── 2. FAB auto-hide su scroll verso il basso ─────────────────────── */
  (function initFabScroll() {
    var main = document.getElementById('main');
    if (!main) return;

    var lastScrollY = 0;
    var ticking     = false;

    main.addEventListener('scroll', function () {
      if (!ticking) {
        requestAnimationFrame(function () {
          var fabs = document.querySelectorAll('.mob-fab, #pct-ai-fab');
          var scrollY  = main.scrollTop;
          var goingDown = scrollY > lastScrollY + 4;
          var goingUp   = scrollY < lastScrollY - 4;

          if (goingDown) {
            fabs.forEach(function (f) {
              f.style.transform = 'scale(0) translateY(20px)';
              f.style.opacity   = '0';
              f.style.pointerEvents = 'none';
            });
          } else if (goingUp) {
            fabs.forEach(function (f) {
              f.style.transform = '';
              f.style.opacity   = '';
              f.style.pointerEvents = '';
            });
          }
          lastScrollY = scrollY;
          ticking = false;
        });
        ticking = true;
      }
    }, { passive: true });
  })();

  /* ─── 3. Long-press su [title] → popover Bootstrap ──────────────────── */
  (function initLongPressPopover() {
    if (!isMobile()) return;
    var LONG_PRESS_MS = 500;
    // WeakMap: evita di salvare il timer numerico in dataset (che lo converte in stringa)
    var _timers = new WeakMap();

    document.addEventListener('pointerdown', function (e) {
      var el = e.target.closest('[title]');
      if (!el || !el.title) return;

      var timer = setTimeout(function () {
        vibrate(12);
        if (window.bootstrap && window.bootstrap.Popover) {
          var pop = bootstrap.Popover.getInstance(el);
          if (!pop) {
            pop = new bootstrap.Popover(el, {
              content: el.dataset.originalTitle || el.title,
              trigger: 'manual',
              placement: 'top',
              container: 'body',
            });
            // Salva il title originale e rimuovilo per evitare tooltip nativo
            if (!el.dataset.originalTitle) el.dataset.originalTitle = el.title;
            el.removeAttribute('title');
          }
          pop.show();
          setTimeout(function () { pop.hide(); }, 2500);
        }
      }, LONG_PRESS_MS);

      _timers.set(el, timer);

      function cancel() {
        clearTimeout(_timers.get(el));
        _timers.delete(el);
      }
      el.addEventListener('pointerup',     cancel, { once: true });
      el.addEventListener('pointermove',   cancel, { once: true });
      el.addEventListener('pointercancel', cancel, { once: true });
    });
  })();

  /* ─── 4. Pull-to-refresh su #main ───────────────────────────────────── */
  (function initPullToRefresh() {
    var main = document.getElementById('main');
    if (!main) return;

    var startY = 0, pulling = false, indicator = null;

    function mkIndicator() {
      indicator = document.createElement('div');
      indicator.id = 'pct-ptr-indicator';
      indicator.style.cssText = [
        'position:fixed',
        'top:' + (58 + (parseInt(getComputedStyle(document.documentElement)
          .getPropertyValue('--sat') || '0'))) + 'px',
        'left:50%',
        'transform:translateX(-50%) translateY(-60px)',
        'width:40px','height:40px',
        'background:#1a3a5c',
        'border-radius:50%',
        'display:flex','align-items:center','justify-content:center',
        'color:#fff','font-size:1.1rem',
        'z-index:9999',
        'box-shadow:0 2px 12px rgba(26,58,92,.4)',
        'transition:transform .18s cubic-bezier(.4,0,.2,1)',
        'pointer-events:none',
      ].join(';');
      indicator.innerHTML = '<i class="bi bi-arrow-clockwise" id="pct-ptr-icon"></i>';
      document.body.appendChild(indicator);
    }

    main.addEventListener('touchstart', function (e) {
      if (main.scrollTop <= 0) {
        startY = e.touches[0].clientY;
        pulling = false;
      }
    }, { passive: true });

    main.addEventListener('touchmove', function (e) {
      if (!startY || main.scrollTop > 0) return;
      var dy = e.touches[0].clientY - startY;
      if (dy <= 0) return;

      if (!indicator) mkIndicator();
      var progress = Math.min(1, dy / PTR_PULL);
      var translateY = -60 + progress * 70;
      indicator.style.transform = 'translateX(-50%) translateY(' + translateY + 'px)';

      var icon = document.getElementById('pct-ptr-icon');
      if (icon) icon.style.transform = 'rotate(' + (progress * 360) + 'deg)';

      if (dy >= PTR_PULL && !pulling) {
        pulling = true;
        vibrate(15);
        if (icon) icon.className = 'bi bi-arrow-repeat';
      } else if (dy < PTR_PULL && pulling) {
        pulling = false;
        if (icon) icon.className = 'bi bi-arrow-clockwise';
      }
    }, { passive: true });

    main.addEventListener('touchend', function () {
      if (indicator) {
        indicator.style.transform = 'translateX(-50%) translateY(-60px)';
        setTimeout(function () {
          if (indicator) { indicator.remove(); indicator = null; }
        }, 200);
      }
      if (pulling) {
        pulling = false;
        startY  = 0;
        // Mostra spinner breve poi ricarica
        var sp = document.createElement('div');
        sp.style.cssText = 'position:fixed;top:50%;left:50%;transform:translate(-50%,-50%);z-index:9999;background:rgba(255,255,255,.9);padding:1rem;border-radius:50%;box-shadow:0 2px 12px rgba(0,0,0,.15)';
        sp.innerHTML = '<div class="spinner-border text-primary" style="width:2rem;height:2rem"></div>';
        document.body.appendChild(sp);
        setTimeout(function () { window.location.reload(); }, 400);
      }
      startY = 0;
    }, { passive: true });
  })();

})();
