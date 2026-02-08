from __future__ import annotations

import os
from typing import Any, Dict, Optional

from google.adk.tools import ToolContext

from .supabase_client import sb


DEFAULT_SESSION_ID = os.environ.get("DEFAULT_SESSION_ID", "dev")
DEFAULT_USER_ID = os.environ.get("DEFAULT_USER_ID", "web_user")

def _sid(session_id: Optional[str], tool_context: Optional[ToolContext] = None) -> str:
    """
    Prefer the parent session id stored in state, then the ADK invocation context.
    Falls back to provided session_id, then DEFAULT_SESSION_ID.
    """
    if tool_context is not None:
        try:
            state_sid = tool_context.state.get("ps_session_id")
            if isinstance(state_sid, str) and state_sid.strip():
                return state_sid.strip()
        except Exception:
            pass
        try:
            return tool_context._invocation_context.session.id
        except Exception:
            pass
    sid = (session_id or "").strip()
    return sid or DEFAULT_SESSION_ID


def _uid(
    user_id: Optional[str],
    *,
    tool_context: Optional[ToolContext] = None,
    session_id: Optional[str] = None,
) -> str:
    """
    Prefer the parent user id stored in state, then the ADK invocation context.
    Falls back to provided user_id, then session_id, then DEFAULT_USER_ID.
    """
    if tool_context is not None:
        try:
            state_uid = tool_context.state.get("ps_user_id")
            if isinstance(state_uid, str) and state_uid.strip():
                return state_uid.strip()
        except Exception:
            pass
        try:
            return tool_context._invocation_context.session.user_id
        except Exception:
            pass
    uid = (user_id or "").strip()
    if uid:
        return uid
    sid = (session_id or "").strip()
    return sid or DEFAULT_USER_ID


def _emit_ui(tool_context: Optional[ToolContext], payload: Dict[str, Any]) -> None:
    if tool_context is None:
        return
    try:
        tool_context.actions.state_delta["ui"] = payload
    except Exception:
        pass


# Products


