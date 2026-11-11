/**
 * Verificación del frontend de RF-IA-02 (curva de olvido): capturas a 375 y
 * 1280 px de "Próximos repasos" en Progreso y del inicio de una sesión de
 * Práctica con un repaso vencido primero, axe-core (WCAG 2.1 AA) a 375 px y
 * registro de peticiones.
 *
 *   node rf-ia-02.mjs --url http://localhost --usuario <uuid con repasos>
 *
 * `--usuario` debe tener repasos vencidos, de hoy y de los próximos días.
 * Los estados vacío y de error se simulan interceptando repasos/ en el
 * navegador: no se crean usuarios ni datos. La única escritura es la sesión
 * de Práctica que se crea al empezar (POST /api/v2/sesiones/); su id queda
 * en el resumen.
 *
 * Zona horaria del navegador: UTC. "Hoy" y "mañana" son días de calendario
 * en la zona del navegador, así que la misma agenda se agrupa distinto según
 * dónde esté el estudiante; fijarla hace la captura reproducible.
 *
 * Cada contexto es nuevo y bloquea los service workers, así la caché de la
 * PWA no muestra la versión anterior.
 *
 * Salidas:
 *   docs/wiki/img/rf-ia-02/*.png
 *   tools/auditoria-ux/reportes/rf-ia-02/{resumen,peticiones}.json
 */

import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import sharp from 'sharp';

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = resolve(AQUI, '..', '..');
const DIR_IMG = join(RAIZ, 'docs', 'wiki', 'img', 'rf-ia-02');
const DIR_REP = join(AQUI, 'reportes', 'rf-ia-02');

const { values: args } = parseArgs({
  options: { url: { type: 'string' }, usuario: { type: 'string' } },
});
if (!args.url || !args.usuario) {
  console.error('Uso: node rf-ia-02.mjs --url <base> --usuario <uuid con repasos>');
  process.exit(1);
}

const BASE = args.url.replace(/\/$/, '');
const USUARIO = args.usuario;
const VIEWPORTS = { 375: { width: 375, height: 812 }, 1280: { width: 1280, height: 800 } };
const ETIQUETAS_WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const CLAVE_USUARIO = 'hanzi-mentor:usuario-id';
const ZONA_HORARIA = 'UTC';
const RUTA_REPASOS = '**/api/v2/progreso/*/repasos/*';
const SECCION = 'section[aria-labelledby="progreso-repasos"]';

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
const resumen = {
  base: BASE,
  fecha: new Date().toISOString(),
  usuario: USUARIO,
  zonaHoraria: ZONA_HORARIA,
  axe: {},
  comprobaciones: {},
  capturas: [],
};
const peticiones = [];

async function contextoNuevo(browser, ancho) {
  const contexto = await browser.newContext({
    viewport: VIEWPORTS[ancho],
    deviceScaleFactor: 1,
    serviceWorkers: 'block',
    reducedMotion: 'reduce',
    locale: 'es-CO',
    timezoneId: ZONA_HORARIA,
  });
  await contexto.addInitScript(
    ([clave, valor]) => localStorage.setItem(clave, valor),
    [CLAVE_USUARIO, USUARIO],
  );
  return contexto;
}

/** Anota las peticiones de repasos/ y de sesiones/ con su estado. */
function registrarPeticiones(pagina, estado) {
  pagina.on('response', async (respuesta) => {
    const peticion = respuesta.request();
    const url = new URL(peticion.url());
    if (!/\/repasos\/$|\/api\/v2\/sesiones\/$/.test(url.pathname)) return;
    const fila = {
      caso: estado.caso,
      metodo: peticion.method(),
      ruta: url.pathname.replace(/[0-9a-f-]{36}/, '<usuario>') + url.search,
      estado: respuesta.status(),
    };
    if (peticion.method() === 'POST') {
      const datos = await respuesta.json().catch(() => null);
      fila.sesion_id = datos?.id;
      fila.ejercicios = datos?.ejercicios?.map((e) => `${e.caracter} ${e.tipo}${e.es_refuerzo ? ' refuerzo' : ''}`);
    }
    peticiones.push(fila);
  });
  pagina.on('requestfailed', (peticion) => {
    const url = new URL(peticion.url());
    if (!/\/repasos\/$/.test(url.pathname)) return;
    peticiones.push({
      caso: estado.caso,
      metodo: peticion.method(),
      ruta: url.pathname.replace(/[0-9a-f-]{36}/, '<usuario>') + url.search,
      estado: 'cortada en el navegador',
    });
  });
}

