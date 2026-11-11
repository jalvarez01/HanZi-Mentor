import { createContext } from 'react';

// Separado del provider para que ProgresoContext.jsx exporte solo componentes (fast refresh).
export const ProgresoContext = createContext(null);
