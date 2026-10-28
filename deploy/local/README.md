# Despliegue desde tu ordenador (Fase 8d, parche)

La web se sirve desde tu PC (la 3080 Ti) y un túnel la publica en internet. Es un parche: Oracle y Hugging Face PRO siguen siendo las opciones de futuro (`docs/es/ROADMAP.md`, Fase 8).

```
navegador ──HTTPS──► túnel (servidor del proveedor) ──► tu PC: 127.0.0.1:8000
                                                        make api-public
                                                        (API + web compilada + Qdrant en Docker)
```

- **Sin abrir puertos del router:** la conexión del túnel sale desde tu PC.
- **La API solo escucha en `127.0.0.1`:** desde tu red local no se llega a ella; solo por el túnel.
- **El túnel publica solo el puerto 8000:** el resto del ordenador no queda accesible.
- **No hace falta el bundle:** el índice ya está en tu Qdrant local. El bundle (`deploy/bundle/`) es solo para Oracle.
- **La web solo funciona con tu PC encendido**, con Docker abierto y `make api-public` corriendo.

## Opciones de túnel

| | Tailscale Funnel | Cloudflare, túnel rápido | Cloudflare, túnel con nombre | ngrok (gratis) |
|---|---|---|---|---|
| Cuenta | Sí (gratis; inicio de sesión con Google, Microsoft o GitHub) | **No** | Sí | Sí |
| Coste | Gratis | Gratis | Gratis, pero **hace falta un dominio propio** en Cloudflare (de pago) | Gratis |
| URL | Fija: `https://<pc>.<tailnet>.ts.net` | Aleatoria en cada arranque (`*.trycloudflare.com`) | Fija, en tu dominio | Fija: `https://<nombre>.ngrok-free.app` |
| Streaming del chat (SSE) | Sí: Funnel es un proxy TCP, el TLS se termina en tu PC | **No**: "Quick Tunnels do not support Server-Sent Events" (documentación oficial). El chat de la web usa SSE | Sí | Sí |
| Para el recruiter | Entra directo | Entra directo | Entra directo | **Página de aviso de ngrok** antes de la web |
| Límites | Ancho de banda limitado, sin cifra publicada | 200 peticiones a la vez; sin garantía de disponibilidad | Los de la cuenta gratuita | 1 GB/mes de salida y 20 000 peticiones/mes |

**Conclusión:** la metodología no es la misma en los dos. Cloudflare sin cuenta (túnel rápido) no sirve para el chat, porque no admite SSE. Con cuenta, la URL fija exige comprar un dominio. **Tailscale Funnel** es la única opción gratuita que cumple todo. Un túnel rápido de Cloudflare sirve, como mucho, para comprobar en 5 minutos que el chat no funciona por él (abajo).

Fuentes (consultadas el 2026-10-28):
- Tailscale Funnel: https://tailscale.com/kb/1223/funnel y https://tailscale.com/kb/1311/tailscale-funnel
- Túneles rápidos de Cloudflare: https://developers.cloudflare.com/cloudflare-one/networks/connectors/cloudflare-tunnel/do-more-with-tunnels/trycloudflare/
- Límites de ngrok: https://ngrok.com/docs/pricing-limits/free-plan-limits

## Antes de abrir nada (una vez)

1. **Qdrant solo para tu PC.** Hoy Docker publica Qdrant (puertos 6333 y 6334) en todas las interfaces, sin contraseña: cualquiera en tu misma red (la wifi de casa, o la de donde estés) podría leer el índice, incluido el CV sin enmascarar, o borrarlo. El túnel no lo expone a internet, pero conviene cerrarlo igual. Cambio propuesto en `docker-compose.yml`: `"127.0.0.1:6333:6333"` y `"127.0.0.1:6334:6334"`, y `docker compose up -d` (los datos están en un volumen y no se pierden). **Pendiente de tu permiso.**
2. **El firewall de Windows activo** en los tres perfiles (comprobado: lo está).
3. **Sesión de Windows sin permisos de administrador** para `make api-public`, si es posible.
4. **Windows, Docker Desktop y Tailscale actualizados.**

## Pasos con Tailscale Funnel

Lo que requiere tu cuenta lo haces tú.

