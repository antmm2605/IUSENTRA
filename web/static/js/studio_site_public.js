/* ================================================================
   IUSENTRA — Sito Studio Pubblico
   Gestione nav mobile (drawer), cookie banner, prenotazioni.
   ================================================================ */
(function () {
  "use strict";

  // ================================================================
  //  NAV MOBILE — Drawer slide-in professionale
  // ================================================================
  const toggle   = document.querySelector(".studio-site-nav-toggle");
  const nav      = document.getElementById("studioSiteNav");
  const backdrop = document.getElementById("studioSiteNavBackdrop");

  const MOBILE_BP = 992; // px — breakpoint tablet/desktop

  function openNav() {
    if (!nav || !toggle) return;
    nav.classList.add("is-open");
    toggle.setAttribute("aria-expanded", "true");
    toggle.querySelector("i").className = "bi bi-x-lg";
    toggle.querySelector("span").textContent = "Chiudi";
    if (backdrop) {
      backdrop.classList.add("is-open");
      backdrop.removeAttribute("aria-hidden");
    }
    document.body.style.overflow = "hidden";
    // Focus al primo link per accessibilità
    const firstLink = nav.querySelector("a");
    if (firstLink) setTimeout(() => firstLink.focus(), 50);
  }

  function closeNav() {
    if (!nav || !toggle) return;
    nav.classList.remove("is-open");
    toggle.setAttribute("aria-expanded", "false");
    toggle.querySelector("i").className = "bi bi-list";
    toggle.querySelector("span").textContent = "Menu";
    if (backdrop) {
      backdrop.classList.remove("is-open");
      backdrop.setAttribute("aria-hidden", "true");
    }
    document.body.style.overflow = "";
  }

  function toggleNav() {
    const isOpen = toggle && toggle.getAttribute("aria-expanded") === "true";
    isOpen ? closeNav() : openNav();
  }

  if (toggle) toggle.addEventListener("click", toggleNav);
  if (backdrop) backdrop.addEventListener("click", closeNav);

  // Pulsante chiudi dentro il drawer
  document.querySelectorAll(".studio-site-nav-close").forEach(function (btn) {
    btn.addEventListener("click", closeNav);
  });

  // Chiudi con ESC
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeNav();
  });

  // Chiudi automaticamente al cambio dimensione → desktop
  window.addEventListener("resize", function () {
    if (!isMobile()) closeNav();
  });

  // Evidenzia la voce di menu attiva
  (function highlightActiveLink() {
    if (!nav) return;
    const currentPath = window.location.pathname;
    nav.querySelectorAll("a").forEach(function (link) {
      const href = link.getAttribute("href") || "";
      if (href && (currentPath === href || (href !== "/" && currentPath.startsWith(href)))) {
        link.classList.add("is-active");
        link.setAttribute("aria-current", "page");
      }
    });
  })();

  // ================================================================
  //  SCROLL SMOOTH — solo su browser che lo supportano nativamente
  // ================================================================
  document.querySelectorAll('a[href^="#"]').forEach(function (anchor) {
    anchor.addEventListener("click", function (e) {
      const target = document.querySelector(anchor.getAttribute("href"));
      if (!target) return;
      e.preventDefault();
      closeNav();
      target.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  });

  // ================================================================
  //  COOKIE BANNER
  // ================================================================
  const cookieBanner = document.querySelector("[data-cookie-banner]");
  if (cookieBanner) {
    const storageKey = "iusentra_site_cookie_consent";
    const current = window.localStorage.getItem(storageKey);

    const applyAnalytics = function () {
      const configNode = document.getElementById("studioSiteAnalyticsConfig");
      if (!configNode) return;
      var config = {};
      try { config = JSON.parse(configNode.textContent || "{}"); } catch (_e) { config = {}; }
      if (!config.provider || !config.id) return;
      window.dispatchEvent(
        new CustomEvent("studio-site:analytics-consent", { detail: config })
      );
    };

    if (!current) {
      cookieBanner.hidden = false;
    } else if (current === "analytics") {
      applyAnalytics();
    }

    var accept = cookieBanner.querySelector("[data-cookie-accept]");
    var reject = cookieBanner.querySelector("[data-cookie-reject]");
    if (accept) {
      accept.addEventListener("click", function () {
        window.localStorage.setItem(storageKey, "analytics");
        cookieBanner.hidden = true;
        applyAnalytics();
      });
    }
    if (reject) {
      reject.addEventListener("click", function () {
        window.localStorage.setItem(storageKey, "necessary");
        cookieBanner.hidden = true;
      });
    }
  }

  // ================================================================
  //  PRENOTAZIONE — caricamento fasce orarie
  // ================================================================
  var officeField = document.getElementById("siteBookingOffice");
  var dateField   = document.getElementById("siteBookingDate");
  var timeField   = document.getElementById("siteBookingTime");

  if (!officeField || !dateField || !timeField) return;

  function buildSlotsUrl() {
    var baseUrl     = officeField.dataset.slotsUrl || "";
    var officeId    = officeField.value || "";
    var requestedDate = dateField.value || "";
    if (!baseUrl || !officeId || !requestedDate) return "";
    var url = new URL(baseUrl, window.location.origin);
    url.searchParams.set("office_id", officeId);
    url.searchParams.set("data", requestedDate);
    return url.toString();
  }

  function setTimePlaceholder(label) {
    timeField.innerHTML = "";
    var opt = document.createElement("option");
    opt.value = "";
    opt.textContent = label;
    timeField.appendChild(opt);
  }

  async function loadSlots() {
    var targetUrl = buildSlotsUrl();
    if (!targetUrl) {
      setTimePlaceholder("Seleziona prima sede e data");
      return;
    }
    setTimePlaceholder("Caricamento fasce disponibili…");
    try {
      var response = await fetch(targetUrl, { headers: { Accept: "application/json" } });
      var payload  = await response.json();
      var rows     = Array.isArray(payload.slots) ? payload.slots : [];
      timeField.innerHTML = "";
      if (!rows.length) {
        setTimePlaceholder("Nessuna fascia disponibile per la data selezionata");
        return;
      }
      var ph = document.createElement("option");
      ph.value = "";
      ph.textContent = "Seleziona una fascia oraria";
      timeField.appendChild(ph);
      rows.forEach(function (row) {
        var opt = document.createElement("option");
        opt.value = row.time || "";
        opt.textContent = row.label || row.time || "";
        timeField.appendChild(opt);
      });
    } catch (_err) {
      setTimePlaceholder("Impossibile caricare le fasce disponibili");
    }
  }

  officeField.addEventListener("change", loadSlots);
  dateField.addEventListener("change", loadSlots);
})();
