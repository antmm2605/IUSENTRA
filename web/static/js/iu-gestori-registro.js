/*
 * Registro dei gestori evento dei template legacy.
 * Generato da scripts/csp_gestori_legacy.py: non modificare a mano l'elenco,
 * si rigenera dai template. Ogni voce e' il codice che stava in un attributo
 * on<evento>="..."; iu-gestori.js lo esegue con la stessa semantica.
 * Il file non e' in modalita' strict: serve lo scope dell'attributo (with).
 */
(function (R) {
R["g14a937e7d3"] = function (event, __v) { with (document) with (this.form || {}) with (this) {
toggleTema()
}}; /* fine g14a937e7d3 */
R["g27444d4efa"] = function (event, __v) { with (document) with (this.form || {}) with (this) {
pctNotifPanel.toggle(this)
}}; /* fine g27444d4efa */
R["g320b883d1e"] = function (event, __v) { with (document) with (this.form || {}) with (this) {
window.print()
}}; /* fine g320b883d1e */
R["g73d21adcd6"] = function (event, __v) { with (document) with (this.form || {}) with (this) {
history.back(); return false
}}; /* fine g73d21adcd6 */
R["g86945dcc07"] = function (event, __v) { with (document) with (this.form || {}) with (this) {
document.getElementById('sync-stale-banner').classList.remove('show')
}}; /* fine g86945dcc07 */
R["gab9e4c17dd"] = function (event, __v) { with (document) with (this.form || {}) with (this) {
return confirm('Revocare accesso a ' + __v[0] + '?')
}}; /* fine gab9e4c17dd */
R["gc5a13f1cbb"] = function (event, __v) { with (document) with (this.form || {}) with (this) {
document.getElementById('file_ics').click()
}}; /* fine gc5a13f1cbb */
R["gf603811aa1"] = function (event, __v) { with (document) with (this.form || {}) with (this) {
location.reload()
}}; /* fine gf603811aa1 */
R["gf83484882f"] = function (event, __v) { with (document) with (this.form || {}) with (this) {
PCT_NOTIFICHE.richiediPermesso()
}}; /* fine gf83484882f */
})(window.IU_GESTORI = window.IU_GESTORI || {});