1. **Instala Tailscale para Windows** (https://tailscale.com/download, o `winget install tailscale.tailscale`) e inicia sesión. Se crea una tailnet gratuita con tu cuenta.
2. **En la consola de administración** (https://login.tailscale.com/admin), activa MagicDNS y los certificados HTTPS (DNS → HTTPS Certificates).
3. **Arranca la web** desde la raíz del repo, con Docker Desktop abierto:
   ```
   make web-build        # solo si ha cambiado web/
   make api-public
   ```
   Espera a que `http://127.0.0.1:8000/health` diga `"loaded": true`.
4. **Abre el túnel** en otra terminal, **sin `--bg`**:
   ```
   tailscale funnel --https=443 localhost:8000
   ```
   La primera vez abre una página para aprobar Funnel, que crea el permiso `funnel` en la política de la tailnet. Te da la URL pública. Sin `--bg`, el túnel se cierra al pulsar Ctrl+C o al cerrar la terminal. Con `--bg` seguiría abierto incluso después de reiniciar el PC.
5. **Restringe el origen a tu URL** (opcional; la web y la API comparten origen, así que funciona igual):
   ```
   make api-public PUBLIC_ORIGIN=https://<pc>.<tailnet>.ts.net
   ```
6. **Prueba desde fuera de tu red** (el móvil con datos): la web, una pregunta del CV, una de vLLM y una con el agente. Las DNS públicas pueden tardar hasta 10 minutos la primera vez.

**Para apagarlo:**
- Ctrl+C en la terminal del túnel (o `tailscale funnel reset` si lo abriste con `--bg`). `tailscale funnel status` dice si sigue abierto.
- Ctrl+C en `make api-public` para la API.

## Prueba opcional: túnel rápido de Cloudflare (sin cuenta)

Solo para comprobar lo de SSE. Con `make api-public` corriendo:
```
winget install Cloudflare.cloudflared
cloudflared tunnel --url http://localhost:8000
```
Te da una URL `*.trycloudflare.com`. Abre la web y haz una pregunta: según la documentación, el chat no debería llegar en streaming. Ctrl+C lo cierra, y la URL deja de existir.

## Lo que hace `make api-public`

Es `make api` con tres cambios:
- **`RAG_API_MAX_QUEUE=4`:** como mucho 4 preguntas o búsquedas a la vez, sumando las que se responden y las que esperan. A partir de ahí, la web contesta "The server is busy answering other questions: try again in a minute." (y `/search` devuelve un error 503). La API responde de una en una (una GPU), así que sin límite un solo visitante podría encolar peticiones para todos.
- **`RAG_API_DOCS=0`:** oculta la documentación automática de FastAPI (`/docs`, `/redoc` y `/openapi.json`). Un servidor público no necesita listar sus endpoints.
- **`RAG_ALLOWED_ORIGINS`:** con `PUBLIC_ORIGIN`, solo tu web puede llamar a la API desde un navegador.

Modelos de la web: Qwen3-1.7B por defecto, Qwen3-0.6B y Granite 4.0 Micro, todos con y sin agente (`Makefile`, `API_MODELS`).

## Seguridad: qué queda expuesto y qué no

**Expuesto a internet:** solo la API en el puerto 8000:
- Los endpoints `/chat`, `/chat/reset`, `/search`, `/sources/{id}`, `/config`, `/metrics` y `/health`.
- La web compilada (`web/dist`).

**Protegido:**
- **Ficheros:** la API no sirve nada de tu disco salvo `web/dist`. `/sources/{id}` solo acepta identificadores de fragmentos del índice. El `.env`, la clave de Groq y `data/` no son accesibles.
- **Sin escritura:** no hay endpoints que escriban ni que ejecuten nada. El agente solo puede buscar en el índice, así que una pregunta maliciosa (inyección en el prompt) no puede hacer nada fuera del RAG.
- **Datos del CV:** el teléfono y el correo antiguo se enmascaran al responder, en el contexto del LLM, en la respuesta y en las fuentes (`rag.toml`, `private_data`), con cualquier modelo. Solo sale el correo público.
- **Entradas acotadas:** preguntas de hasta 1 000 caracteres, respuestas de hasta 1 024 tokens y como mucho 4 peticiones a la vez.
- **Visitantes:** no se guardan datos. Las conversaciones viven en memoria y caducan a los 30 minutos.

**Riesgos que quedan:**
- **Abuso de uso:** alguien puede mandar preguntas sin parar. La cola lo limita a 4 a la vez, pero no hay límite por persona: los demás visitantes verían el aviso de "ocupado" y tu GPU estaría trabajando. Si pasa, se cierra el túnel. Un límite por IP se puede añadir más adelante.
- **Tu IP de casa:** con Tailscale Funnel no se ve; los visitantes ven las IP de los relays de Tailscale.
- **Errores de software:** como en cualquier servidor, un fallo de FastAPI, uvicorn o Tailscale podría ser una vía de entrada. Por eso: todo actualizado, el túnel abierto solo cuando haga falta y la API sin permisos de administrador.

**Mientras sirves la web:** desactiva la suspensión de Windows y no lances benchmarks, porque comparten la GPU. Cambiar de modelo afecta a todos los visitantes (solo hay uno cargado a la vez), y el primer mensaje tras el cambio tarda unos 5–15 s más.
