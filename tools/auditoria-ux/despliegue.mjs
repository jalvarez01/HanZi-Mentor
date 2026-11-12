/**
 * Evidencia del despliegue en AWS: recorrido completo de la app servida por
 * HTTP en la IP pública, con capturas a 375 y 1280 px y axe-core (WCAG 2.1
 * AA) a 375 px en cada pantalla.
 *
 *   node despliegue.mjs [--url http://52.44.136.85] [--commit e3425c3]
 *
 * Un solo contexto de navegador nuevo, en español, con los service workers
 * bloqueados (sin caché de la PWA). El usuario lo crea la propia app al
 * abrir Inicio (UUID en localStorage); su id queda en el resumen para
 * limpiarlo después. Todo lo que se escribe en producción pasa por la app:
 * dos sesiones de Práctica, un reporte asíncrono y Premium con la tarjeta de
 * prueba 4242 4242 4242 4242 de la pasarela simulada.
 *
 * En las sesiones, los ejercicios de pinyin se responden alternando "No lo
 * sé" y un pinyin errado, y los de trazo con "Fallé", para que aparezcan
 * patrones de error y repasos. No se fuerza nada: si un patrón no aparece,
 * queda anotado.
 *
 * Salidas:
 *   docs/wiki/img/despliegue/*.png
 *   tools/auditoria-ux/reportes/despliegue/resumen.json
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
const DIR_IMG = join(RAIZ, 'docs', 'wiki', 'img', 'despliegue');
const DIR_REP = join(AQUI, 'reportes', 'despliegue');

const { values: args } = parseArgs({
  options: {
    url: { type: 'string', default: 'http://52.44.136.85' },
    commit: { type: 'string', default: 'e3425c3' },
  },
});

const BASE = args.url.replace(/\/$/, '');
const VIEWPORTS = { 375: { width: 375, height: 812 }, 1280: { width: 1280, height: 800 } };
const ETIQUETAS_WCAG = ['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa'];
const CLAVE_USUARIO = 'hanzi-mentor:usuario-id';
// Carácter de HSK 1 preferido para Trazos; si no está en el catálogo se usa el primero de nivel 1.
const CARACTER_PREFERIDO = '上';
// Pinyin bien formado pero errado para casi cualquier carácter de HSK 1.
const PINYIN_ERRADO = 'zhuang';
const TARJETA = { titular: 'Prueba Despliegue', numero: '4242 4242 4242 4242', vencimiento: '12/30', cvc: '123' };

const esperar = (ms) => new Promise((r) => setTimeout(r, ms));
const resumen = {
  url: BASE,
  fecha: new Date().toISOString(),
  commitDesplegado: args.commit,
  usuario: null,
  pasos: {},
  sesiones: [],
  axe: {},
  notas: [],
  capturas: [],
};
const erroresConsola = [];

function paso(clave, ok, detalle) {
  resumen.pasos[clave] = { ok: Boolean(ok), ...(detalle ? { detalle } : {}) };
  console.log(`${ok ? 'ok   ' : 'FALLA'} ${clave}${detalle ? ` (${typeof detalle === 'string' ? detalle : JSON.stringify(detalle)})` : ''}`);
}

async function abrir(pagina, ruta) {
  await pagina.goto(`${BASE}${ruta}`, { waitUntil: 'networkidle' });
  await pagina.evaluate(() => document.fonts.ready);
  await esperar(400);
}

async function centrar(pagina, selector) {
  if (!selector) return;
  await pagina.locator(selector).first().evaluate((el) => el.scrollIntoView({ block: 'center' }));
  await esperar(250);
}

async function guardar(pagina, nombre, selector) {
  await centrar(pagina, selector);
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
}

/** axe y captura a 375 px, y captura a 1280 px de la misma página. */
async function pantalla(pagina, nombre, selector) {
  await pagina.setViewportSize(VIEWPORTS[375]);
  await esperar(400);
  await centrar(pagina, selector);
  await axe(pagina, nombre);
  await guardar(pagina, `${nombre}-375`, selector);
  await pagina.setViewportSize(VIEWPORTS[1280]);
  await esperar(500);
  await guardar(pagina, `${nombre}-1280`, selector);
  await pagina.setViewportSize(VIEWPORTS[375]);
  await esperar(300);
}