def search_products(
    query: str,
    category: Optional[str] = None,
    limit: int = 8,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    q = query.strip()
    t = sb().table("products").select("id,part_number,name,category").limit(limit)

    if category in ("refrigerator", "dishwasher"):
        t = t.eq("category", category)

    if len(q) >= 2:
        t = t.or_(f"part_number.ilike.%{q}%,name.ilike.%{q}%")

    res = t.execute()
    items = res.data or []
    _emit_ui(
        tool_context,
        {
            "type": "product_list",
            "title": "Search results",
            "items": items,
        },
    )
    return {"status": "ok", "items": items}


def get_product_by_part_number(
    part_number: str,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    pn = part_number.strip()
    res = (
        sb()
        .table("products")
        .select("id,part_number,name,category")
        .eq("part_number", pn)
        .limit(1)
        .execute()
    )
    if not res.data:
        return {"status": "not_found", "part_number": pn}
    product = res.data[0]
    _emit_ui(
        tool_context,
        {
            "type": "product_detail",
            "product": product,
        },
    )
    return {"status": "ok", "product": product}


# ----------------------------
# Compatibility
# ----------------------------

def check_compatibility(
    part_number: str,
    model_number: str,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    pn = part_number.strip()
    mn = model_number.strip()

    prod = sb().table("products").select("id,part_number,name,category").eq("part_number", pn).limit(1).execute()
    if not prod.data:
        return {"status": "not_found", "reason": "unknown_part_number", "part_number": pn}

    model = sb().table("appliance_models").select("id,model_number,brand").eq("model_number", mn).limit(1).execute()
    if not model.data:
        return {"status": "not_found", "reason": "unknown_model_number", "model_number": mn}

    link = (
        sb()
        .table("product_compatibility")
        .select("product_id,model_id")
        .eq("product_id", prod.data[0]["id"])
        .eq("model_id", model.data[0]["id"])
        .limit(1)
        .execute()
    )

    result = {
        "status": "ok",
        "compatible": bool(link.data),
        "part": prod.data[0],
        "model": model.data[0],
    }
    _emit_ui(
        tool_context,
        {
            "type": "compatibility",
            "part_number": prod.data[0]["part_number"],
            "model_number": model.data[0]["model_number"],
            "compatible": bool(link.data),
            "part": prod.data[0],
            "model": model.data[0],
        },
    )
    return result


def get_compatible_models(
    part_number: str,
    limit: int = 50,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    prod = get_product_by_part_number(part_number, tool_context=tool_context)
    if prod["status"] != "ok":
        return prod

    product_id = prod["product"]["id"]

    links = (
        sb()
        .table("product_compatibility")
        .select("model_id")
        .eq("product_id", product_id)
        .limit(limit)
        .execute()
    )

    model_ids = [r["model_id"] for r in (links.data or [])]
    if not model_ids:
        return {"status": "ok", "part": prod["product"], "models": []}

    models = (
        sb()
        .table("appliance_models")
        .select("model_number,brand")
        .in_("id", model_ids)
        .execute()
    )

    models_list = models.data or []
    _emit_ui(
        tool_context,
        {
            "type": "compatible_models",
            "part": prod["product"],
            "models": models_list,
        },
    )
    return {"status": "ok", "part": prod["product"], "models": models_list}


def get_compatible_parts(
    model_number: str,
    limit: int = 50,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    mn = model_number.strip()

    model = (
        sb()
        .table("appliance_models")
        .select("id,model_number,brand")
        .eq("model_number", mn)
        .limit(1)
        .execute()
    )

    if not model.data:
        return {"status": "not_found", "reason": "unknown_model_number", "model_number": mn}

    model_id = model.data[0]["id"]

    links = (
        sb()
        .table("product_compatibility")
        .select("product_id")
        .eq("model_id", model_id)
        .limit(limit)
        .execute()
    )

    product_ids = [r["product_id"] for r in (links.data or [])]
    if not product_ids:
        return {"status": "ok", "model": model.data[0], "parts": []}

    parts = (
        sb()
        .table("products")
        .select("part_number,name,category")
        .in_("id", product_ids)
        .execute()
    )

    parts_list = parts.data or []
    _emit_ui(
        tool_context,
        {
            "type": "compatible_parts",
            "model": model.data[0],
            "parts": parts_list,
        },
    )
    return {"status": "ok", "model": model.data[0], "parts": parts_list}


# ----------------------------
# Installation guides
# ----------------------------

def get_installation_guide(
    part_number: str,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    prod = get_product_by_part_number(part_number, tool_context=tool_context)
    if prod["status"] != "ok":
        return prod

    guides = (
        sb()
        .table("installation_guides")
        .select("id,title,steps,product_id")
        .eq("product_id", prod["product"]["id"])
        .limit(5)
        .execute()
    )
    if not guides.data:
        _emit_ui(
            tool_context,
            {
                "type": "installation_guides",
                "part": prod["product"],
                "guides": [],
                "replace_text": f"I couldn't find an installation guide for {part_number.strip()}.",
            },
        )
        return {"status": "not_found", "reason": "no_installation_guide", "part_number": part_number.strip()}

    guides_list = guides.data
    _emit_ui(
        tool_context,
        {
            "type": "installation_guides",
            "part": prod["product"],
            "guides": guides_list,
            "replace_text": f"Here is the installation guide for {part_number.strip()}.",
        },
    )
    return {"status": "ok", "part": prod["product"], "guides": guides_list}


# ----------------------------
# Transactions
# ----------------------------


def _cart_ui_payload(cart_state: Dict[str, Any]) -> Dict[str, Any]:
    items = []
    total_qty = 0
    for it in cart_state.get("items") or []:
        p = it.get("product") or {}
        qty = int(it.get("quantity") or 0)
        total_qty += qty
        items.append(
            {
                "part_number": p.get("part_number"),
                "name": p.get("name"),
                "category": p.get("category"),
                "quantity": qty,
                "unit_price_cents": it.get("unit_price_cents"),
            }
        )
    replace_text = (
        "Your cart is empty."
        if total_qty == 0
        else f"You have {total_qty} item{'s' if total_qty != 1 else ''} in your cart."
    )
    return {
        "type": "cart",
        "cart_id": cart_state.get("cart_id"),
        "items": items,
        "replace_text": replace_text,
    }

def create_or_get_cart(session_id: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    sid = _sid(session_id, tool_context)

    existing = (
        sb()
        .table("carts")
        .select("id,status,session_id")
        .eq("session_id", sid)
        .eq("status", "open")
        .limit(1)
        .execute()
    )
    if existing.data:
        return {"status": "ok", "cart_id": existing.data[0]["id"], "created": False, "session_id": sid}

    created = sb().table("carts").insert({"session_id": sid, "status": "open"}).execute()
    return {"status": "ok", "cart_id": created.data[0]["id"], "created": True, "session_id": sid}


def add_to_cart(
    session_id: str,
    part_number: str,
    quantity: int = 1,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    INCREMENT behavior: adds `quantity` more units to cart.
    """
    session_id = _sid(session_id, tool_context)
    cart = create_or_get_cart(session_id, tool_context=tool_context)
    if cart["status"] != "ok":
        return cart
    cart_id = cart["cart_id"]

    prod = get_product_by_part_number(part_number)
    if prod["status"] != "ok":
        return prod
    product = prod["product"]

    qty = int(quantity)
    if qty <= 0:
        return {"status": "error", "error": "quantity must be > 0"}

    cur = (
        sb()
        .table("cart_items")
        .select("id,quantity")
        .eq("cart_id", cart_id)
        .eq("product_id", product["id"])
        .limit(1)
        .execute()
    )

    if cur.data:
        new_qty = int(cur.data[0]["quantity"]) + qty
        upd = sb().table("cart_items").update({"quantity": new_qty}).eq("id", cur.data[0]["id"]).execute()
        result = {
            "status": "ok",
            "cart_id": cart_id,
            "action": "incremented",
            "item": {"part_number": product["part_number"], "name": product["name"], "quantity": upd.data[0]["quantity"]},
        }
        cart_state = get_cart(session_id, tool_context=tool_context)
        if cart_state.get("status") == "ok":
            _emit_ui(tool_context, _cart_ui_payload(cart_state))
        return result

    ins = sb().table("cart_items").insert({
        "cart_id": cart_id,
        "product_id": product["id"],
        "quantity": qty,
        "unit_price_cents": None,
    }).execute()

    result = {
        "status": "ok",
        "cart_id": cart_id,
        "action": "inserted",
        "item": {"part_number": product["part_number"], "name": product["name"], "quantity": ins.data[0]["quantity"]},
    }
    cart_state = get_cart(session_id, tool_context=tool_context)
    if cart_state.get("status") == "ok":
        _emit_ui(tool_context, _cart_ui_payload(cart_state))
    return result


def set_cart_item_quantity(
    session_id: str,
    part_number: str,
    quantity: int,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    SET behavior: sets absolute quantity (must be > 0).
    """
    session_id = _sid(session_id, tool_context)
    cart = create_or_get_cart(session_id, tool_context=tool_context)
    if cart["status"] != "ok":
        return cart
    cart_id = cart["cart_id"]

    prod = get_product_by_part_number(part_number)
    if prod["status"] != "ok":
        return prod
    product = prod["product"]

    qty = int(quantity)
    if qty <= 0:
        return {"status": "error", "error": "quantity must be > 0"}

    cur = (
        sb()
        .table("cart_items")
        .select("id,quantity")
        .eq("cart_id", cart_id)
        .eq("product_id", product["id"])
        .limit(1)
        .execute()
    )

    if cur.data:
        upd = sb().table("cart_items").update({"quantity": qty}).eq("id", cur.data[0]["id"]).execute()
        result = {
            "status": "ok",
            "cart_id": cart_id,
            "action": "set_quantity",
            "item": {"part_number": product["part_number"], "name": product["name"], "quantity": upd.data[0]["quantity"]},
        }
        cart_state = get_cart(session_id, tool_context=tool_context)
        if cart_state.get("status") == "ok":
            _emit_ui(tool_context, _cart_ui_payload(cart_state))
        return result

    ins = sb().table("cart_items").insert({
        "cart_id": cart_id,
        "product_id": product["id"],
        "quantity": qty,
        "unit_price_cents": None,
    }).execute()

    result = {
        "status": "ok",
        "cart_id": cart_id,
        "action": "inserted_with_quantity",
        "item": {"part_number": product["part_number"], "name": product["name"], "quantity": ins.data[0]["quantity"]},
    }
    cart_state = get_cart(session_id, tool_context=tool_context)
    if cart_state.get("status") == "ok":
        _emit_ui(tool_context, _cart_ui_payload(cart_state))
    return result


def remove_from_cart(
    session_id: str,
    part_number: str,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    Remove item entirely (delete row). This is the correct "set to 0" behavior.
    """
    session_id = _sid(session_id, tool_context)
    cart = create_or_get_cart(session_id, tool_context=tool_context)
    if cart["status"] != "ok":
        return cart
    cart_id = cart["cart_id"]

    prod = get_product_by_part_number(part_number)
    if prod["status"] != "ok":
        return prod
    product = prod["product"]

    cur = (
        sb()
        .table("cart_items")
        .select("id,quantity")
        .eq("cart_id", cart_id)
        .eq("product_id", product["id"])
        .limit(1)
        .execute()
    )
    if not cur.data:
        result = {"status": "ok", "cart_id": cart_id, "action": "no_op", "message": "Item not in cart."}
        cart_state = get_cart(session_id, tool_context=tool_context)
        if cart_state.get("status") == "ok":
            _emit_ui(tool_context, _cart_ui_payload(cart_state))
        return result

    sb().table("cart_items").delete().eq("id", cur.data[0]["id"]).execute()
    result = {"status": "ok", "cart_id": cart_id, "action": "removed", "item": {"part_number": product["part_number"], "name": product["name"]}}
    cart_state = get_cart(session_id, tool_context=tool_context)
    if cart_state.get("status") == "ok":
        _emit_ui(tool_context, _cart_ui_payload(cart_state))
    return result


def decrement_cart_item(
    session_id: str,
    part_number: str,
    quantity: int = 1,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    Remove `quantity` units. If result <= 0, delete row.
    """
    session_id = _sid(session_id, tool_context)
    cart = create_or_get_cart(session_id, tool_context=tool_context)
    if cart["status"] != "ok":
        return cart
    cart_id = cart["cart_id"]

    prod = get_product_by_part_number(part_number)
    if prod["status"] != "ok":
        return prod
    product = prod["product"]

    dec = int(quantity)
    if dec <= 0:
        return {"status": "error", "error": "quantity must be > 0"}

    cur = (
        sb()
        .table("cart_items")
        .select("id,quantity")
        .eq("cart_id", cart_id)
        .eq("product_id", product["id"])
        .limit(1)
        .execute()
    )
    if not cur.data:
        result = {"status": "ok", "cart_id": cart_id, "action": "no_op", "message": "Item not in cart."}
        cart_state = get_cart(session_id, tool_context=tool_context)
        if cart_state.get("status") == "ok":
            _emit_ui(tool_context, _cart_ui_payload(cart_state))
        return result

    current_qty = int(cur.data[0]["quantity"])
    new_qty = current_qty - dec

    if new_qty <= 0:
        sb().table("cart_items").delete().eq("id", cur.data[0]["id"]).execute()
        result = {"status": "ok", "cart_id": cart_id, "action": "removed", "item": {"part_number": product["part_number"], "name": product["name"]}}
        cart_state = get_cart(session_id, tool_context=tool_context)
        if cart_state.get("status") == "ok":
            _emit_ui(tool_context, _cart_ui_payload(cart_state))
        return result

    upd = sb().table("cart_items").update({"quantity": new_qty}).eq("id", cur.data[0]["id"]).execute()
    result = {"status": "ok", "cart_id": cart_id, "action": "decremented", "item": {"part_number": product["part_number"], "name": product["name"], "quantity": upd.data[0]["quantity"]}}
    cart_state = get_cart(session_id, tool_context=tool_context)
    if cart_state.get("status") == "ok":
        _emit_ui(tool_context, _cart_ui_payload(cart_state))
    return result


def get_cart(session_id: str, tool_context: Optional[ToolContext] = None) -> Dict[str, Any]:
    session_id = _sid(session_id, tool_context)
    cart = create_or_get_cart(session_id, tool_context=tool_context)
    if cart["status"] != "ok":
        return cart
    cart_id = cart["cart_id"]

    items = (
        sb()
        .table("cart_items")
        .select("id,quantity,unit_price_cents,product_id")
        .eq("cart_id", cart_id)
        .execute()
    )

    product_ids = list({i["product_id"] for i in (items.data or [])})
    products_by_id = {}

    if product_ids:
        prod_rows = sb().table("products").select("id,part_number,name,category").in_("id", product_ids).execute()
        products_by_id = {p["id"]: p for p in (prod_rows.data or [])}

    hydrated = []
    for it in (items.data or []):
        p = products_by_id.get(it["product_id"], {})
        hydrated.append({
            "quantity": it["quantity"],
            "unit_price_cents": it.get("unit_price_cents"),
            "product": p,
        })

    result = {"status": "ok", "cart_id": cart_id, "items": hydrated}
    _emit_ui(tool_context, _cart_ui_payload(result))
    return result


def estimate_shipping(
    session_id: str,
    zip_code: str,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    session_id = _sid(session_id, tool_context)
    cart_state = get_cart(session_id, tool_context=tool_context)
    if cart_state["status"] != "ok":
        return cart_state

    cart_id = cart_state["cart_id"]
    total_qty = sum(int(i["quantity"]) for i in cart_state["items"])
    if total_qty == 0:
        return {"status": "error", "error": "cart is empty", "cart_id": cart_id}

    options = [
        {"service": "Standard", "eta_days": "4-7", "cost_cents": 799 + 50 * total_qty},
        {"service": "Expedited", "eta_days": "2-3", "cost_cents": 1499 + 75 * total_qty},
    ]
    estimate = {"zip_code": zip_code.strip(), "total_items": total_qty, "options": options}

    sb().table("shipping_estimates").insert({
        "cart_id": cart_id,
        "zip_code": zip_code.strip(),
        "estimate_json": estimate,
    }).execute()

    result = {"status": "ok", "cart_id": cart_id, "estimate": estimate}
    _emit_ui(
        tool_context,
        {
            "type": "shipping",
            "zip_code": estimate.get("zip_code"),
            "total_items": estimate.get("total_items"),
            "options": estimate.get("options"),
        },
    )
    return result


def create_checkout_session(
    session_id: str,
    user_id: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    session_id = _sid(session_id, tool_context)
    user_id = _uid(user_id, tool_context=tool_context, session_id=session_id)
    base_url = os.environ.get("CHECKOUT_BASE_URL", "http://localhost:3000").rstrip("/")

    cart_state = get_cart(session_id, tool_context=tool_context)
    if cart_state["status"] != "ok":
        return cart_state

    cart_id = cart_state["cart_id"]
    if not cart_state["items"]:
        return {"status": "error", "error": "cart is empty", "cart_id": cart_id}

    created = sb().table("checkout_sessions").insert({"cart_id": cart_id, "status": "created"}).execute()
    session_uuid = created.data[0]["id"]
    checkout_url = f"{base_url}/checkout?session={session_uuid}"

    sb().table("checkout_sessions").update({"checkout_url": checkout_url, "status": "handed_off"}).eq("id", session_uuid).execute()
    # Create order + order items snapshot for history
    order = (
        sb()
        .table("orders")
        .insert(
            {
                "user_id": user_id,
                "cart_id": cart_id,
                "checkout_session_id": session_uuid,
                "status": "created",
            }
        )
        .execute()
    )
    order_id = order.data[0]["id"]

    items = cart_state.get("items") or []
    if items:
        order_items = []
        for it in items:
            p = it.get("product") or {}
            order_items.append(
                {
                    "order_id": order_id,
                    "product_id": p.get("id"),
                    "part_number": p.get("part_number") or "",
                    "name": p.get("name") or "",
                    "quantity": int(it.get("quantity") or 0),
                    "unit_price_cents": it.get("unit_price_cents"),
                }
            )
        sb().table("order_items").insert(order_items).execute()
    # Finalize cart: mark it non-open and clear items so a new cart starts empty.
    sb().table("cart_items").delete().eq("cart_id", cart_id).execute()
    sb().table("carts").update({"status": "finalized"}).eq("id", cart_id).execute()

    result = {
        "status": "ok",
        "cart_id": cart_id,
        "checkout_session_id": session_uuid,
        "checkout_url": checkout_url,
        "cart_finalized": True,
    }
    _emit_ui(
        tool_context,
        {
            "type": "checkout",
            "checkout_session_id": session_uuid,
            "checkout_url": checkout_url,
        },
    )
    return result


def list_checkout_history(
    session_id: str,
    limit: int = 10,
    offset: int = 0,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    List prior checkout sessions for the current demo session.
    """
    session_id = _sid(session_id, tool_context)

    limit = max(1, min(int(limit), 50))
    offset = max(0, int(offset))

    carts = (
        sb()
        .table("carts")
        .select("id")
        .eq("session_id", session_id)
        .execute()
    )
    cart_ids = [c["id"] for c in (carts.data or [])]
    if not cart_ids:
        return {
            "status": "ok",
            "items": [],
            "limit": limit,
            "offset": offset,
            "next_offset": offset,
            "has_more": False,
        }

    res = (
        sb()
        .table("checkout_sessions")
        .select("id,cart_id,status,checkout_url,created_at")
        .in_("cart_id", cart_ids)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    items = res.data or []
    return {
        "status": "ok",
        "items": items,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + len(items),
        "has_more": len(items) == limit,
    }


def list_order_history(
    user_id: Optional[str] = None,
    limit: int = 10,
    offset: int = 0,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    List prior orders for the current user.
    """
    uid = _uid(user_id, tool_context=tool_context)

    limit = max(1, min(int(limit), 50))
    offset = max(0, int(offset))

    orders_res = (
        sb()
        .table("orders")
        .select("id,cart_id,checkout_session_id,status,created_at")
        .eq("user_id", uid)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
        .execute()
    )
    orders = orders_res.data or []
    order_ids = [o["id"] for o in orders]

    items_by_order: Dict[str, list[Dict[str, Any]]] = {}
    if order_ids:
        items_res = (
            sb()
            .table("order_items")
            .select("order_id,part_number,name,quantity,unit_price_cents")
            .in_("order_id", order_ids)
            .execute()
        )
        for item in items_res.data or []:
            items_by_order.setdefault(item["order_id"], []).append(item)

    hydrated = []
    for order in orders:
        hydrated.append(
            {
                **order,
                "items": items_by_order.get(order["id"], []),
            }
        )

    result = {
        "status": "ok",
        "user_id": uid,
        "items": hydrated,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + len(hydrated),
        "has_more": len(hydrated) == limit,
    }
    _emit_ui(
        tool_context,
        {
            "type": "order_history",
            "orders": hydrated,
            "offset": offset,
            "has_more": len(hydrated) == limit,
        },
    )
    return result

def list_products(
    category: Optional[str] = None,
    limit: int = 12,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    Browse parts by category ('refrigerator' or 'dishwasher') without a search query.
    If category is omitted or "all", returns a combined list across both categories.
    """
    limit = max(1, min(int(limit), 25))
    cat = category.strip().lower() if isinstance(category, str) else ""

    if cat in ("", "all", "both", "any", "all categories", "refrigerator and dishwasher", "dishwasher and refrigerator", "refrigerator/dishwasher", "dishwasher/refrigerator"):
        per_cat = max(1, (limit + 1) // 2)
        fr = (
            sb()
            .table("products")
            .select("id,part_number,name,category")
            .eq("category", "refrigerator")
            .limit(per_cat)
            .execute()
        )
        dw = (
            sb()
            .table("products")
            .select("id,part_number,name,category")
            .eq("category", "dishwasher")
            .limit(per_cat)
            .execute()
        )
        items = (fr.data or []) + (dw.data or [])
        payload = {
            "status": "ok",
            "items": items[:limit],
            "categories": ["refrigerator", "dishwasher"],
            "limit": limit,
        }
        _emit_ui(
            tool_context,
            {
                "type": "product_list",
                "title": "All parts (refrigerator + dishwasher)",
                "items": items[:limit],
            },
        )
        return payload

    if cat not in ("refrigerator", "dishwasher"):
        return {"status": "error", "error": "category must be 'refrigerator' or 'dishwasher' (or 'all')"}

    res = (
        sb()
        .table("products")
        .select("id,part_number,name,category")
        .eq("category", cat)
        .limit(limit)
        .execute()
    )
    items = res.data or []
    _emit_ui(
        tool_context,
        {
            "type": "product_list",
            "title": f"{cat.title()} parts",
            "items": items,
        },
    )
    return {"status": "ok", "items": items, "category": cat, "limit": limit}


def list_supported_models(
    category: str,
    limit: int = 25,
    offset: int = 0,
    brand: Optional[str] = None,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    List models that have at least one compatible product in the given category
    ('refrigerator' or 'dishwasher').
    """
    cat = category.strip().lower()
    if cat not in ("refrigerator", "dishwasher"):
        return {"status": "error", "error": "category must be 'refrigerator' or 'dishwasher'"}

    limit = max(1, min(int(limit), 100))
    offset = max(0, int(offset))

    # Step 1: get product ids for category (paged)
    prod_rows = (
        sb()
        .table("products")
        .select("id")
        .eq("category", cat)
        .range(0, 999)  # keep bounded; for big catalogs you'd do this differently
        .execute()
    )
    product_ids = [p["id"] for p in (prod_rows.data or [])]
    if not product_ids:
        return {"status": "ok", "items": [], "limit": limit, "offset": offset, "has_more": False}

    # Step 2: find model_ids linked to those products (paged)
    links = (
        sb()
        .table("product_compatibility")
        .select("model_id")
        .in_("product_id", product_ids)
        .execute()
    )
    model_ids = sorted({r["model_id"] for r in (links.data or [])})
    if not model_ids:
        return {"status": "ok", "items": [], "limit": limit, "offset": offset, "has_more": False}

    # Step 3: page model rows
    q = (
        sb()
        .table("appliance_models")
        .select("model_number,brand")
        .in_("id", model_ids)
        .order("brand")
        .order("model_number")
    )
    if brand:
        q = q.ilike("brand", f"%{brand.strip()}%")

    res = q.range(offset, offset + limit - 1).execute()
    items = res.data or []
    payload = {
        "status": "ok",
        "category": cat,
        "items": items,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + len(items),
        "has_more": len(items) == limit,
    }
    _emit_ui(
        tool_context,
        {
            "type": "model_list",
            "title": f"Supported {cat.title()} models",
            "items": items,
            "offset": offset,
            "has_more": len(items) == limit,
        },
    )
    return payload

from typing import Any, Dict, Optional

def list_models(
    brand: Optional[str] = None,
    limit: int = 25,
    offset: int = 0,
    tool_context: Optional[ToolContext] = None,
) -> Dict[str, Any]:
    """
    List appliance models. Use pagination.
    NOTE: Without an appliance_type column, this lists all models in your DB.
    """
    q = sb().table("appliance_models").select("model_number,brand").order("brand").order("model_number")

    if brand:
        q = q.ilike("brand", f"%{brand.strip()}%")

    limit = max(1, min(int(limit), 100))     # cap for safety
    offset = max(0, int(offset))

    res = q.range(offset, offset + limit - 1).execute()
    items = res.data or []

    payload = {
        "status": "ok",
        "items": items,
        "limit": limit,
        "offset": offset,
        "next_offset": offset + len(items),
        "has_more": len(items) == limit,
    }
    _emit_ui(
        tool_context,
        {
            "type": "model_list",
            "title": "Models",
            "items": items,
            "offset": offset,
            "has_more": len(items) == limit,
        },
    )
    return payload
