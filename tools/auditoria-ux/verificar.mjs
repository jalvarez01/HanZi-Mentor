/**
 * Verificación complementaria a axe (T24).
 *
 *   node verificar.mjs --version antes   --url http://localhost:5173
 *   node verificar.mjs --version despues --url http://localhost
 *
 * 1. Contraste medido en píxeles: axe no ve imágenes de fondo (el paisaje es
 *    un ::before fixed) y mezcla los paneles semitransparentes sobre el color
 *    del body; en >=561 px ese color es casi negro y los ratios salen
 *    inflados. Aquí, por cada nodo que axe marca en color-contrast, se recorta
 *    el elemento ya pintado, se toman los colores dominantes que no son el
 *    texto y se calcula el ratio del texto contra el peor de ellos.
 * 2. Solapamiento con la barra inferior al final del scroll.
 * 3. Foco tapado por la barra inferior al recorrer con Tab (WCAG 2.2 2.4.11).
 *
 * Salida: tools/auditoria-ux/reportes/<version>/verificacion.json
 */

import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { chromium } from 'playwright';
import { AxeBuilder } from '@axe-core/playwright';
import sharp from 'sharp';

const AQUI = dirname(fileURLToPath(import.meta.url));

const { values: args } = parseArgs({
  options: { version: { type: 'string' }, url: { type: 'string' } },
});

if (!['antes', 'despues'].includes(args.version) || !args.url) {
  console.error('Uso: node verificar.mjs --version antes|despues --url <base>');
  process.exit(1);
}

const BASE = args.url.replace(/\/$/, '');
const DIR_REP = join(AQUI, 'reportes', args.version);

const PAGINAS = ['/', '/trazos', '/practica', '/progreso', '/como-funciona'];
const VIEWPORTS = { 375: { width: 375, height: 812 }, 1280: { width: 1280, height: 800 } };

// Un color de fondo candidato debe ocupar al menos esta fracción del recorte.
const FRACCION_MIN = 0.15;
// Colores a menos de esta distancia (RGB) del texto se tratan como texto.
const DISTANCIA_TEXTO = 40;

const luminancia = ([r, g, b]) => {
  const c = [r, g, b].map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
};