/**
 * Juega una sesión de HSK 1 completa. Pinyin: "No lo sé" y pinyin errado
 * alternados. Trazo: "Fallé". Devuelve el id y los ejercicios.
 */
async function sesionCompleta(pagina, { capturarEnCurso }) {
  await abrir(pagina, '/practica');
  const creada = pagina.waitForResponse(
    (r) => r.url().endsWith('/api/v2/sesiones/') && r.request().method() === 'POST',
  );
  await pagina.locator('button.practica-nivel').first().click();
  const sesion = await (await creada).json();
  await pagina.locator('.practica-tarjeta').waitFor();
  await esperar(400);

  if (capturarEnCurso) {
    paso('b-practica-en-curso', (await pagina.locator('.practica-tarjeta').count()) === 1,
      `sesión ${sesion.id}, ${sesion.ejercicios.length} ejercicios`);
    await pantalla(pagina, 'b-practica-en-curso');
  }

  const respuestas = [];
  let pinyin = 0;
  for (let i = 0; i < sesion.ejercicios.length; i += 1) {
    const ej = sesion.ejercicios[i];
    if (ej.tipo === 'trazo') {
      await pagina.locator('.practica-acciones .hm-btn').first().click(); // Fallé
      respuestas.push(`${ej.caracter} trazo: Fallé`);
    } else if (pinyin % 2 === 0) {
      await pagina.locator('.respuesta-pinyin__acciones .hm-btn').first().click(); // No lo sé
      respuestas.push(`${ej.caracter} pinyin: No lo sé`);
      pinyin += 1;
    } else {
      await pagina.locator('#pinyin-campo').fill(PINYIN_ERRADO);
      await pagina.locator('.respuesta-pinyin__acciones button[type="submit"]').click();
      respuestas.push(`${ej.caracter} pinyin: ${PINYIN_ERRADO}`);
      pinyin += 1;
    }
    await pagina.locator('.practica-feedback, .practica-resumen').first().waitFor({ timeout: 15000 });
    if (await pagina.locator('.practica-resumen').count()) break;
    await pagina.locator('.practica-siguiente').click();
    await pagina.locator('.practica-tarjeta').waitFor();
  }
  await pagina.locator('.practica-resumen').waitFor({ timeout: 15000 });
  const info = { id: sesion.id, ejercicios: sesion.ejercicios.map((e) => `${e.caracter} ${e.tipo}${e.patron ? ` patron:${e.patron}` : ''}${e.es_refuerzo ? ' refuerzo' : ''}`), respuestas };
  resumen.sesiones.push(info);
  return info;
}

// ---------------------------------------------------------------------- main

await mkdir(DIR_IMG, { recursive: true });
await mkdir(DIR_REP, { recursive: true });
const browser = await chromium.launch();
const contexto = await browser.newContext({
  viewport: VIEWPORTS[375],
  deviceScaleFactor: 1,
  serviceWorkers: 'block',
  reducedMotion: 'reduce',
  locale: 'es-CO',
  timezoneId: 'America/Bogota',
});
const pagina = await contexto.newPage();
pagina.on('console', (m) => { if (m.type() === 'error') erroresConsola.push({ ruta: new URL(pagina.url()).pathname, texto: m.text() }); });
pagina.on('pageerror', (e) => erroresConsola.push({ ruta: new URL(pagina.url()).pathname, texto: `pageerror: ${e.message}` }));

