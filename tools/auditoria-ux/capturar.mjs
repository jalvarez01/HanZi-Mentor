/**
 * Auditoría UI/UX (T24): capturas + axe-core (WCAG 2.1 AA) de una versión
 * del frontend.
 *
 *   node capturar.mjs --version antes   --url http://localhost:5173
 *   node capturar.mjs --version despues --url http://localhost
 *   node capturar.mjs --version antes   --url http://localhost:5173 --solo error
 *
 * `--solo error` se corre con el servicio de progreso detenido (agente_tutor
 * en "antes", flask_progreso en "después"); el resto, con todo arriba.
 *
 * Cada captura usa un contexto nuevo: localStorage vacío = usuario nuevo sin
 * progreso. Service workers bloqueados para que la PWA no sirva caché vieja.
 *
 * Salidas:
 *   docs/wiki/img/auditoria-ux/<version>-*.png  (PNG con paleta, sharp)
 *   tools/auditoria-ux/reportes/<version>/*.json (axe completo + chequeos)
 */

import { mkdir, readFile, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import sharp from 'sharp';

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = resolve(AQUI, '..', '..');
const DIR_IMG = join(RAIZ, 'docs', 'wiki', 'img', 'auditoria-ux');

const { values: args } = parseArgs({
  options: {
    version: { type: 'string' },
    url: { type: 'string' },
    solo: { type: 'string' },
  },
});

if (!['antes', 'despues'].includes(args.version) || !args.url) {
  console.error('Uso: node capturar.mjs --version antes|despues --url <base> [--solo error]');
  process.exit(1);
}

const VERSION = args.version;
const BASE = args.url.replace(/\/$/, '');
const DIR_REP = join(AQUI, 'reportes', VERSION);

// Diferencias entre versiones: "antes" llamaba a contenido v1 directo.
const CONFIG = {
  antes: { patronCaracteres: '**/api/caracteres/**', i18n: false },
  despues: { patronCaracteres: '**/api/v2/caracteres/**', i18n: true },
}[VERSION];

const PAGINAS = [
  { id: 'inicio', ruta: '/' },
  { id: 'trazos', ruta: '/trazos' },
  { id: 'practica', ruta: '/practica' },
  { id: 'progreso', ruta: '/progreso' },
  { id: 'como-funciona', ruta: '/como-funciona' },
];

const VIEWPORTS = {
  375: { width: 375, height: 812 },
  1280: { width: 1280, height: 800 },
};

const ETIQUETAS_WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const CLAVE_IDIOMA = 'hanzi-mentor:idioma';

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

async function nuevoContexto(browser, ancho, { idioma } = {}) {
  const contexto = await browser.newContext({
    viewport: VIEWPORTS[ancho],
    deviceScaleFactor: 1,
    serviceWorkers: 'block',
    reducedMotion: 'reduce',
    locale: 'es-CO',
  });
  if (idioma) {
    await contexto.addInitScript(
      ([clave, valor]) => localStorage.setItem(clave, valor),
      [CLAVE_IDIOMA, idioma],
    );
  }
  return contexto;
}

async function abrir(pagina, ruta) {
  await pagina.goto(`${BASE}${ruta}`, { waitUntil: 'networkidle' });
  await pagina.evaluate(() => document.fonts.ready);
  await esperar(500);
}

async function guardarPng(nombre, buffer) {
  const optimizado = await sharp(buffer)
    .png({ palette: true, quality: 90, effort: 10, compressionLevel: 9 })
    .toBuffer();
  const ruta = join(DIR_IMG, `${VERSION}-${nombre}.png`);
  await writeFile(ruta, optimizado);
  return { archivo: ruta, bytes: optimizado.length };
}

async function guardarJson(nombre, datos) {
  await writeFile(join(DIR_REP, `${nombre}.json`), JSON.stringify(datos, null, 2));
}

async function medirAxe(pagina) {
  return new AxeBuilder({ page: pagina }).withTags(ETIQUETAS_WCAG).analyze();
}

/** Chequeos automáticos complementarios a axe. */
async function chequeos(pagina) {
  return pagina.evaluate(() => ({
    lang: document.documentElement.lang || null,
    titulo: document.title,
    desbordeHorizontal: document.documentElement.scrollWidth > window.innerWidth,
    scrollWidth: document.documentElement.scrollWidth,
    innerWidth: window.innerWidth,
    tieneMain: !!document.querySelector('main, [role="main"]'),
    h1: [...document.querySelectorAll('h1')].map((h) => h.textContent.trim()),
    pestanaActiva: document.querySelector('nav [aria-current="page"]')?.textContent.trim() ?? null,
    objetivosPequenos: [...document.querySelectorAll('a[href], button, input, select, textarea, [tabindex]')]
      .filter((el) => el.offsetParent !== null)
      .map((el) => {
        const r = el.getBoundingClientRect();
        return { texto: (el.textContent || el.getAttribute('aria-label') || '').trim().slice(0, 30), ancho: Math.round(r.width), alto: Math.round(r.height) };
      })
      .filter((o) => o.ancho < 44 || o.alto < 44),
  }));
}

/** Recorre con Tab y registra a qué elemento llega el foco en cada paso. */
async function secuenciaTab(pagina, pasos = 40) {
  const secuencia = [];
  for (let i = 0; i < pasos; i++) {
    await pagina.keyboard.press('Tab');
    const info = await pagina.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body) return null;
      const estilo = getComputedStyle(el);
      return {
        etiqueta: el.tagName.toLowerCase(),
        texto: (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 40),
        enNav: !!el.closest('nav'),
        outline: `${estilo.outlineStyle} ${estilo.outlineWidth} ${estilo.outlineColor}`,
        boxShadow: estilo.boxShadow,
      };
    });
    secuencia.push(info);
  }
  return secuencia;
}

