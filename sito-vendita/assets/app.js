/* IUSENTRA — sito di vendita: animazioni degli schizzi e modulo demo. */
(function () {
  "use strict";

  var ridotto = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /* Ricevute del deposito: si completano una dopo l'altra, poi ricominciano. */
  var ricevute = document.querySelectorAll(".schizzo-ricevute li");
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
      setInterval(avanza, 1400);
    }
  }

  /* Testi che si alternano negli schizzi. */
  var giri = {
    avviso: [
      "Nuova PEC dalla cancelleria collegata a RG 4512/2026",
      "Deposito RG 1188/2026 accettato dalla cancelleria",
      "Termine calcolato: memoria n. 2 entro il 29 dicembre 2026"
    ],
    cerca: ["decreto ingiuntivo", "Rossi c/ Bianchi", "art. 171-ter"]
  };
  if (!ridotto) {
    document.querySelectorAll("[data-giro]").forEach(function (el) {
      var voci = giri[el.getAttribute("data-giro")];
      if (!voci) return;
      var i = 0;
      setInterval(function () {
        i = (i + 1) % voci.length;
        el.textContent = voci[i];
      }, 3200);
    });
  }

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
