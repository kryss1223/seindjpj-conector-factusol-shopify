from fastapi import APIRouter
"""
Endpoint para health cehck de la conexion. 
Hay que crear un router con prefijo y la funcion al crear
nuevas rutas como: 
/webhooks/shopify/customers-create
/webhooks/shopify/orders-create
/sync/customer
/admin/retry-event

"""

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("")
def health_check():
    return {
        "status": "ok",
        "service": "shopify-factusol-connector"
    }