/** Pulsa Tab hasta que `condicion` (evaluada en el navegador) sea cierta. */
async function tabHasta(pagina, condicion, maximo = 40) {
  for (let i = 0; i < maximo; i++) {
    await pagina.keyboard.press('Tab');
    if (await pagina.evaluate(condicion)) return true;
  }
  return false;
}

function resumirAxe(resultado) {
  const porImpacto = { critical: 0, serious: 0, moderate: 0, minor: 0 };
  const reglas = resultado.violations.map((v) => {
    porImpacto[v.impact] = (porImpacto[v.impact] ?? 0) + 1;
    return { id: v.id, impacto: v.impact, nodos: v.nodes.length, ayuda: v.help };
  });
  return { porImpacto, reglas };
}

async function capturasBase(browser, resumen) {
  for (const { id, ruta } of PAGINAS) {
    for (const ancho of Object.keys(VIEWPORTS)) {
      const contexto = await nuevoContexto(browser, ancho);
      const pagina = await contexto.newPage();
      await abrir(pagina, ruta);

      const img = await guardarPng(`${id}-${ancho}`, await pagina.screenshot({ fullPage: true }));
      const axe = await medirAxe(pagina);
      const extra = await chequeos(pagina);
      const tab = ancho === '1280' ? await secuenciaTab(pagina) : undefined;

      await guardarJson(`${id}-${ancho}`, { axe, chequeos: extra, secuenciaTab: tab });
      resumen.paginas[`${id}-${ancho}`] = { ...resumirAxe(axe), chequeos: extra, bytes: img.bytes };
      console.log(`${id}-${ancho}: ${axe.violations.length} reglas violadas`);
      resumen.axeCore ??= axe.testEngine.version;
      await contexto.close();
    }
  }
}

async function capturaCarga(browser, resumen) {
  const contexto = await nuevoContexto(browser, 375);
  const pagina = await contexto.newPage();
  // Retrasa el catálogo para dejar visible el estado de carga.
  await pagina.route(CONFIG.patronCaracteres, async (r) => {
    await esperar(4000);
    await r.continue().catch(() => {});
  });
  await pagina.goto(`${BASE}/trazos`, { waitUntil: 'domcontentloaded' });
  await esperar(1500);
  const img = await guardarPng('carga-trazos-375', await pagina.screenshot({ fullPage: true }));
  const anuncio = await pagina.evaluate(() =>
    [...document.querySelectorAll('[role="status"], [aria-live], [aria-busy="true"]')].map((el) => el.textContent.trim()),
  );
  resumen.estados.carga = { pagina: 'trazos', anunciosAccesibles: anuncio, bytes: img.bytes };
  await pagina.unrouteAll({ behavior: 'ignoreErrors' });
  await contexto.close();
}

