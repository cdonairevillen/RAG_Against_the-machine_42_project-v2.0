# Despliegue desde tu ordenador (Fase 8d, parche)

La web se sirve desde tu PC (la 3080 Ti) y un túnel la publica en internet. Es un parche: Oracle y Hugging Face PRO siguen siendo las opciones de futuro (`docs/es/ROADMAP.md`, Fase 8).

```
navegador ──HTTPS──► túnel (servidor del proveedor) ──► tu PC: 127.0.0.1:8000
                                                        make api-public
                                                        (API + web compilada + Qdrant en Docker)
```

- **Sin abrir puertos del router:** el túnel sale desde tu PC.
- **La API solo escucha en `127.0.0.1`:** desde tu red local no se llega a ella; solo por el túnel.
- **No hace falta el bundle:** el índice ya está en tu Qdrant local. El bundle (`deploy/bundle/`) es solo para Oracle.
- **La web solo funciona con tu PC encendido**, con Docker abierto y `make api-public` corriendo.

## El problema del fútbol

En España, durante los partidos de LaLiga, los operadores bloquean direcciones IP compartidas de Cloudflare por orden judicial. Las webs que pasan por esas IP dejan de verse desde España aunque no tengan nada que ver con el fútbol. La autorización cubre hasta la temporada 2026/27. Por eso **Cloudflare Tunnel no es buena idea** para una demo que van a abrir recruiters en España.

## Opciones de túnel

| | Tailscale Funnel | ngrok (gratis) | Cloudflare Tunnel | DuckDNS + router + Caddy |
|---|---|---|---|---|
| Coste | Gratis | Gratis | Gratis (URL fija: hace falta un dominio, de pago) | Gratis |
| URL | Fija: `https://<pc>.<tailnet>.ts.net` | Fija: `https://<nombre>.ngrok-free.app` | Aleatoria en cada arranque (sin dominio) | Fija: `https://<nombre>.duckdns.org` |
| Fútbol (España) | No es Cloudflare. Falta comprobar de quién son las IP de sus relays (abajo) | No es Cloudflare | **Bloqueado en los partidos** | No pasa por nadie: es tu IP |
| Para el recruiter | Entra directo | **Página de aviso de ngrok** antes de la web (una vez cada 7 días) | Entra directo | Entra directo |
| Límites | Ancho de banda limitado, sin cifra publicada; en beta | 1 GB/mes de salida y 20 000 peticiones/mes | — | Los de tu conexión |
| En contra | Instalar Tailscale y activar HTTPS y Funnel en tu tailnet | El aviso y el límite mensual | El bloqueo | Abre el puerto 443 de tu router y expone tu IP de casa; no funciona si tu operador usa CGNAT |

**Recomendación: Tailscale Funnel.** Es gratis, la URL es fija y no pasa por Cloudflare. ngrok sirve de reserva para una prueba rápida.

Fuentes (consultadas el 2026-10-27):
- Tailscale Funnel: https://tailscale.com/docs/features/tailscale-funnel y https://tailscale.com/kb/1311/tailscale-funnel
- Límites de ngrok: https://ngrok.com/docs/pricing-limits/free-plan-limits
- Bloqueos de LaLiga: https://bandaancha.eu/bloqueos-futbol

## Pasos con Tailscale Funnel

Lo que requiere tu cuenta lo haces tú. Yo no instalo nada ni creo cuentas.

1. **Instala Tailscale para Windows** (https://tailscale.com/download) e inicia sesión. Crea una tailnet gratuita.
2. **En la consola de administración**, activa MagicDNS y los certificados HTTPS (DNS → HTTPS Certificates).
3. **Arranca la web** desde la raíz del repo, con Docker Desktop abierto:
   ```
   make web-build        # solo si ha cambiado web/
   make api-public
   ```
   Espera a que `http://127.0.0.1:8000/health` diga `"loaded": true`.
4. **Abre el túnel** en otra terminal:
   ```
   tailscale funnel --bg --https=443 localhost:8000
   ```
   La primera vez abre una página para aprobar Funnel, que crea el permiso `funnel` en la política de la tailnet. Te da la URL pública.
5. **Restringe el origen a tu URL** (opcional; la web y la API comparten origen, así que funciona igual):
   ```
   make api-public PUBLIC_ORIGIN=https://<pc>.<tailnet>.ts.net
   ```
6. **Comprueba de quién son las IP del relay**, para saber si el fútbol le afecta:
   ```
   nslookup <pc>.<tailnet>.ts.net
   ```
   Busca las IP en https://ipinfo.io. Si son de Cloudflare, cuéntamelo y pasamos a otra opción.
7. **Prueba desde fuera de tu red** (el móvil con datos): la web, una pregunta del CV, una de vLLM y una con el agente.

**Para apagarlo:**
- `tailscale funnel --https=443 off` cierra el túnel.
- Ctrl+C en `make api-public` para la API.
- `--bg` hace que el túnel siga activo tras reiniciar el PC. Sin la API, la URL dará un error 502 hasta que la vuelvas a arrancar.

## Lo que hace `make api-public`

Es `make api` con dos cambios:
- **`RAG_API_MAX_QUEUE=4`:** como mucho 4 preguntas a la vez, sumando la que se responde y las que esperan. A partir de ahí, la web contesta "The server is busy answering other questions: try again in a minute." La API responde de una en una (una GPU), así que sin límite un solo visitante podría encolar peticiones para todos.
- **`RAG_ALLOWED_ORIGINS`:** con `PUBLIC_ORIGIN`, solo tu web puede llamar a la API desde un navegador.

Modelos de la web: Qwen3-1.7B por defecto, Qwen3-0.6B y Granite 4.0 Micro, todos con y sin agente (`Makefile`, `API_MODELS`).

## Seguridad y privacidad

- **Datos del CV:** el teléfono y el correo antiguo se enmascaran al responder, en el contexto del LLM, en la respuesta y en las fuentes (`rag.toml`, `private_data`). Es igual con cualquier modelo. Solo sale el correo público.
- **Lo que queda expuesto:** los endpoints de la API (`/chat`, `/search`, `/sources/{id}`, `/config`, `/metrics`, `/health`) y la documentación automática de FastAPI (`/docs`). No hay escritura ni datos de visitantes: las conversaciones viven en memoria y caducan a los 30 minutos.
- **Cambiar de modelo** afecta a todos los visitantes, porque solo hay uno cargado a la vez. El primer mensaje tras un cambio tarda unos 5–15 s más.
- **Mientras sirves la web**, desactiva la suspensión de Windows y no lances benchmarks: comparten la GPU.
