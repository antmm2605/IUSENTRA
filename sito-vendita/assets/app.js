/* IUSENTRA — sito di vendita: animazioni, vetrina a schede e modulo demo. */
(function () {
  "use strict";

  var radice = document.documentElement;
  var ridotto = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  radice.classList.add("js");

  /* La catena in apertura: ogni anello si accende dopo il precedente, poi ricomincia. */
  var catena = document.getElementById("catena");
  var orologio = document.getElementById("catena-orologio");
  if (catena && !ridotto) {
    var anelli = catena.querySelectorAll(".anello");
    var orari = ["09:14", "09:14", "09:15", "09:15", "09:15", "09:16"];
    var indice = -1;
    catena.classList.add("in-corso");
    var accendi = function () {
      indice = indice >= anelli.length ? -1 : indice + 1;
      anelli.forEach(function (a, i) {
        a.classList.toggle("acceso", i <= indice);
        a.classList.toggle("attuale", i === indice);
      });
      if (orologio && indice >= 0 && indice < orari.length) orologio.textContent = orari[indice];
      setTimeout(accendi, indice >= anelli.length - 1 ? 3200 : 1100);
    };
    setTimeout(accendi, 500);
  }

  /* Frasi dei comandi vocali. */
  var frase = document.querySelector('[data-giro="voce"]');
  if (frase && !ridotto) {
    var frasi = ["«Apri lo scadenziario»", "«Nuovo cliente: Marco Rossi»", "«Nota vocale: richiamare il CTU domani»", "«Lex, quando scade l'appello?»"];
    var f = 0;
    setInterval(function () { f = (f + 1) % frasi.length; frase.textContent = frasi[f]; }, 2600);
  }

  /* Ricevute del deposito. */
  var ricevute = document.querySelectorAll(".ricevute li");
  if (ricevute.length) {
    if (ridotto) {
      ricevute.forEach(function (li) { li.classList.add("fatto"); });
    } else {
      var passo = 0;
      var avanza = function () {
        ricevute.forEach(function (li, i) {
          li.classList.toggle("fatto", i < passo);
          li.classList.toggle("attesa", i === passo);
        });
        passo = passo > ricevute.length ? 0 : passo + 1;
      };
      avanza();
      setInterval(avanza, 1300);
    }
  }

  /* Vetrina a schede: scorre da sola finché il visitatore non sceglie una voce. */
  var corpo = document.querySelector(".vetrina-corpo");
  var schede = Array.prototype.slice.call(document.querySelectorAll(".scheda"));
  var titolo = document.getElementById("vetrina-titolo");
  var timerSchede = null;
  var mostra = function (scheda, daUtente) {
    schede.forEach(function (s) {
      var attiva = s === scheda;
      s.setAttribute("aria-selected", String(attiva));
      s.tabIndex = attiva ? 0 : -1;
      var pannello = document.getElementById(s.getAttribute("aria-controls"));
      if (pannello) pannello.hidden = !attiva;
      if (attiva && pannello && titolo) titolo.textContent = "iusentra · " + pannello.getAttribute("data-titolo");
    });
    if (daUtente) {
      clearInterval(timerSchede);
      timerSchede = null;
      if (corpo) corpo.classList.add("fermo");
    }
  };
  schede.forEach(function (s, i) {
    s.addEventListener("click", function () { mostra(s, true); });
    s.addEventListener("keydown", function (e) {
      var d = e.key === "ArrowDown" || e.key === "ArrowRight" ? 1 : e.key === "ArrowUp" || e.key === "ArrowLeft" ? -1 : 0;
      if (!d) return;
      e.preventDefault();
      var prossima = schede[(i + d + schede.length) % schede.length];
      mostra(prossima, true);
      prossima.focus();
    });
  });
  if (schede.length && corpo && !ridotto && "IntersectionObserver" in window) {
    var avviaSchede = function () {
      if (timerSchede || corpo.classList.contains("fermo")) return;
      timerSchede = setInterval(function () {
        var attuale = schede.findIndex(function (s) { return s.getAttribute("aria-selected") === "true"; });
        mostra(schede[(attuale + 1) % schede.length], false);
      }, 7000);
    };
    new IntersectionObserver(function (voci) {
      voci.forEach(function (v) {
        if (v.isIntersecting) avviaSchede();
        else { clearInterval(timerSchede); timerSchede = null; }
      });
    }, { threshold: 0.35 }).observe(corpo);
  } else if (corpo) {
    corpo.classList.add("fermo");
  }

  /* Comparsa leggera delle sezioni: il contenuto resta sempre visibile. */
  if (!ridotto && "IntersectionObserver" in window) {
    var daMostrare = document.querySelectorAll(".confronto-tabella, .ora, .vetrina-corpo, .moduli-griglia li, .intermezzo, .norme, .piano, .modulo");
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
  var aggiorna = function () {
    var alto = radice.scrollHeight - window.innerHeight;
    if (barraLettura) barraLettura.style.transform = "scaleX(" + (alto > 0 ? Math.min(1, window.scrollY / alto) : 0) + ")";
    if (ctaMobile && apertura && demo) {
      var oltreApertura = apertura.getBoundingClientRect().bottom < 0;
      var allaDemo = demo.getBoundingClientRect().top < window.innerHeight;
      ctaMobile.hidden = !oltreApertura || allaDemo;
    }
  };
  window.addEventListener("scroll", aggiorna, { passive: true });
  window.addEventListener("resize", aggiorna);
  aggiorna();

  /* Modulo demo: controllo dei campi. L'invio reale va collegato al servizio scelto. */
  var modulo = document.getElementById("modulo-demo");
  var esito = document.getElementById("modulo-esito");
  if (modulo && esito) {
    modulo.addEventListener("submit", function (evento) {
      evento.preventDefault();
      var nome = modulo.elements.nome;
      var email = modulo.elements.email;
      var privacy = modulo.elements.privacy;
      var errori = [];
      nome.setAttribute("aria-invalid", String(!nome.value.trim()));
      email.setAttribute("aria-invalid", String(!email.validity.valid || !email.value));
      if (!nome.value.trim()) errori.push("il nome");
      if (!email.value || !email.validity.valid) errori.push("un'email valida");
      if (!privacy.checked) errori.push("il consenso privacy");
      if (errori.length) {
        esito.className = "modulo-esito errore";
        esito.textContent = "Per prenotare manca " + errori.join(", ") + ".";
        return;
      }
      esito.className = "modulo-esito ok";
      esito.textContent = "Modulo compilato correttamente. L'invio della richiesta verrà attivato alla messa online del sito.";
      modulo.reset();
    });
  }
})();