async function abrir(pagina, ruta) {
  await pagina.goto(`${BASE}${ruta}`, { waitUntil: 'networkidle' });
  await pagina.evaluate(() => document.fonts.ready);
  await esperar(400);
}

async function capturar(pagina, nombre, selector) {
  if (selector) {
    await pagina.locator(selector).first().evaluate((el) => el.scrollIntoView({ block: 'center' }));
    await esperar(250);
  }
  const optimizado = await sharp(await pagina.screenshot())
    .png({ palette: true, colors: 96, quality: 70, dither: 0.8, effort: 10, compressionLevel: 9 })
    .toBuffer();
  await writeFile(join(DIR_IMG, `${nombre}.png`), optimizado);
  resumen.capturas.push({ archivo: `${nombre}.png`, bytes: optimizado.length });
}

async function axe(pagina, nombre) {
  const resultado = await new AxeBuilder({ page: pagina }).withTags(ETIQUETAS_WCAG).analyze();
  resumen.axe[nombre] = resultado.violations.map((v) => ({
    id: v.id,
    impacto: v.impact,
    nodos: v.nodes.map((n) => n.target.join(' ')),
  }));
  const desborde = await pagina.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  comprobar(`${nombre}: sin desborde horizontal`, !desborde);
}

function comprobar(nombre, valor) {
  resumen.comprobaciones[nombre] = Boolean(valor);
  console.log(`${valor ? 'ok   ' : 'FALLA'} ${nombre}`);
}

// ------------------------------------------------------------------ Progreso