const ratio = (a, b) => {
  const [x, y] = [luminancia(a), luminancia(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

const deHex = (h) => [1, 3, 5].map((i) => parseInt(h.slice(i, i + 2), 16));
const distancia = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

/** Colores dominantes (cuantizados a 5 bits) del recorte, con su fracción. */
async function coloresDominantes(buffer) {
  const { data, info } = await sharp(buffer).removeAlpha().raw().toBuffer({ resolveWithObject: true });
  const cuenta = new Map();
  for (let i = 0; i < data.length; i += 3) {
    const k = `${data[i] >> 3},${data[i + 1] >> 3},${data[i + 2] >> 3}`;
    cuenta.set(k, (cuenta.get(k) || 0) + 1);
  }
  const total = info.width * info.height;
  return [...cuenta.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([k, n]) => ({ rgb: k.split(',').map((v) => (Number(v) << 3) + 4), fraccion: n / total }));
}

async function contrastePixeles(pagina, ancho, ruta) {
  const axe = await new AxeBuilder({ page: pagina }).withRules(['color-contrast']).analyze();
  const filas = [];
  for (const violacion of axe.violations) {
    for (const nodo of violacion.nodes) {
      const datos = nodo.any[0]?.data;
      if (!datos?.fgColor) continue;
      const texto = deHex(datos.fgColor);
      let real = null;
      let fondoReal = null;
      try {
        const el = pagina.locator(nodo.target[0]).first();
        await el.scrollIntoViewIfNeeded({ timeout: 2000 });
        const fondos = (await coloresDominantes(await el.screenshot({ timeout: 2000 })))
          .filter((f) => f.fraccion >= FRACCION_MIN && distancia(f.rgb, texto) > DISTANCIA_TEXTO);
        if (fondos.length) {
          const peor = fondos.reduce((a, b) => (ratio(texto, a.rgb) <= ratio(texto, b.rgb) ? a : b));
          real = Number(ratio(texto, peor.rgb).toFixed(2));
          fondoReal = `#${peor.rgb.map((v) => Math.min(255, v).toString(16).padStart(2, '0')).join('')}`;
        }
      } catch {
        // Elemento oculto o no recortable: queda sin medición propia.
      }
      filas.push({
        ancho: Number(ancho),
        ruta,
        selector: nodo.target.join(' '),
        texto: datos.fgColor,
        fondoAxe: datos.bgColor,
        ratioAxe: datos.contrastRatio,
        fondoReal,
        ratioReal: real,
        requerido: Number(String(datos.expectedContrastRatio).replace(':1', '')),
        fuente: datos.fontSize,
      });
    }
  }
  return filas;
}

async function solapamientoFinal(pagina) {
  return pagina.evaluate(() => {
    window.scrollTo(0, document.documentElement.scrollHeight);
    const barra = document.querySelector('nav')?.getBoundingClientRect();
    if (!barra) return null;
    const tapados = [...document.querySelectorAll('.app-shell a, .app-shell button, .app-shell p, .app-shell h2')]
      .filter((el) => !el.closest('nav, header') && el.offsetParent)
      .filter((el) => {
        const r = el.getBoundingClientRect();
        return r.bottom > barra.top + 2 && r.top < barra.bottom;
      })
      .map((el) => el.textContent.trim().slice(0, 40));
    return { barraTop: Math.round(barra.top), tapados };
  });
}

async function focoTapado(pagina, pasos = 30) {
  await pagina.evaluate(() => window.scrollTo(0, 0));
  const tapados = [];
  for (let i = 0; i < pasos; i++) {
    await pagina.keyboard.press('Tab');
    const texto = await pagina.evaluate(() => {
      const el = document.activeElement;
      const nav = document.querySelector('nav');
      if (!el || el === document.body || !nav || el.closest('nav')) return null;
      const b = el.getBoundingClientRect();
      const barra = nav.getBoundingClientRect();
      const bajoLaBarra = Math.max(0, Math.min(b.bottom, barra.bottom) - Math.max(b.top, barra.top));
      return b.height > 0 && bajoLaBarra >= b.height * 0.5
        ? (el.getAttribute('aria-label') || el.textContent).trim().slice(0, 40)
        : null;
    });
    if (texto && !tapados.includes(texto)) tapados.push(texto);
  }
  return tapados;
}

async function main() {
  await mkdir(DIR_REP, { recursive: true });
  const browser = await chromium.launch({ channel: 'chrome' });
  const salida = { version: args.version, base: BASE, fecha: new Date().toISOString(), contraste: [], barra: [] };

  try {
    for (const ancho of Object.keys(VIEWPORTS)) {
      for (const ruta of PAGINAS) {
        const contexto = await browser.newContext({
          viewport: VIEWPORTS[ancho],
          deviceScaleFactor: 1,
          serviceWorkers: 'block',
          reducedMotion: 'reduce',
        });
        const pagina = await contexto.newPage();
        await pagina.goto(`${BASE}${ruta}`, { waitUntil: 'networkidle' });
        await pagina.evaluate(() => document.fonts.ready);

        salida.contraste.push(...(await contrastePixeles(pagina, ancho, ruta)));
        salida.barra.push({
          ancho: Number(ancho),
          ruta,
          finDePagina: await solapamientoFinal(pagina),
          focoTapado: await focoTapado(pagina),
        });
        console.log(`${ancho} ${ruta}: listo`);
        await contexto.close();
      }
    }
  } finally {
    await browser.close();
  }

  const fallas = salida.contraste.filter((f) => f.ratioReal !== null && f.ratioReal < f.requerido);
  salida.resumen = {
    nodosAxe: salida.contraste.length,
    fallasReales: fallas.length,
    sinMedir: salida.contraste.filter((f) => f.ratioReal === null).length,
  };
  await writeFile(join(DIR_REP, 'verificacion.json'), JSON.stringify(salida, null, 2));
  console.log(`Listo: ${JSON.stringify(salida.resumen)}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
