/**
 * Verificación del frontend de RF-IA-01 (patrones de error): capturas a 375
 * y 1280 px, axe-core (WCAG 2.1 AA) a 375 px y registro de las peticiones
 * que llevan `codigo_error`.
 *
 *   node rf-ia-01.mjs --url http://localhost --usuario <uuid con patrones>
 *
 * `--usuario` es un usuario que ya tiene patrones de error. Para el resto se
 * generan usuarios nuevos. El guion solo agrega respuestas: no borra nada.
 * "patrones/ caído" y "errores/ caído" se simulan cortando esa petición en
 * el navegador, sin detener ningún servicio.
 *
 * Salidas:
 *   docs/wiki/img/rf-ia-01/*.png
 *   tools/auditoria-ux/reportes/rf-ia-01/{resumen,peticiones}.json
 */

import { randomUUID } from 'node:crypto';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import sharp from 'sharp';

const AQUI = dirname(fileURLToPath(import.meta.url));
const RAIZ = resolve(AQUI, '..', '..');
const DIR_IMG = join(RAIZ, 'docs', 'wiki', 'img', 'rf-ia-01');
const DIR_REP = join(AQUI, 'reportes', 'rf-ia-01');

const { values: args } = parseArgs({
  options: { url: { type: 'string' }, usuario: { type: 'string' } },
});
if (!args.url || !args.usuario) {
  console.error('Uso: node rf-ia-01.mjs --url <base> --usuario <uuid con patrones>');
  process.exit(1);
}

const BASE = args.url.replace(/\/$/, '');
const CON_PATRONES = args.usuario;
const VIEWPORTS = { 375: { width: 375, height: 812 }, 1280: { width: 1280, height: 800 } };
const ETIQUETAS_WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const CLAVE_USUARIO = 'hanzi-mentor:usuario-id';

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
const resumen = { base: BASE, fecha: new Date().toISOString(), axe: {}, comprobaciones: {}, capturas: [] };
const peticiones = [];

async function contextoDe(browser, ancho, usuarioId) {
  const contexto = await browser.newContext({
    viewport: VIEWPORTS[ancho],
    deviceScaleFactor: 1,
    serviceWorkers: 'block',
    reducedMotion: 'reduce',
    locale: 'es-CO',
  });
  await contexto.addInitScript(
    ([clave, valor]) => localStorage.setItem(clave, valor),
    [CLAVE_USUARIO, usuarioId],
  );
  return contexto;
}