try {
  // a. Inicio, sin errores en la consola.
  await abrir(pagina, '/');
  await pagina.locator('main').first().waitFor();
  resumen.usuario = await pagina.evaluate((k) => localStorage.getItem(k), CLAVE_USUARIO);
  const contextoSeguro = await pagina.evaluate(() => window.isSecureContext);
  const erroresInicio = erroresConsola.filter((e) => e.ruta === '/');
  paso('a-inicio', erroresInicio.length === 0 && /^[0-9a-f-]{36}$/.test(resumen.usuario ?? ''), {
    usuario: resumen.usuario, isSecureContext: contextoSeguro, erroresConsola: erroresInicio,
  });
  await pantalla(pagina, 'a-inicio');

  // b y c. Dos sesiones completas; captura en curso de la primera y fin de la segunda.
  await sesionCompleta(pagina, { capturarEnCurso: true });
  await sesionCompleta(pagina, { capturarEnCurso: false });
  await pagina.locator('.practica-desempeno').waitFor({ timeout: 10000 }).catch(() => {});
  await esperar(1500); // aviso del patrón principal, que llega aparte
  const conDesempeno = (await pagina.locator('.practica-desempeno').count()) === 1;
  const conPatron = (await pagina.locator('.practica-patron').count()) === 1;
  const adaptados = resumen.sesiones[1].ejercicios.filter((e) => e.includes('patron:')).length;
  const refuerzos = resumen.sesiones[1].ejercicios.filter((e) => e.includes('refuerzo')).length;
  paso('c-dos-sesiones', conDesempeno, {
    sesiones: resumen.sesiones.map((s) => s.id), panelDesempeno: conDesempeno, avisoPatron: conPatron,
    segundaSesion: { adaptadosAPatron: adaptados, refuerzos },
  });
  if (!conPatron) resumen.notas.push('El aviso de patrón principal no apareció al cerrar la segunda sesión.');
  if (!adaptados) resumen.notas.push('La segunda sesión no trajo ejercicios adaptados a un patrón (RF-IA-03).');
  if (!refuerzos) resumen.notas.push('La segunda sesión no trajo ejercicios de refuerzo.');
  await pantalla(pagina, 'c-fin-segunda-sesion', '.practica-desempeno');

  // d. Trazos de un carácter de HSK 1 con oraciones de Tatoeba.
  const nivel1 = (await (await pagina.request.get(`${BASE}/api/v2/caracteres/?nivel=1&limite=30`)).json())
    .caracteres.map((c) => c.hanzi);
  const CARACTER_TRAZOS = nivel1.includes(CARACTER_PREFERIDO) ? CARACTER_PREFERIDO : nivel1[0];
  await abrir(pagina, `/trazos?caracter=${encodeURIComponent(CARACTER_TRAZOS)}`);
  await pagina.locator('.trazos-ficha').waitFor({ timeout: 10000 });
  const inicioEjemplos = Date.now();
  const conEjemplos = await pagina.locator('.ejemplos .ejemplo').first().waitFor({ timeout: 10000 })
    .then(() => true).catch(() => false);
  const nEjemplos = await pagina.locator('.ejemplos .ejemplo').count();
  paso('d-trazos-tatoeba', conEjemplos, {
    caracter: CARACTER_TRAZOS, oraciones: nEjemplos, ms: Date.now() - inicioEjemplos,
    estado: conEjemplos ? 'con oraciones' : await pagina.locator('.ejemplos').innerText().catch(() => 'sin sección'),
  });
  await pantalla(pagina, 'd-trazos-tatoeba', '.ejemplos');

  // e. Progreso con patrones de error y próximos repasos.
  await abrir(pagina, '/progreso');
  const patrones = pagina.locator('section[aria-labelledby="progreso-patrones"]');
  const repasos = pagina.locator('section[aria-labelledby="progreso-repasos"]');
  await patrones.locator('.patron, .hm-status--empty, [role="alert"]').first().waitFor({ timeout: 15000 });
  await repasos.locator('.repaso, .hm-status--empty, [role="alert"]').first().waitFor({ timeout: 15000 });
  const codigos = await patrones.locator('.patron').evaluateAll((els) => els.map((e) => e.dataset.codigo));
  const nRepasos = await repasos.locator('.repaso').count();
  const grupos = await repasos.locator('.repasos-grupo').evaluateAll((els) => els.map((e) => e.dataset.grupo));
  paso('e-progreso-patrones-repasos', codigos.length > 0 && nRepasos > 0, { patrones: codigos, repasos: nRepasos, grupos });
  if (!codigos.length) resumen.notas.push('Tus patrones de error quedó vacío tras dos sesiones.');
  if (!nRepasos) resumen.notas.push('Próximos repasos quedó vacío tras dos sesiones.');
  await pantalla(pagina, 'e-progreso-patrones', 'section[aria-labelledby="progreso-patrones"]');
  await pantalla(pagina, 'e-progreso-repasos', 'section[aria-labelledby="progreso-repasos"]');

  // f. Reporte asíncrono terminado (hasta 45 s).
  const reporte = pagina.locator('section.reporte');
  const inicioReporte = Date.now();
  await reporte.locator('.reporte-acciones .hm-btn').last().click();
  const listo = await reporte.locator('.reporte-resumen').waitFor({ timeout: 45000 }).then(() => true).catch(() => false);
  paso('f-reporte-asincrono', listo, {
    ms: Date.now() - inicioReporte,
    estado: listo ? 'listo' : await reporte.locator('.hm-status').innerText().catch(() => 'sin estado'),
  });
  await pantalla(pagina, 'f-progreso-reporte', 'section.reporte');

  // g. Progreso en inglés, cambiando el idioma desde la app.
  await pagina.locator('.selector-idioma__opcion[lang="en"]').click();
  await esperar(800);
  const lang = await pagina.evaluate(() => document.documentElement.lang);
  const tituloPatrones = await patrones.locator('h2').innerText();
  paso('g-progreso-en-ingles', lang === 'en', { htmlLang: lang, tituloPatrones });
  await pantalla(pagina, 'g-progreso-ingles', 'section[aria-labelledby="progreso-patrones"]');
  await pagina.locator('.selector-idioma__opcion[lang="es"]').click();
  await esperar(800);

  // h. Premium con la tarjeta de prueba.
  const plan = pagina.locator('#plan');
  await plan.locator('.plan-acciones .hm-btn--jade').waitFor({ timeout: 15000 });
  await plan.locator('.plan-acciones .hm-btn--jade').click();
  await pagina.locator('#pago-titular').fill(TARJETA.titular);
  await pagina.locator('#pago-numero').fill(TARJETA.numero);
  await pagina.locator('#pago-vencimiento').fill(TARJETA.vencimiento);
  await pagina.locator('#pago-cvc').fill(TARJETA.cvc);
  await pagina.locator('form.pago button[type="submit"]').click();
  const renovable = await plan.getByText(/Podrás renovar desde el/).waitFor({ timeout: 15000 })
    .then(() => true).catch(() => false);
  paso('h-premium', renovable, {
    insignia: await plan.locator('.plan-insignia').innerText().catch(() => null),
    textos: await plan.locator('.plan-texto, .plan-exito').allInnerTexts(),
  });
  await pantalla(pagina, 'h-plan-premium', '#plan');
} catch (e) {
  resumen.error = String(e?.stack ?? e);
  console.error(e);
  await guardar(pagina, 'error').catch(() => {});
} finally {
  await browser.close();
}

resumen.erroresConsola = erroresConsola;
resumen.violacionesAxe = Object.values(resumen.axe).reduce((n, v) => n + v.length, 0);
resumen.bytesCapturas = resumen.capturas.reduce((n, c) => n + c.bytes, 0);
await writeFile(join(DIR_REP, 'resumen.json'), JSON.stringify(resumen, null, 2));

console.log(`\nUsuario de prueba: ${resumen.usuario}`);
console.log('axe (violaciones por pantalla, 375 px):');
for (const [nombre, v] of Object.entries(resumen.axe)) {
  console.log(`  ${nombre}: ${v.length}${v.length ? ' ' + JSON.stringify(v) : ''}`);
}
console.log(`Errores de consola: ${erroresConsola.length}`);
for (const n of resumen.notas) console.log(`Nota: ${n}`);
console.log(`Capturas: ${resumen.capturas.length}, ${resumen.bytesCapturas} bytes`);
