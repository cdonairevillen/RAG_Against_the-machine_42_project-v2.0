# Despliegue en Oracle Cloud (Always Free)

Guía para publicar la web **sin coste** y **separada de Google Cloud**:
- **Servidor:** una máquina virtual ARM de Oracle Cloud *Always Free* con Docker. Corre la API y la web compilada (la misma imagen que se preparó para el Space de Hugging Face) detrás de **Caddy**, que pone el HTTPS.
- **Índice:** el bundle (snapshots de Qdrant + BM25) se copia a la máquina con `scp` y no se publica nunca.
- **Frontend (opcional):** la misma web en **GitHub Pages**, llamando a la API de Oracle.

**Por qué Oracle y no Hugging Face** (DEC-19 en `docs/es/decisions.md`): desde julio de 2026, Hugging Face exige un plan de pago (PRO) para crear Spaces de Docker o Gradio.

```
                 ┌──────────── VM de Oracle (ARM, 2 OCPU, 12 GB, Ubuntu) ────────────┐
navegador ─443─► │ Caddy (HTTPS, Let's Encrypt) ──► contenedor rag (:7860)            │
                 │                                   ├── FastAPI (src/api) + web/dist │
                 │                                   ├── RAG: router, bge-m3, reranker,│
                 │                                   │   Qwen3-0.6B (en la imagen)    │
                 │                                   └── Qdrant ◄── ~/rag/bundle (scp)│
                 └────────────────────────────────────────────────────────────────────┘
GitHub Pages (opcional) ── la misma web, apuntando a https://<nombre>.duckdns.org
```

**Medido** (imagen del Space con `--cpus=2 --memory=12g`, `FASE_7.md`):
- **RAM:** 4.2 GB tras cargar y 5.0 GB de pico respondiendo. Sobra margen en los 12 GB.
- **Velocidad en Oracle:** sin medir. Con 2 CPU x86 limitadas, cada respuesta tardaba 23–37 s; en ARM puede ser algo más lenta. Hay *streaming*, así que el texto aparece mientras se genera.

---

## 0. Antes de empezar (en tu PC)

1. **Índice al día:** `make index` y después `make bundle` (en `deploy/bundle/`, con SHA256).
   - ⚠️ El bundle contiene el material del CV **sin enmascarar** (el enmascarado se aplica al responder). No lo subas a ningún sitio público: solo a tu máquina con `scp`.
   - Mira en `deploy/bundle/bundle.json` que salen los dominios que quieres servir (`vllm`, `xquad`, `cv` y `about`).
2. **Código preparado:** `make space-stage`. Compila la web y deja en `deploy/stage/` solo lo que necesita la imagen, más `deploy/oracle/`.
3. **Clave SSH** (PowerShell), si no tienes una:
   ```powershell
   ssh-keygen -t ed25519 -f $HOME\.ssh\oracle_rag
   ```
   Al crear la máquina subirás `oracle_rag.pub`, la clave **pública**.

## 1. Cuenta de Oracle Cloud

1. Regístrate en https://www.oracle.com/cloud/free/.
   - Pide tarjeta para verificar la identidad. Con recursos *Always Free* **no cobra**. Puedes dejar la cuenta como *Free Tier*, sin pasarla a *Pay As You Go*: así es imposible que cobre.
2. **Región de origen (*home region*):** elígela con cuidado, porque **no se puede cambiar** y las máquinas gratuitas solo se crean en ella.
   - La más cercana es **Spain Central (Madrid)**.
   - Si al crear la máquina sale *"Out of capacity"*, prueba otro *Availability Domain* u otra hora. Pasa con las máquinas ARM gratuitas en las regiones más usadas.

## 2. Crear la máquina virtual

En la consola: **Compute → Instances → Create instance**.

| Campo | Valor |
|---|---|
| Name | `rag` |
| Image | **Canonical Ubuntu 24.04** (la variante para ARM, *aarch64*) |
| Shape | *Change shape → Ampere →* **VM.Standard.A1.Flex**, con **2 OCPU** y **12 GB** de memoria (el máximo gratuito; debe salir la etiqueta *Always Free-eligible*) |
| Networking | Crea una VCN nueva con su subred **pública** y marca **Assign a public IPv4 address** |
| SSH keys | *Upload public key files*: `oracle_rag.pub` |
| Boot volume | *Specify a custom boot volume size*: **100 GB** (la imagen ocupa ~23 GB, y el límite gratuito es de 200 GB en total) |

Pulsa **Create** y apunta la **IP pública** cuando la instancia esté en *Running*.

## 3. Abrir los puertos 80 y 443

Hay que abrirlos en **dos sitios**.

**a) En la red de Oracle:**
1. *Networking → Virtual cloud networks →* tu VCN *→ Security Lists → Default Security List → Add Ingress Rules*.
2. Añade dos reglas, cada una con *Source CIDR* `0.0.0.0/0`, *IP Protocol* TCP y *Destination port* **80** y **443**.