/** Anota cada POST que lleva (o debería llevar) el tipo de error. */
function registrarPeticiones(pagina, estado) {
  pagina.on('request', (peticion) => {
    const ruta = new URL(peticion.url()).pathname;
    if (peticion.method() !== 'POST' || !/\/(responder|errores)\/$/.test(ruta)) return;
    peticiones.push({
      caso: estado.caso,
      ruta: ruta.replace(/[0-9a-f-]{36}/, '<usuario>').replace(/\/\d+\//, '/<id>/'),
      cuerpo: JSON.parse(peticion.postData() || 'null'),
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
    .png({ palette: true, quality: 90, effort: 10, compressionLevel: 9 })
    .toBuffer();
  await writeFile(join(DIR_IMG, `${nombre}.png`), optimizado);
  resumen.capturas.push(`${nombre}.png`);
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
  resumen.comprobaciones[`${nombre}: sin desborde horizontal`] = !desborde;
}

function comprobar(nombre, valor) {
  resumen.comprobaciones[nombre] = valor;
  console.log(`${valor ? 'ok   ' : 'FALLA'} ${nombre}`);
}

// ------------------------------------------------------------------ Progreso

async function progreso(browser, ancho, usuarioId, nombre, { cortar = false } = {}) {
  const contexto = await contextoDe(browser, ancho, usuarioId);
  const pagina = await contexto.newPage();
  if (cortar) {
    await pagina.route('**/api/v2/progreso/*/patrones/', (ruta) => ruta.abort('connectionrefused'));
  }
  await abrir(pagina, '/progreso');
  const seccion = pagina.locator('section[aria-labelledby="progreso-patrones"]');
  await seccion.waitFor();

  if (nombre === 'patrones') {
    comprobar(`progreso ${ancho}: lista de patrones`, (await seccion.locator('.patron').count()) > 0);
  } else if (nombre === 'vacio') {
    comprobar(`progreso ${ancho}: estado vacío`, (await seccion.locator('.hm-status--empty').count()) === 1);
  } else {
    comprobar(`progreso ${ancho}: error con Reintentar`,
      (await seccion.locator('[role="alert"]').count()) === 1
      && (await seccion.locator('.patrones-reintentar').count()) === 1);
    comprobar(`progreso ${ancho}: el resto de la página sigue`,
      (await pagina.locator('.progreso-metricas').count()) === 1
      && (await pagina.locator('main > [role="alert"]').count()) === 0);
  }

  if (ancho === 375) await axe(pagina, `progreso-${nombre}-375`);
  await capturar(pagina, `progreso-${nombre}-${ancho}`, 'section[aria-labelledby="progreso-patrones"]');

  if (cortar && ancho === 375) {
    // "Reintentar" con el servicio de vuelta: aparece la lista.
    await pagina.unroute('**/api/v2/progreso/*/patrones/');
    await seccion.locator('.patrones-reintentar').click();
    await seccion.locator('.patron').first().waitFor();
    comprobar('progreso: Reintentar recupera la lista', true);

    // "Actualizar" vuelve a pedir patrones/.
    const pedido = pagina.waitForRequest((r) => r.url().endsWith('/patrones/'));
    await pagina.locator('.progreso-acciones .hm-btn').click();
    await pedido;
    comprobar('progreso: Actualizar vuelve a pedir patrones/', true);
  }
  await contexto.close();
}

// ------------------------------------------------------------------ Práctica

async function pinyinDe(pagina, hanzi) {
  const respuesta = await pagina.request.get(`${BASE}/api/v2/caracteres/${encodeURIComponent(hanzi)}/`);
  return (await respuesta.json()).pinyin;
}

/**
 * Hace una sesión completa. `acciones[i]` dice qué hacer en el ejercicio i:
 * 'acierto', 'fallo' (pinyin equivocado o "Fallé"), 'no-se' o
 * 'sin-explicacion' (pinyin equivocado y la evaluación responde sin
 * explicación). Lo que no esté en la lista se acierta.
 */
async function sesion(browser, ancho, usuarioId, nombre, acciones, { cortarPatrones = false } = {}) {
  const contexto = await contextoDe(browser, ancho, usuarioId);
  const pagina = await contexto.newPage();
  const estado = { caso: '' };
  registrarPeticiones(pagina, estado);
  if (cortarPatrones) {
    await pagina.route('**/api/v2/progreso/*/patrones/', (ruta) => ruta.abort('connectionrefused'));
  }

  await abrir(pagina, '/practica');
  const creada = pagina.waitForResponse(
    (r) => r.url().endsWith('/api/v2/sesiones/') && r.request().method() === 'POST',
  );
  await pagina.locator('.practica-nivel').first().click();
  const { ejercicios } = await (await creada).json();

  for (const [i, ejercicio] of ejercicios.entries()) {
    const accion = acciones[i] || 'acierto';
    const esTrazo = ejercicio.tipo === 'trazo';
    estado.caso = `${nombre}: ${esTrazo ? 'trazo' : 'pinyin'} ${accion}`;
    const respondido = pagina.waitForResponse((r) => r.url().includes('/responder/'));

    if (esTrazo) {
      await pagina.locator('.practica-acciones button').nth(accion === 'acierto' ? 1 : 0).click();
    } else if (accion === 'no-se') {
      await pagina.locator('.respuesta-pinyin__acciones button[type="button"]').click();
    } else {
      if (accion === 'sin-explicacion') {
        await pagina.route('**/api/v2/evaluacion/', async (ruta) => {
          const original = await ruta.fetch();
          const cuerpo = await original.json();
          delete cuerpo.explicacion;
          await ruta.fulfill({ response: original, json: cuerpo });
        });
      }
      const correcto = await pinyinDe(pagina, ejercicio.caracter);
      const equivocado = correcto.startsWith('m') ? 'bo' : 'ma';
      await pagina.locator('#pinyin-campo').fill(accion === 'acierto' ? correcto : equivocado);
      await pagina.locator('.respuesta-pinyin button[type="submit"]').click();
    }
    await respondido;
    if (accion === 'sin-explicacion') await pagina.unroute('**/api/v2/evaluacion/');

    const ultimo = i === ejercicios.length - 1;
    if (!ultimo) {
      await pagina.locator('.practica-feedback').waitFor();
      if (ancho === 375 && accion === 'fallo' && !esTrazo && !resumen.axe['practica-feedback-375']) {
        await axe(pagina, 'practica-feedback-375');
      }
      await pagina.locator('.practica-siguiente').click();
    }
  }

  await pagina.locator('.practica-resumen').waitFor();
  await pagina.waitForLoadState('networkidle');
  await esperar(400);
  const avisos = await pagina.locator('.practica-patron').count();
  if (ancho === 375) await axe(pagina, `practica-fin-${nombre}-375`);
  await capturar(pagina, `practica-fin-${nombre}-${ancho}`);
  const cierre = (await pagina.locator('.practica-resumen .hm-btn').count()) === 1;
  await contexto.close();
  return { avisos, cierre, ejercicios };
}

// -------------------------------------------------------------------- Trazos

/** Dibuja el primer trazo al revés (de su final a su inicio) con el mouse. */
async function trazoAlReves(pagina, hanzi) {
  const detalle = await (await pagina.request.get(
    `${BASE}/api/v2/caracteres/${encodeURIComponent(hanzi)}/`,
  )).json();
  const mediana = detalle.trazos[0].mediana;
  const caja = await pagina.locator('.lienzo-canvas').boundingBox();
  // Make Me a Hanzi: lienzo de 1024 con el eje Y invertido y origen en (0, 900).
  const puntos = [...mediana].reverse().map(([x, y]) => ({
    x: caja.x + (x / 1024) * caja.width,
    y: caja.y + ((900 - y) / 1024) * caja.height,
  }));
  await pagina.mouse.move(puntos[0].x, puntos[0].y);
  await pagina.mouse.down();
  for (const punto of puntos.slice(1)) await pagina.mouse.move(punto.x, punto.y, { steps: 8 });
  await pagina.mouse.up();
}

async function trazos(browser, ancho, usuarioId, { cortarErrores = false } = {}) {
  const contexto = await contextoDe(browser, ancho, usuarioId);
  const pagina = await contexto.newPage();
  const estado = { caso: `trazos ${ancho}${cortarErrores ? ' (errores/ caído)' : ''}: trazo al revés` };
  registrarPeticiones(pagina, estado);
  if (cortarErrores) {
    await pagina.route('**/api/v2/progreso/*/errores/', (ruta) => ruta.abort('connectionrefused'));
  }

  await abrir(pagina, `/trazos?caracter=${encodeURIComponent('一')}`);
  await pagina.locator('.lienzo-canvas').scrollIntoViewIfNeeded();
  const evaluado = pagina.waitForResponse((r) => r.url().includes('/api/v2/evaluacion/'));
  const anotado = pagina.waitForRequest((r) => r.url().endsWith('/errores/'));
  await trazoAlReves(pagina, '一');
  const veredicto = await (await evaluado).json();
  await anotado;
  await pagina.locator('.por-que').waitFor();
  await esperar(500);

  const sufijo = cortarErrores ? ' con errores/ caído' : '';
  comprobar(`trazos ${ancho}${sufijo}: veredicto y bloque Por qué`,
    veredicto.aprobado === false
    && (await pagina.locator('.resultado').count()) === 1
    && (await pagina.locator('.por-que').count()) === 1);
  comprobar(`trazos ${ancho}${sufijo}: sin avisos de error`,
    (await pagina.locator('[role="alert"]').count()) === 0
    && (await pagina.locator('.hm-status--empty').count()) === 0);

  if (!cortarErrores) {
    if (ancho === 375) await axe(pagina, 'trazos-fallado-375');
    await capturar(pagina, `trazos-fallado-${ancho}`, '.lienzo-wrap');
  }
  await contexto.close();
  return veredicto.explicacion?.codigo;
}

// ---------------------------------------------------------------------- main

await mkdir(DIR_IMG, { recursive: true });
await mkdir(DIR_REP, { recursive: true });
const browser = await chromium.launch();

const nuevo = randomUUID();        // sin respuestas: estado vacío y fin de sesión sin aviso
const deTrazos = randomUUID();     // solo practica en Trazos
resumen.usuarios = { conPatrones: CON_PATRONES, nuevo, deTrazos };

for (const ancho of [375, 1280]) {
  await progreso(browser, ancho, CON_PATRONES, 'patrones');
  await progreso(browser, ancho, nuevo, 'vacio');
  await progreso(browser, ancho, CON_PATRONES, 'error', { cortar: true });
}

// Con aviso: el usuario ya tiene patrones. En 375 recorre todos los casos.
const conAviso = await sesion(browser, 375, CON_PATRONES, 'con-aviso', ['fallo', 'fallo', 'no-se', 'acierto', 'fallo']);
comprobar('práctica 375: aviso de patrón al terminar', conAviso.avisos === 1 && conAviso.cierre);
const conAviso1280 = await sesion(browser, 1280, CON_PATRONES, 'con-aviso', []);
comprobar('práctica 1280: aviso de patrón al terminar', conAviso1280.avisos === 1 && conAviso1280.cierre);

// Sin aviso: usuario nuevo, un solo fallo (y sin explicación).
const sinAviso = await sesion(browser, 375, nuevo, 'sin-aviso', ['sin-explicacion']);
comprobar('práctica 375: sin patrones no hay aviso', sinAviso.avisos === 0 && sinAviso.cierre);
const sinAviso1280 = await sesion(browser, 1280, nuevo, 'sin-aviso', []);
comprobar('práctica 1280: sin patrones no hay aviso', sinAviso1280.avisos === 0 && sinAviso1280.cierre);

// patrones/ caído al terminar: el cierre queda igual, sin aviso ni error.
const caido = await sesion(browser, 375, CON_PATRONES, 'patrones-caido', [], { cortarPatrones: true });
comprobar('práctica: con patrones/ caído la sesión cierra sin aviso', caido.avisos === 0 && caido.cierre);

for (const ancho of [375, 1280]) {
  const codigo = await trazos(browser, ancho, deTrazos);
  comprobar(`trazos ${ancho}: la explicación es TRAZO_INVERTIDO`, codigo === 'TRAZO_INVERTIDO');
}
await trazos(browser, 375, deTrazos, { cortarErrores: true });

await browser.close();

resumen.violacionesAxe = Object.values(resumen.axe).reduce((n, v) => n + v.length, 0);
await writeFile(join(DIR_REP, 'resumen.json'), JSON.stringify(resumen, null, 2));
await writeFile(join(DIR_REP, 'peticiones.json'), JSON.stringify(peticiones, null, 2));

console.log('\nPeticiones con tipo de error:');
for (const p of peticiones) console.log(`  ${p.caso} -> ${p.ruta} ${JSON.stringify(p.cuerpo)}`);
console.log('\naxe (violaciones por estado):');
for (const [estado, violaciones] of Object.entries(resumen.axe)) {
  console.log(`  ${estado}: ${violaciones.length}${violaciones.length ? ' ' + JSON.stringify(violaciones) : ''}`);
}
const fallas = Object.entries(resumen.comprobaciones).filter(([, ok]) => !ok).map(([n]) => n);
console.log(`\nComprobaciones: ${Object.keys(resumen.comprobaciones).length - fallas.length} ok, ${fallas.length} con falla`);
if (fallas.length) console.log(fallas.join('\n'));