async function capturasFoco(browser, resumen) {
  // Barra inferior en móvil.
  let contexto = await nuevoContexto(browser, 375);
  let pagina = await contexto.newPage();
  await abrir(pagina, '/');
  const enNav = await tabHasta(pagina, () => !!document.activeElement?.closest('nav'));
  let img = await guardarPng('foco-tabbar-375', await pagina.screenshot());
  resumen.estados.focoTabbar = { alcanzado: enNav, bytes: img.bytes };
  await contexto.close();

  // Primer control de contenido en Trazos (fuera de nav y header).
  contexto = await nuevoContexto(browser, 1280);
  pagina = await contexto.newPage();
  await abrir(pagina, '/trazos');
  const enContenido = await tabHasta(pagina, () => {
    const el = document.activeElement;
    return !!el && el !== document.body && !el.closest('nav, header');
  });
  await pagina.evaluate(() => document.activeElement?.scrollIntoView({ block: 'center' }));
  img = await guardarPng('foco-trazos-1280', await pagina.screenshot());
  resumen.estados.focoTrazos = { alcanzado: enContenido, bytes: img.bytes };
  await contexto.close();
}

async function capturasIdioma(browser, resumen) {
  resumen.estados.idioma = {};
  for (const id of ['inicio', 'progreso']) {
    const contexto = await nuevoContexto(browser, 375, { idioma: 'en' });
    const pagina = await contexto.newPage();
    await abrir(pagina, PAGINAS.find((p) => p.id === id).ruta);
    const img = await guardarPng(`en-${id}-375`, await pagina.screenshot({ fullPage: true }));
    const axe = await medirAxe(pagina);
    const extra = await chequeos(pagina);
    await guardarJson(`en-${id}-375`, { axe, chequeos: extra });
    resumen.estados.idioma[id] = { lang: extra.lang, ...resumirAxe(axe), bytes: img.bytes };
    await contexto.close();
  }
}

async function capturaError(browser, resumen) {
  const contexto = await nuevoContexto(browser, 375);
  const pagina = await contexto.newPage();
  await abrir(pagina, '/progreso');
  await esperar(2000);
  const img = await guardarPng('error-progreso-375', await pagina.screenshot({ fullPage: true }));
  const axe = await medirAxe(pagina);
  const aviso = await pagina.evaluate(() => ({
    alertas: [...document.querySelectorAll('[role="alert"]')].map((el) => el.textContent.trim()),
    textoError: [...document.querySelectorAll('.error, .hm-status--error')].map((el) => el.textContent.trim()),
    botones: [...document.querySelectorAll('button')].map((b) => b.textContent.trim()),
  }));
  await guardarJson('error-progreso-375', { axe, aviso });
  resumen.estados.error = { pagina: 'progreso', ...aviso, ...resumirAxe(axe), bytes: img.bytes };
  await contexto.close();
}

async function main() {
  await mkdir(DIR_IMG, { recursive: true });
  await mkdir(DIR_REP, { recursive: true });

  const browser = await chromium.launch({ channel: 'chrome' });
  const { version: playwright } = JSON.parse(
    await readFile(join(AQUI, 'node_modules', 'playwright', 'package.json'), 'utf8'),
  );
  const resumen = {
    version: VERSION,
    base: BASE,
    fecha: new Date().toISOString(),
    chrome: browser.version(),
    playwright,
    axeCore: null,
    etiquetas: ETIQUETAS_WCAG,
    paginas: {},
    estados: {},
  };

  try {
    if (args.solo === 'error') {
      await capturaError(browser, resumen);
      await guardarJson('resumen-error', resumen);
    } else {
      await capturasBase(browser, resumen);
      await capturaCarga(browser, resumen);
      await capturasFoco(browser, resumen);
      if (CONFIG.i18n) await capturasIdioma(browser, resumen);
      await guardarJson('resumen', resumen);
    }
  } finally {
    await browser.close();
  }
  console.log(`Listo: ${VERSION} (${Object.keys(resumen.paginas).length} páginas)`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