async function progresoConRepasos(browser, ancho) {
  const contexto = await contextoNuevo(browser, ancho);
  const pagina = await contexto.newPage();
  const estado = { caso: `progreso ${ancho}: con repasos` };
  registrarPeticiones(pagina, estado);

  await abrir(pagina, '/progreso');
  const seccion = pagina.locator(SECCION);
  await seccion.locator('.repaso').first().waitFor();

  const grupos = await seccion.locator('.repasos-grupo').evaluateAll((els) => els.map((e) => e.dataset.grupo));
  comprobar(`progreso ${ancho}: grupos en orden Vencidos, Hoy, Próximos`,
    JSON.stringify(grupos) === JSON.stringify(['vencidos', 'hoy', 'proximos']));

  const textos = async (grupo) => seccion
    .locator(`[data-grupo="${grupo}"] .repaso__cuando`)
    .allInnerTexts();
  const vencidos = await textos('vencidos');
  const hoy = await textos('hoy');
  const proximos = await textos('proximos');
  resumen[`textos-${ancho}`] = { vencidos, hoy, proximos };
  // hace() usa Intl con numeric "auto": "vencido hace 3 días", "vencido
  // anteayer", "vencido ayer", "vencido hace 5 horas".
  comprobar(`progreso ${ancho}: vencidos dicen "vencido" y el tiempo de hace()`,
    vencidos.length > 0 && vencidos.every((t) => /^vencido (hace .+|ayer|anteayer)$/.test(t)));
  comprobar(`progreso ${ancho}: hoy dice "hoy"`, hoy.length > 0 && hoy.every((t) => t === 'hoy'));
  comprobar(`progreso ${ancho}: próximos dicen "mañana" o "en N días"`,
    proximos.length > 0 && proximos.every((t) => t === 'mañana' || /^en \d+ días?$/.test(t)));
  const hanzi = await seccion.locator('.repaso__hanzi').evaluateAll((els) => els.map((e) => e.lang));
  comprobar(`progreso ${ancho}: cada carácter con lang="zh"`, hanzi.length > 0 && hanzi.every((l) => l === 'zh'));
  comprobar(`progreso ${ancho}: el bloque anterior "Próximo repaso" ya no está`,
    (await pagina.locator('#progreso-repaso').count()) === 0);

  if (ancho === 375) {
    await axe(pagina, 'progreso-repasos-375');

    // "Actualizar" de la página vuelve a pedir repasos/.
    estado.caso = 'progreso 375: Actualizar';
    const pedido = pagina.waitForRequest((r) => /\/repasos\//.test(r.url()));
    await pagina.locator('.progreso-acciones .hm-btn').click();
    await pedido;
    comprobar('progreso: "Actualizar" vuelve a pedir repasos/', true);
    await esperar(400);
  }
  await capturar(pagina, `progreso-repasos-${ancho}`, SECCION);
  await contexto.close();
}

async function progresoVacio(browser, ancho) {
  const contexto = await contextoNuevo(browser, ancho);
  const pagina = await contexto.newPage();
  registrarPeticiones(pagina, { caso: `progreso ${ancho}: vacío (simulado)` });
  await pagina.route(RUTA_REPASOS, (ruta) => ruta.fulfill({
    json: { usuario_id: USUARIO, momento: new Date().toISOString(), dias: 7, vencidos: [], proximos: [] },
  }));

  await abrir(pagina, '/progreso');
  const seccion = pagina.locator(SECCION);
  await seccion.locator('.hm-status--empty').waitFor();
  comprobar(`progreso ${ancho}: estado vacío con su texto`,
    (await seccion.locator('.hm-status--empty').innerText()) === 'No tenés repasos en los próximos 7 días.'
    && (await seccion.locator('.repasos-grupo').count()) === 0);

  if (ancho === 375) await axe(pagina, 'progreso-vacio-375');
  await capturar(pagina, `progreso-vacio-${ancho}`, SECCION);
  await contexto.close();
}

async function progresoError(browser, ancho) {
  const contexto = await contextoNuevo(browser, ancho);
  const pagina = await contexto.newPage();
  const estado = { caso: `progreso ${ancho}: error (simulado)` };
  registrarPeticiones(pagina, estado);
  await pagina.route(RUTA_REPASOS, (ruta) => ruta.abort('connectionrefused'));

  await abrir(pagina, '/progreso');
  const seccion = pagina.locator(SECCION);
  await seccion.locator('[role="alert"]').waitFor();
  comprobar(`progreso ${ancho}: error con "Reintentar" dentro de la sección`,
    (await seccion.locator('.repasos-reintentar').count()) === 1);
  comprobar(`progreso ${ancho}: el resto de la página sigue`,
    (await pagina.locator('.progreso-metricas').count()) === 1
    && (await pagina.locator('main > [role="alert"]').count()) === 0
    && (await pagina.locator('section[aria-labelledby="progreso-patrones"]').count()) === 1);

  if (ancho === 375) await axe(pagina, 'progreso-error-375');
  await capturar(pagina, `progreso-error-${ancho}`, SECCION);

  if (ancho === 375) {
    // "Reintentar" con el servicio de vuelta: aparece la lista.
    await pagina.unroute(RUTA_REPASOS);
    estado.caso = 'progreso 375: Reintentar';
    await seccion.locator('.repasos-reintentar').click();
    await seccion.locator('.repaso').first().waitFor();
    comprobar('progreso: "Reintentar" recupera la lista',
      (await seccion.locator('[role="alert"]').count()) === 0);
  }
  await contexto.close();
}

// ------------------------------------------------------------------ Práctica

/**
 * Empieza una sesión de HSK1 y captura su primer ejercicio. Se crea una sola
 * sesión: la captura de 1280 px es la misma página con otra ventana.
 */
async function practicaConVencido(browser) {
  const contexto = await contextoNuevo(browser, 375);
  const pagina = await contexto.newPage();
  registrarPeticiones(pagina, { caso: 'práctica: empezar sesión' });

  const repasos = await (await pagina.request.get(`${BASE}/api/v2/progreso/${USUARIO}/repasos/`)).json();
  const vencidos = repasos.vencidos.map((r) => r.caracter);

  await abrir(pagina, '/practica');
  const creada = pagina.waitForResponse(
    (r) => r.url().endsWith('/api/v2/sesiones/') && r.request().method() === 'POST',
  );
  await pagina.locator('.practica-nivel').first().click();
  const sesion = await (await creada).json();
  await pagina.locator('.practica-tarjeta').waitFor();
  await esperar(400);

  const caracteres = sesion.ejercicios.map((e) => e.caracter);
  resumen.sesionPractica = { id: sesion.id, ejercicios: caracteres, vencidosAntes: vencidos };
  comprobar('práctica: los primeros ejercicios son los vencidos, en orden',
    vencidos.length > 0 && JSON.stringify(caracteres.slice(0, vencidos.length)) === JSON.stringify(vencidos.slice(0, 4)));
  comprobar('práctica: el primero es repaso (es_refuerzo) de tipo significado',
    sesion.ejercicios[0].es_refuerzo === true && sesion.ejercicios[0].tipo === 'significado');
  comprobar('práctica: sin caracteres repetidos', new Set(caracteres).size === caracteres.length);
  comprobar('práctica: la tarjeta muestra el vencido y la etiqueta de refuerzo',
    (await pagina.locator('.practica-refuerzo').count()) === 1
    && (await pagina.locator('.practica-tarjeta').innerText()).includes(vencidos[0]));

  await axe(pagina, 'practica-vencido-375');
  await capturar(pagina, 'practica-vencido-375');
  await pagina.setViewportSize(VIEWPORTS[1280]);
  await esperar(500);
  await capturar(pagina, 'practica-vencido-1280');
  await contexto.close();
}

// ---------------------------------------------------------------------- main

await mkdir(DIR_IMG, { recursive: true });
await mkdir(DIR_REP, { recursive: true });
const browser = await chromium.launch();

for (const ancho of [375, 1280]) {
  await progresoConRepasos(browser, ancho);
  await progresoVacio(browser, ancho);
  await progresoError(browser, ancho);
}
await practicaConVencido(browser);

await browser.close();

resumen.violacionesAxe = Object.values(resumen.axe).reduce((n, v) => n + v.length, 0);
resumen.bytesCapturas = resumen.capturas.reduce((n, c) => n + c.bytes, 0);
await writeFile(join(DIR_REP, 'resumen.json'), JSON.stringify(resumen, null, 2));
await writeFile(join(DIR_REP, 'peticiones.json'), JSON.stringify(peticiones, null, 2));

console.log('\nPeticiones:');
for (const p of peticiones) {
  console.log(`  ${p.caso} -> ${p.metodo} ${p.ruta} [${p.estado}]${p.sesion_id ? ` sesion ${p.sesion_id}` : ''}`);
}
console.log('\naxe (violaciones por estado):');
for (const [estado, violaciones] of Object.entries(resumen.axe)) {
  console.log(`  ${estado}: ${violaciones.length}${violaciones.length ? ' ' + JSON.stringify(violaciones) : ''}`);
}
console.log(`\nTextos: ${JSON.stringify(resumen['textos-375'])}`);
console.log(`Sesión de Práctica creada: ${resumen.sesionPractica?.id} ${JSON.stringify(resumen.sesionPractica?.ejercicios)}`);
console.log(`Capturas: ${resumen.capturas.length}, ${resumen.bytesCapturas} bytes`);
const fallas = Object.entries(resumen.comprobaciones).filter(([, ok]) => !ok).map(([n]) => n);
console.log(`Comprobaciones: ${Object.keys(resumen.comprobaciones).length - fallas.length} ok, ${fallas.length} con falla`);
if (fallas.length) console.log(fallas.join('\n'));
