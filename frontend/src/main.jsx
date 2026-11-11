import React from 'react';
import ReactDOM from 'react-dom/client';

// Fuentes alojadas en el proyecto: latín en Source Serif 4 e Inter,
// caracteres chinos en Noto Serif SC (dividida por rangos unicode).
import '@fontsource/source-serif-4/400.css';
import '@fontsource/source-serif-4/400-italic.css';
import '@fontsource/source-serif-4/600.css';
import '@fontsource/source-serif-4/700.css';
import '@fontsource/inter/400.css';
import '@fontsource/inter/500.css';
import '@fontsource/inter/600.css';
import '@fontsource/inter/700.css';
import '@fontsource/noto-serif-sc/400.css';

import './i18n';
import App from './App';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
