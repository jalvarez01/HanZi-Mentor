# Gateway

Esta carpeta quedó como placeholder de un posible gateway a medida (código
propio en `config/`, `routes/`, `middleware/`). Para esta entrega se decidió
en cambio usar **nginx** como proxy reverso, porque el caso de uso es
ruteo por prefijo + terminación TLS — exactamente lo que nginx resuelve con
configuración declarativa, sin mantener código adicional.

La implementación real vive en [`infra/nginx/nginx.conf`](../infra/nginx/nginx.conf).

Si más adelante se necesita lógica de gateway que nginx no cubra bien
(por ejemplo, autenticación centralizada con reglas complejas por usuario),
esta carpeta es el lugar natural para un gateway a medida en Node/Express
o Django. Por ahora no hace falta.
