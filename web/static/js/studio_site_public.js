(function () {
  const navToggle = document.querySelector(".studio-site-nav-toggle");
  const nav = document.getElementById("studioSiteNav");
  if (navToggle && nav) {
    navToggle.addEventListener("click", () => {
      const expanded = navToggle.getAttribute("aria-expanded") === "true";
      navToggle.setAttribute("aria-expanded", expanded ? "false" : "true");
      nav.classList.toggle("is-open", !expanded);
    });
  }

  const cookieBanner = document.querySelector("[data-cookie-banner]");
  if (cookieBanner) {
    const storageKey = "iusentra_site_cookie_consent";
    const current = window.localStorage.getItem(storageKey);
    const applyAnalytics = () => {
      const configNode = document.getElementById("studioSiteAnalyticsConfig");
      if (!configNode) return;
      let config = {};
      try {
        config = JSON.parse(configNode.textContent || "{}");
      } catch (_error) {
        config = {};
      }
      if (!config.provider || !config.id) return;
      window.dispatchEvent(new CustomEvent("studio-site:analytics-consent", { detail: config }));
    };
    if (!current) {
      cookieBanner.hidden = false;
    } else if (current === "analytics") {
      applyAnalytics();
    }
    const accept = cookieBanner.querySelector("[data-cookie-accept]");
    const reject = cookieBanner.querySelector("[data-cookie-reject]");
    if (accept) {
      accept.addEventListener("click", () => {
        window.localStorage.setItem(storageKey, "analytics");
        cookieBanner.hidden = true;
        applyAnalytics();
      });
    }
    if (reject) {
      reject.addEventListener("click", () => {
        window.localStorage.setItem(storageKey, "necessary");
        cookieBanner.hidden = true;
      });
    }
  }

  const officeField = document.getElementById("siteBookingOffice");
  const dateField = document.getElementById("siteBookingDate");
  const timeField = document.getElementById("siteBookingTime");

  if (!officeField || !dateField || !timeField) {
    return;
  }

  const buildUrl = () => {
    const baseUrl = officeField.dataset.slotsUrl || "";
    const officeId = officeField.value || "";
    const requestedDate = dateField.value || "";
    if (!baseUrl || !officeId || !requestedDate) {
      return "";
    }
    const url = new URL(baseUrl, window.location.origin);
    url.searchParams.set("office_id", officeId);
    url.searchParams.set("data", requestedDate);
    return url.toString();
  };

  const setPlaceholder = (label) => {
    timeField.innerHTML = "";
    const option = document.createElement("option");
    option.value = "";
    option.textContent = label;
    timeField.appendChild(option);
  };

  const loadSlots = async () => {
    const targetUrl = buildUrl();
    if (!targetUrl) {
      setPlaceholder("Seleziona prima sede e data");
      return;
    }

    setPlaceholder("Caricamento fasce disponibili...");
    try {
      const response = await fetch(targetUrl, { headers: { Accept: "application/json" } });
      const payload = await response.json();
      const rows = Array.isArray(payload.slots) ? payload.slots : [];
      timeField.innerHTML = "";
      if (!rows.length) {
        setPlaceholder("Nessuna fascia disponibile per la data selezionata");
        return;
      }
      const placeholder = document.createElement("option");
      placeholder.value = "";
      placeholder.textContent = "Seleziona una fascia oraria";
      timeField.appendChild(placeholder);
      rows.forEach((row) => {
        const option = document.createElement("option");
        option.value = row.time || "";
        option.textContent = row.label || row.time || "";
        timeField.appendChild(option);
      });
    } catch (_error) {
      setPlaceholder("Impossibile caricare le fasce disponibili");
    }
  };

  officeField.addEventListener("change", loadSlots);
  dateField.addEventListener("change", loadSlots);
})();
