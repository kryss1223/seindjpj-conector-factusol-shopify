from pydantic import BaseModel, Field


class ShopifyOrderNoteAttribute(BaseModel):
    name: str | None = None
    value: str | None = None


class ShopifyOrderAddress(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    company: str | None = None
    address1: str | None = None
    address2: str | None = None
    city: str | None = None
    province: str | None = None
    country: str | None = None
    zip: str | None = None
    phone: str | None = None


class ShopifyOrderCustomer(BaseModel):
    id: int | None = None
    email: str | None = None
    phone: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    admin_graphql_api_id: str | None = None


class ShopifyOrderLineItem(BaseModel):
    id: int | None = None
    product_id: int | None = None
    variant_id: int | None = None
    sku: str | None = None
    name: str | None = None
    title: str | None = None
    quantity: int | None = None
    price: str | None = None


class ShopifyOrderPayload(BaseModel):
    id: int
    admin_graphql_api_id: str | None = None
    name: str | None = None
    email: str | None = None
    contact_email: str | None = None
    phone: str | None = None
    financial_status: str | None = None
    currency: str | None = None
    total_price: str | None = None
    subtotal_price: str | None = None
    note_attributes: list[ShopifyOrderNoteAttribute] = Field(default_factory=list)
    billing_address: ShopifyOrderAddress | None = None
    shipping_address: ShopifyOrderAddress | None = None
    customer: ShopifyOrderCustomer | None = None
    line_items: list[ShopifyOrderLineItem] = Field(default_factory=list)