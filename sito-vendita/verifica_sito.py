"""Controlli browser del sito statico. Richiede Playwright solo nell'ambiente di verifica."""
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

parser = argparse.ArgumentParser()
parser.add_argument('url', nargs='?', default='http://127.0.0.1:8080/')
parser.add_argument('--output', default='/tmp/iusentra-sito-verifica')
args = parser.parse_args()
output = Path(args.output)
output.mkdir(parents=True, exist_ok=True)

with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', args=['--no-sandbox'])
    for device, width, height in [('desktop', 1440, 1000), ('notebook', 1366, 768),
                                   ('tablet', 820, 1180), ('mobile', 390, 844), ('small', 320, 740)]:
        page = browser.new_page(viewport={'width': width, 'height': height})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.goto(args.url, wait_until='networkidle')
        expect(page.locator('h1')).to_contain_text('Il tuo tempo.')
        page.screenshot(path=str(output / f'{device}-apertura.png'))
        # First-screen comparison and voice example remain illustrative and reversible.
        page.locator('#vista-prima').click()
        expect(page.locator('#pratica-dispersa')).to_be_visible()
        expect(page.locator('#pratica-collegata')).to_be_hidden()
        page.locator('#collega-pratica').click()
        expect(page.locator('#vista-collegata')).to_have_attribute('aria-pressed', 'true')
        expect(page.locator('#pratica-collegata')).to_be_visible()
        # The illustration has distinct preparation, confirmation and replay states.
        page.locator('#prova-catena').click()
        expect(page.locator('#prova-catena')).to_have_text('Conferma nell’esempio →')
        expect(page.locator('.catena.confermata')).to_have_count(0)
        page.locator('#prova-catena').click()
        expect(page.locator('.catena.confermata')).to_have_count(1)
        page.locator('#prova-catena').click()
        expect(page.locator('#prova-catena')).to_have_text('Conferma nell’esempio →')
        # Every preference controls its preview and the closing recap without jumping away.
        for key, title in [('pec', 'PEC e scadenze'), ('editor', 'Atti e depositi'), ('portale', 'Clienti e parcelle')]:
            choice = page.locator(f'[data-scelta="{key}"]')
            choice.scroll_into_view_if_needed()
            page.wait_for_timeout(100)
            before = page.evaluate('scrollY')
            choice.click()
            expect(choice).to_have_attribute('aria-pressed', 'true')
            expect(page.locator(f'#p-{key}')).to_be_visible()
            expect(page.locator('#percorso-finale')).to_have_text(title)
            assert abs(page.evaluate('scrollY') - before) < 3, 'La scelta ha interrotto la lettura'
            if width <= 1020:
                tab_box = page.locator(f'#t-{key}').bounding_box()
                list_box = page.locator('.schede').bounding_box()
                assert tab_box['x'] >= list_box['x'], 'Scheda selezionata fuori dalla fila'
                assert tab_box['x'] + tab_box['width'] <= list_box['x'] + list_box['width']
        page.locator('#scelta-link').click()
        page.wait_for_timeout(800)
        page.screenshot(path=str(output / f'{device}-vetrina.png'))
        page.locator('#prova-voce').click()
        expect(page.locator('#voce-esito')).to_contain_text('Termine da verificare e confermare.')
        expect(page.locator('#prova-voce')).to_be_enabled()
        # All ten tabs keep the selected state; keyboard Home/End and arrows work.
        for tab in page.locator('.scheda').all():
            tab.click()
            expect(tab).to_have_attribute('aria-selected', 'true')
            expect(page.locator('#' + tab.get_attribute('aria-controls'))).to_be_visible()
        page.locator('#t-sito').focus()
        page.keyboard.press('Home')
        expect(page.locator('#t-agenda')).to_be_focused()
        page.keyboard.press('End')
        expect(page.locator('#t-sito')).to_be_focused()
        page.keyboard.press('ArrowRight')
        expect(page.locator('#t-agenda')).to_be_focused()
        page.wait_for_timeout(7200)
        expect(page.locator('#t-agenda')).to_have_attribute('aria-selected', 'true')
        expect(page.locator('.moduli-griglia li:visible')).to_have_count(8)
        page.locator('#moduli-toggle').click()
        expect(page.locator('.moduli-griglia li:visible')).to_have_count(16)
        page.locator('#moduli-toggle').click()
        expect(page.locator('.moduli-griglia li:visible')).to_have_count(8)
        page.locator('.norme-dettaglio summary').click()
        expect(page.locator('.norme li:visible')).to_have_count(10)
        for faq in page.locator('.domande summary').all():
            faq.click()
            expect(faq.locator('..')).to_have_attribute('open', '')
        page.locator('#percorso-select').select_option('editor')
        expect(page.locator('#percorso-finale')).to_have_text('Atti e depositi')
        page.evaluate('scrollTo(0, document.getElementById("demo").offsetTop - 84)')
        page.wait_for_timeout(800)
        page.screenshot(path=str(output / f'{device}-finale.png'))
        page.locator('#rivedi-percorso').click()
        expect(page.locator('#t-editor')).to_have_attribute('aria-selected', 'true')
        assert page.locator('form').count() == 0, 'Non deve esserci un modulo che promette invii'
        expect(page.locator('#demo')).to_contain_text('acquisti non sono ancora aperti')
        # Full natural scroll, fragment destinations and horizontal overflow.
        for anchor in page.locator('a[href^="#"]').all():
            target = anchor.get_attribute('href')[1:]
            assert page.locator('[id="' + target + '"]').count() == 1, target
        for y in range(0, page.evaluate('document.documentElement.scrollHeight'), 450):
            page.evaluate('(y) => scrollTo(0,y)', y)
            page.wait_for_timeout(25)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), f'Overflow {device}'
        assert not errors, errors
        page.screenshot(path=str(output / f'{device}-pagina.png'), full_page=True)
        print(f'{device}: percorso, 10 schede, tastiera, 16 funzioni, FAQ, finale, scroll senza overflow: OK')
        page.close()
    page = browser.new_page(reduced_motion='reduce')
    page.goto(args.url, wait_until='networkidle')
    page.locator('#prova-catena').click()
    expect(page.locator('#prova-catena')).to_have_text('Conferma nell’esempio →')
    page.locator('#prova-catena').click()
    expect(page.locator('.catena.confermata')).to_have_count(1)
    page.close()
    page = browser.new_page(java_script_enabled=False)
    page.goto(args.url, wait_until='networkidle')
    expect(page.locator('.pannello:visible')).to_have_count(10)
    expect(page.locator('.moduli-griglia li:visible')).to_have_count(16)
    print('Animazioni ridotte e contenuti senza JavaScript: OK')
    browser.close()
