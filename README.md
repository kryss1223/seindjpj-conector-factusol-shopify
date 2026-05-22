# 🔗 SEIND JPJ E-commerce Connect

API middleware desarrollada con **FastAPI** para conectar **Shopify** con **TeamSystem FactuSOL**.

El objetivo inicial es recibir eventos reales desde Shopify, especialmente la creación de clientes, y preparar la integración para validar si dichos clientes ya existen en FactuSOL.

---

## 📌 1. Introducción y problema

Actualmente existen dos sistemas principales:

| Sistema | Función |
|---|---|
| **Shopify** | Canal e-commerce donde se crean clientes online |
| **FactuSOL** | Sistema de gestión donde existen clientes históricos |
| **API FastAPI** | Middleware encargado de comunicar ambos sistemas |

El problema principal es que la tienda necesita saber si un cliente creado en Shopify ya existe en FactuSOL.

Esta información puede afectar a:

- Condiciones comerciales.
- Clasificación del cliente.
- Formas de pago disponibles.
- Flujo posterior de venta.
- Sincronización futura con gestión/facturación.

La integración no conecta Shopify directamente con FactuSOL. En su lugar, se crea una capa intermedia:

Shopify  ─────▶  FastAPI Middleware  ─────▶  FactuSOL

Esta API permitirá controlar la lógica, registrar errores, evitar duplicidades y preparar futuras ampliaciones.

🎯 2. Objetivo

El objetivo de esta primera fase es validar que Shopify puede comunicarse correctamente con el backend propio.

✅ Objetivos completados
Estado	Objetivo
✅	Crear proyecto base con FastAPI
✅	Organizar la API por módulos
✅	Crear endpoint de salud /health
✅	Crear endpoint para webhooks de Shopify
✅	Exponer API local mediante ngrok
✅	Configurar webhook real en Shopify
✅	Recibir evento customers/create
✅	Leer payload JSON enviado por Shopify
✅	Responder correctamente con 200 OK
⏳ Objetivos pendientes
Estado	Objetivo
⏳	Validar firma HMAC de Shopify
⏳	Crear schemas Pydantic para payloads
⏳	Normalizar datos del cliente
⏳	Consultar Shopify Admin GraphQL API
⏳	Definir origen del NIF/CIF
⏳	Preparar mock de FactuSOL
⏳	Integrar API real de FactuSOL
⏳	Clasificar clientes según existencia en FactuSOL
⏳	Actualizar Shopify mediante tags o metafields
🔄 3. Flujo validado

El flujo probado actualmente es:

1. Se crea o prueba un evento de cliente en Shopify.
2. Shopify lanza el webhook customers/create.
3. Shopify envía una petición POST a la URL configurada.
4. ngrok recibe la petición HTTPS.
5. ngrok redirige la petición al backend FastAPI local.
6. FastAPI ejecuta el endpoint correspondiente.
7. La API lee el payload JSON del cliente.
8. La API responde 200 OK.
Diagrama del flujo
┌──────────────────────────┐
│        Shopify           │
│  Evento customers/create │
└─────────────┬────────────┘
              │ POST JSON
              ▼
┌──────────────────────────┐
│          ngrok           │
│  URL pública HTTPS       │
└─────────────┬────────────┘
              │ Redirección local
              ▼
┌──────────────────────────┐
│        FastAPI           │
│ /webhooks/shopify/...    │
└─────────────┬────────────┘
              │ Lee payload
              ▼
┌──────────────────────────┐
│      Respuesta 200 OK    │
└──────────────────────────┘
Resultado obtenido
POST /webhooks/shopify/customers-create → 200 OK

Esto confirma que Shopify ya puede comunicarse con la API propia.

🧩 4. Arquitectura
Arquitectura general
┌─────────────┐
│  Shopify    │
└──────┬──────┘
       │ Webhook customers/create
       ▼
┌─────────────┐
│   ngrok     │
│ HTTPS tunnel│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   FastAPI   │
│ Middleware  │
└──────┬──────┘
       │ Futuro
       ▼
┌─────────────┐
│  FactuSOL   │
└─────────────┘
📁 Estructura del proyecto
shopify-factusol-connector/
│
├── app/
│   ├── main.py
│   ├── __init__.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── __init__.py
│   │       ├── health.py
│   │       └── shopify_webhooks.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   └── config.py
│   │
│   ├── schemas/
│   │   └── __init__.py
│   │
│   └── services/
│       └── __init__.py
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
🧱 Componentes principales
Componente	Descripción
main.py	Punto de entrada de la aplicación FastAPI
health.py	Endpoint de comprobación del estado de la API
shopify_webhooks.py	Endpoints para recibir eventos desde Shopify
config.py	Configuración centralizada mediante variables de entorno
schemas/	Carpeta reservada para modelos Pydantic
services/	Carpeta reservada para lógica de negocio e integraciones
🌐 Endpoints actuales
Método	Endpoint	Uso
GET	/health	Verificar que la API está activa
POST	/webhooks/shopify/customers-create	Recibir webhook real de Shopify
POST	/webhooks/shopify/customers-create/test	Probar manualmente desde Swagger
Endpoint real de Shopify
POST /webhooks/shopify/customers-create

Este endpoint es el que debe configurarse en Shopify.

Endpoint de test
POST /webhooks/shopify/customers-create/test

Este endpoint solo se usa para pruebas manuales desde /docs.

🛠️ Configuración usada en Shopify

Webhook configurado:

Campo	Valor
Evento	Customer creation
Topic técnico	customers/create
Formato	JSON
Método	POST
URL	/webhooks/shopify/customers-create

Ejemplo de URL pública con ngrok:

https://77d2-79-116-174-143.ngrok-free.app/webhooks/shopify/customers-create
📦 Payload recibido

Durante la prueba se recibió correctamente un payload de cliente con campos como:

id
created_at
updated_at
first_name
last_name
state
note
verified_email
email
phone
currency
addresses
default_address
admin_graphql_api_id


⚙️ Ejecución local
1. Instalar dependencias
pip install -r requirements.txt
2. Levantar FastAPI
uvicorn app.main:app --reload
3. Abrir documentación
http://127.0.0.1:8000/docs
4. Exponer API local con ngrok
ngrok http 8000
🔐 Variables de entorno

El proyecto utiliza variables de entorno para evitar exponer credenciales.

Archivo de ejemplo:

APP_NAME=Shopify FactuSOL Connector
ENVIRONMENT=local

SHOPIFY_CLIENT_ID=
SHOPIFY_API_SECRET=
SHOPIFY_ACCESS_TOKEN=
SHOPIFY_SHOP_DOMAIN=
SHOPIFY_API_VERSION=2026-04

El archivo real .env no debe subirse al repositorio.

🚨 Seguridad

El archivo .env debe estar incluido en .gitignore.

.env
.env.*
!.env.example

No deben subirse al repositorio:

Secretos de Shopify.
Tokens de acceso.
Credenciales de FactuSOL.
URLs privadas.
Datos reales de clientes.
