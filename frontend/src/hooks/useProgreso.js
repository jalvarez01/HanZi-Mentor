import { useContext } from 'react';
import { ProgresoContext } from './progresoContexto';

/**
 * Progreso del usuario actual, compartido por el TopBar y las páginas.
 * Lo provee <ProgresoProvider> (una sola petición por navegación).
 */
export function useProgreso() {
  const valor = useContext(ProgresoContext);
  if (!valor) throw new Error('useProgreso debe usarse dentro de <ProgresoProvider>');
  return valor;
}

/** Mayor cantidad de aciertos seguidos en un mismo carácter. */
export function mejorRacha(progreso) {
  const rachas = Object.values(progreso?.aciertos_consecutivos || {});
  return rachas.length ? Math.max(...rachas) : 0;
}