**b) En el cortafuegos de Ubuntu:** las imágenes de Oracle traen `iptables` cerrado. Conéctate y abre los puertos:
```powershell
ssh -i $HOME\.ssh\oracle_rag ubuntu@<IP>
```
```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

## 4. Instalar Docker (en la máquina)

```bash
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
exit        # vuelve a entrar para que el grupo se aplique
```
Comprueba que funciona con `docker run --rm hello-world`.

## 5. Un nombre para la máquina (DuckDNS, gratis)

Let's Encrypt necesita un nombre de dominio, no una IP.
1. Entra en https://www.duckdns.org con tu cuenta de GitHub.
2. Crea un subdominio, por ejemplo `rag-chrystian`, y pon en *current ip* la IP pública de la máquina.
3. Quedará `rag-chrystian.duckdns.org`. Comprueba en PowerShell que apunta bien con `nslookup rag-chrystian.duckdns.org`.

La IP pública se mantiene mientras exista la instancia. Si algún día cambia, actualízala en DuckDNS.

## 6. Subir el código y el índice

Desde la raíz del repo, en tu PC (PowerShell):
```powershell
ssh -i $HOME\.ssh\oracle_rag ubuntu@<IP> "mkdir -p ~/rag"
scp -i $HOME\.ssh\oracle_rag -r deploy/stage  ubuntu@<IP>:~/rag/app
scp -i $HOME\.ssh\oracle_rag -r deploy/bundle ubuntu@<IP>:~/rag/bundle
```
En la máquina queda `~/rag/app` (el código) y `~/rag/bundle` (el índice privado).

## 7. Configurar y arrancar (en la máquina)

```bash
cd ~/rag/app/deploy/oracle
cp .env.example .env
nano .env       # RAG_DOMAIN=rag-chrystian.duckdns.org
                # RAG_ALLOWED_ORIGINS=https://<tu-usuario>.github.io  (o * si no usas Pages)
docker compose up -d --build
```

- **La primera vez tarda:** construye la imagen para ARM, descarga los modelos (~6 GB) y restaura el índice. Calcula entre 20 y 40 minutos.
- **Para seguir el arranque:** `docker compose logs -f rag`. Termina con la línea de uvicorn escuchando en el puerto 7860.
- **Comprobación:** `curl https://rag-chrystian.duckdns.org/health` debe devolver `"loaded": true`.

Abre `https://rag-chrystian.duckdns.org` en el navegador: el contenedor sirve la web completa, sin Pages.

Los contenedores tienen `restart: unless-stopped`, así que se levantan solos si la máquina se reinicia.

## 8. GitHub Pages (opcional)

El servidor ya sirve la web en su propia URL. Pages sirve para tenerla también en `https://<tu-usuario>.github.io/<repo>/`, y sigue siendo gratis.

1. En el repo de GitHub, *Settings → Pages → Source*: **GitHub Actions**.
2. En *Settings → Secrets and variables → Actions → Variables*, crea `RAG_API_URL` = `https://rag-chrystian.duckdns.org`.
3. En *Actions*, lanza **"web (GitHub Pages)"**. Es manual a propósito: nada se publica sin que lo lances tú.
4. Comprueba que `RAG_ALLOWED_ORIGINS` en el `.env` del servidor es `https://<tu-usuario>.github.io`. Si cambias el `.env`, aplícalo con `docker compose up -d`.

**Por qué hace falta el HTTPS:** Pages se sirve por HTTPS, y el navegador bloquea las llamadas de una página HTTPS a una API sin HTTPS. Caddy y DuckDNS lo resuelven.

## 9. Actualizar

- **Código o web:**
  1. En tu PC, `make space-stage`.
  2. En la máquina, guarda el `.env` y borra el código viejo. `scp -r` copiaría la carpeta *dentro* de `~/rag/app` si ya existe:
     ```bash
     cp ~/rag/app/deploy/oracle/.env ~/rag/rag.env && rm -rf ~/rag/app
     ```
  3. En tu PC, copia el código como en el paso 6 (la línea de `deploy/stage`).
  4. En la máquina:
     ```bash
     cp ~/rag/rag.env ~/rag/app/deploy/oracle/.env
     cd ~/rag/app/deploy/oracle && docker compose up -d --build
     ```
- **Índice** (reindexado o material del CV cambiado):
  1. En tu PC, `make index` y `make bundle`.
  2. Borra `~/rag/bundle` en la máquina y vuelve a copiarlo con `scp`.
  3. En la máquina, `docker compose restart rag`. El índice se restaura en cada arranque.

## Límites y avisos

- **Una sola respuesta a la vez:** la generación se serializa (un solo LLM). Con varias visitas a la vez, esperan su turno.
- **Modelos:** la imagen solo trae el 0.6B (decisión P12 pendiente). El 1.7B cabría en memoria (estimado: ~9.5 GB en total, sin medir), pero sería lento en CPU.
- **Reclamo por inactividad:** Oracle puede reclamar una máquina gratuita si durante 7 días la CPU, la red **y** la memoria están por debajo del 20 %. El contenedor ocupa ~40 % de la memoria en reposo, así que no debería pasar.
- **Hilos:** `entrypoint.sh` ajusta los hilos de torch a las CPU del contenedor (DEC-17).
- **Seguridad:** solo están abiertos los puertos 22, 80 y 443. Mantén Ubuntu al día con `sudo apt update && sudo apt upgrade` de vez en cuando.
- **Antes de publicar nada,** revisa `docs/decisions.md` DEC-18 (datos privados en el historial de git).

## Alternativa de pago: Hugging Face Space

Si algún día tienes PRO, lo preparado en la Fase 6 sigue valiendo:
- `deploy/space/` (Dockerfile, `entrypoint.sh` y la ficha del Space).
- El bundle en un dataset **privado** de Hugging Face, que el contenedor descarga al arrancar con `RAG_BUNDLE_REPO` y el secreto `HF_TOKEN`.

El historial de git tiene la guía anterior.
