// Il contenitore IUSENTRA gestisce il proprio ciclo di vita e resta isolato.
// Un service worker del componente autonomo non deve intervenire nel contenitore.
export async function registerStandaloneOffline({ hosted, protocol, navigator }) {
  if (hosted || protocol !== 'https:') return false;
  try {
    const worker = navigator.serviceWorker;
    if (!worker) return false;
    const registration = await worker.register('sw.js', { updateViaCache: 'none' });
    await registration.update();
    return true;
  } catch {
    // Capacità opzionale del solo componente autonomo: alcune policy del
    // browser ne vietano persino la lettura. I comandi PDF restano disponibili.
    return false;
  }
}
