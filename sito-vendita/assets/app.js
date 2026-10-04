/* IUSENTRA — sito di vendita: animazioni e percorsi illustrativi. */
(function () {
  "use strict";

  var radice = document.documentElement;
  var ridotto = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  radice.classList.add("js");

  /* Un esempio attivato dal visitatore, mai un'operazione sul gestionale. */
  var catena = document.getElementById("catena");
  var prova = document.getElementById("prova-catena");
  var esitoCatena = document.getElementById("catena-esito");
  if (catena && prova && esitoCatena) {
    var anelli = Array.from(catena.querySelectorAll(".anello"));
    var statoCatena = "inizio";
    prova.addEventListener("click", function () {
      if (statoCatena === "pronta") {
        statoCatena = "confermata";
        catena.classList.add("confermata");
        anelli.forEach(function (a) { a.classList.add("acceso"); a.classList.remove("attuale"); });
        catena.querySelector(".anello-bottone").textContent = "Confermato";
        esitoCatena.textContent = "Nell’esempio, udienza e scadenze sono confermate. Il cliente può vedere l’aggiornamento sul portale.";
        prova.textContent = "Rivedi l’esempio ↺";
        return;
      }
      statoCatena = "in-corso";
      catena.classList.remove("confermata");
      catena.classList.add("in-corso");
      catena.querySelector(".anello-bottone").textContent = "Da confermare";
      anelli.forEach(function (a) { a.classList.remove("acceso", "attuale"); });
      prova.disabled = true;
      prova.textContent = "La PEC viene collegata…";
      esitoCatena.textContent = "Lettura, fascicolo, termini e agenda seguono la stessa comunicazione.";
      var passo = 0;
      var avanza = function () {
        anelli.forEach(function (a, i) {
          a.classList.toggle("acceso", i <= passo);
          a.classList.toggle("attuale", i === passo);
        });
        if (passo === anelli.length - 1) {
          statoCatena = "pronta";
          prova.disabled = false;
          prova.textContent = "Conferma nell’esempio →";
          esitoCatena.textContent = "Il percorso è pronto. Udienza, termini e aggiornamento cliente aspettano la tua conferma.";
          return;
        }
        passo++;
        setTimeout(avanza, ridotto ? 0 : 350);
      };
      avanza();
    });
  }

  document.querySelectorAll(".ricevute li").forEach(function (li) { li.classList.add("fatto"); });

  /* Le illustrazioni si animano quando visibili, senza cambiare scheda.
     Ogni sequenza si conclude: nessun movimento continuo durante la lettura. */
  if (!ridotto && "IntersectionObserver" in window) {
    var animazioni = new Map();
    var fermaPannello = function (pannello) {
      (animazioni.get(pannello) || []).forEach(clearTimeout);
      animazioni.delete(pannello);
      pannello.classList.remove("animato");
      pannello.querySelectorAll(".ricevute li").forEach(function (li) {
        li.classList.remove("attesa"); li.classList.add("fatto");
      });
    };
    var osservaPannelli = new IntersectionObserver(function (voci) {
      voci.forEach(function (v) {
        var pannello = v.target;
        fermaPannello(pannello);
        if (!v.isIntersecting) return;
        pannello.classList.add("animato");
        var timer = [];
        var ricevute = Array.from(pannello.querySelectorAll(".ricevute li"));
        ricevute.forEach(function (li, i) {
          li.classList.remove("fatto");
          if (i === 0) li.classList.add("attesa");
          timer.push(setTimeout(function () {
            li.classList.remove("attesa"); li.classList.add("fatto");
            if (ricevute[i + 1]) ricevute[i + 1].classList.add("attesa");
          }, (i + 1) * 850));
        });
        var frase = pannello.querySelector('[data-giro="voce"]');
        if (frase) {
          var frasi = ["«Apri lo scadenziario»", "«Nuovo cliente: Marco Rossi»", "«Nota vocale: richiamare il CTU domani»", "«Lex, quando scade l’appello?»"];
          frase.textContent = frasi[0];
          frasi.slice(1).forEach(function (testo, i) {
            timer.push(setTimeout(function () { frase.textContent = testo; }, (i + 1) * 2600));
          });
        }
        animazioni.set(pannello, timer);
      });
    }, { threshold: .15 });
    document.querySelectorAll(".pannello").forEach(function (pannello) { osservaPannelli.observe(pannello); });
  }

  /* Le schede restano sotto il controllo del visitatore. */
  var schede = Array.from(document.querySelectorAll(".scheda"));
  var titolo = document.getElementById("vetrina-titolo");
  var allineaScheda = function (scheda) {
    var lista = scheda.parentElement;
    if (lista.scrollWidth > lista.clientWidth) {
      var scarto = scheda.getBoundingClientRect().left - lista.getBoundingClientRect().left;
      lista.scrollTo({ left: lista.scrollLeft + scarto - 8, behavior: "instant" });
    }
  };
  var mostra = function (scheda) {
    schede.forEach(function (s) {
      var attiva = s === scheda;
      s.setAttribute("aria-selected", String(attiva));
      s.tabIndex = attiva ? 0 : -1;
      var pannello = document.getElementById(s.getAttribute("aria-controls"));
      if (pannello) pannello.hidden = !attiva;
      if (attiva && pannello && titolo) titolo.textContent = "iusentra · " + pannello.getAttribute("data-titolo");
    });
    allineaScheda(scheda);
  };
  var mobileSchede = window.matchMedia("(max-width: 1020px)");
  var orientaSchede = function () {
    document.querySelector(".schede").setAttribute("aria-orientation", mobileSchede.matches ? "horizontal" : "vertical");
  };
  orientaSchede();
  mobileSchede.addEventListener("change", orientaSchede);
  schede.forEach(function (s, i) {
    s.addEventListener("click", function () { mostra(s); });
    s.addEventListener("keydown", function (e) {
      var d = e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 0;
      var prossimo = e.key === "Home" ? 0 : e.key === "End" ? schede.length - 1 : d ? (i + d + schede.length) % schede.length : null;
      if (prossimo === null) return;
      e.preventDefault();
      mostra(schede[prossimo]);
      schede[prossimo].focus({ preventScroll: true });
    });
  });
  var percorsi = {
    pec: { testo: "Dalla PEC al fascicolo, con udienze e termini da confermare. Guarda il collegamento, poi esplora l’agenda.", titolo: "PEC e scadenze", tab: "pec", demo: "Il tuo percorso: una PEC, il fascicolo collegato e una scadenza da confermare." },
    editor: { testo: "I dati della pratica entrano nell’atto. Guarda l’editor, poi segui preparazione, firma e ricevute.", titolo: "Atti e depositi", tab: "editor", demo: "Il tuo percorso: un atto con i dati del fascicolo, la firma e il deposito." },
    portale: { testo: "Documenti, aggiornamenti e pagamenti nel portale del cliente. Guarda come si tiene insieme il rapporto con lo studio.", titolo: "Clienti e parcelle", tab: "portale", demo: "Il tuo percorso: documenti dal cliente, aggiornamenti e parcelle nella stessa pratica." }
  };
  var scelto = null;
  var aggiornaScelta = function (chiave) {
    scelto = chiave;
    var percorso = percorsi[chiave];
    document.querySelectorAll("[data-scelta]").forEach(function (b) { b.setAttribute("aria-pressed", String(b.dataset.scelta === chiave)); });
    document.getElementById("scelta-testo").textContent = percorso.testo;
    document.getElementById("scelta-link").textContent = "Esplora " + percorso.titolo.toLowerCase() + " ↓";
    document.getElementById("scelta-link").setAttribute("href", "#vetrina");
    document.getElementById("demo-contesto").textContent = percorso.demo;
    document.getElementById("percorso-finale").textContent = percorso.titolo;
    document.getElementById("percorso-descrizione").textContent = percorso.demo;
    var select = document.getElementById("percorso-select");
    if (select) select.value = chiave;
    var tab = document.getElementById("t-" + percorso.tab);
    if (tab) {
    /* Prepara la vetrina senza interrompere la lettura della sezione corrente. */
      schede.forEach(function (s) {
        var attiva = s === tab;
        s.setAttribute("aria-selected", String(attiva)); s.tabIndex = attiva ? 0 : -1;
        var panel = document.getElementById(s.getAttribute("aria-controls"));
        panel.hidden = !attiva;
        if (attiva && titolo) titolo.textContent = "iusentra · " + panel.getAttribute("data-titolo");
      });
      allineaScheda(tab);
    }
  };
  document.querySelectorAll("[data-scelta]").forEach(function (b) { b.addEventListener("click", function () { aggiornaScelta(b.dataset.scelta); }); });
  var sceltaFinale = document.getElementById("percorso-select");
  if (sceltaFinale) sceltaFinale.addEventListener("change", function () { aggiornaScelta(sceltaFinale.value); });
  document.getElementById("rivedi-percorso").addEventListener("click", function () {
    aggiornaScelta(scelto || sceltaFinale.value);
  });
  /* Otto funzioni aggiuntive su richiesta, tutte leggibili senza JavaScript. */
  var moduli = Array.from(document.querySelectorAll(".moduli-griglia li"));
  var espandi = document.getElementById("moduli-toggle");
  if (espandi) {
    moduli.slice(8).forEach(function (li) { li.hidden = true; });
    espandi.hidden = false;
    espandi.addEventListener("click", function () {
      var aperto = espandi.getAttribute("aria-expanded") === "true";
      moduli.slice(8).forEach(function (li) { li.hidden = aperto; });
      espandi.setAttribute("aria-expanded", String(!aperto));
      espandi.textContent = aperto ? "Scopri le altre 8 funzioni +" : "Mostra meno funzioni −";
    });
  }
  /* Le scene restano una pagina normale; l'indice segue il punto di lettura. */
  if ("IntersectionObserver" in window) {
    var sceneVisibili = new Map();
    var osservaScene = new IntersectionObserver(function (voci) {
      voci.forEach(function (v) { sceneVisibili.set(v.target.id, v.isIntersecting); });
      var prima = Array.from(document.querySelectorAll(".scena")).find(function (scena) { return sceneVisibili.get(scena.id); });
      if (!prima) return;
      document.querySelectorAll(".racconto-indice a").forEach(function (a) {
        var attivo = a.hash === "#" + prima.id;
        a.classList.toggle("attivo", attivo);
        if (attivo) a.setAttribute("aria-current", "step"); else a.removeAttribute("aria-current");
      });
    }, { rootMargin: "-20% 0px -35% 0px", threshold: 0 });
    document.querySelectorAll(".scena").forEach(function (scena) { osservaScene.observe(scena); });
  }

  /* Comparsa leggera delle sezioni: il contenuto resta sempre visibile. */
  if (!ridotto && "IntersectionObserver" in window) {
    var daMostrare = document.querySelectorAll(".confronto-tabella, .scena, .vetrina-corpo, .moduli-griglia li, .intermezzo, .norme, .piano, .percorso-finale-box");
    var osservatore = new IntersectionObserver(function (voci) {
      voci.forEach(function (v) {
        if (v.isIntersecting) { v.target.classList.add("visto"); osservatore.unobserve(v.target); }
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    daMostrare.forEach(function (el) {
      var r = el.getBoundingClientRect();
      if (r.top > window.innerHeight) { el.classList.add("sale"); osservatore.observe(el); }
    });
  }

  /* Barra di lettura e pulsante demo fisso sul telefono. */
  var barraLettura = document.getElementById("avanzamento");
  var ctaMobile = document.getElementById("cta-mobile");
  var apertura = document.getElementById("inizio");
  var demo = document.getElementById("demo");
  var capitoli = Array.from(document.querySelectorAll(".menu a"));
  var aggiorna = function () {
    var alto = radice.scrollHeight - window.innerHeight;
    if (barraLettura) barraLettura.style.transform = "scaleX(" + (alto > 0 ? Math.min(1, window.scrollY / alto) : 0) + ")";
    if (ctaMobile && apertura && demo) {
      var oltreApertura = apertura.getBoundingClientRect().bottom < 0;
      var allaDemo = demo.getBoundingClientRect().top < window.innerHeight;
      ctaMobile.hidden = !oltreApertura || allaDemo;
    }
    var capitolo = null;
    capitoli.forEach(function (link) {
      var sezione = document.querySelector(link.hash);
      if (sezione && sezione.getBoundingClientRect().top < window.innerHeight * .45) capitolo = link;
    });
    capitoli.forEach(function (link) {
      if (link === capitolo) link.setAttribute("aria-current", "location");
      else link.removeAttribute("aria-current");
    });
  };
  window.addEventListener("scroll", aggiorna, { passive: true });
  window.addEventListener("resize", aggiorna);
  aggiorna();

})();
