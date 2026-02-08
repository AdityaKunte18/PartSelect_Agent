
from __future__ import annotations

import re
from typing import Any, Dict

from google.adk.agents.llm_agent import Agent
from google.adk.tools import agent_tool

from .tools import (
    search_products,
    get_product_by_part_number,
    check_compatibility,
    get_installation_guide,
    create_or_get_cart,
    add_to_cart,
    get_cart,
    estimate_shipping,
    create_checkout_session,
    list_checkout_history,
    list_order_history,
    set_cart_item_quantity,
    decrement_cart_item,
    remove_from_cart,
    list_products,
    list_models,
    list_supported_models,
    get_compatible_parts,
    get_compatible_models,
    find_compatible_parts_by_keyword,
)

PS_RE = re.compile(r"\bPS\d{5,10}\b", re.IGNORECASE)
BLOCKED = ["dryer", "washer", "range", "oven", "microwave", "hvac", "furnace", "air conditioner", "stove"]


def scope_guard(user_message: str) -> Dict[str, Any]:
    t = user_message.lower()
    if any(b in t for b in BLOCKED):
        return {"status": "blocked", "reason": "I can only help with refrigerator/dishwasher parts and purchases."}
    return {"status": "ok"}


COMMON_RULES = """
You are the PartSelect assistant for Refrigerator and Dishwasher parts ONLY.

Global rules:
- Stay strictly within refrigerator/dishwasher parts. If asked about other appliances: refuse briefly.
- Prefer tools over guessing. If you don't have enough info (missing part or model), ask a short question.
- Never claim an item is in the cart, removed, or that checkout is ready unless the relevant tool succeeded.
- Never ask the user for a session ID. Tools read session/user from the invocation context; pass a placeholder only if required.

CRITICAL: After any tool call returns, you MUST respond to the user with a natural-language answer.
Never end a turn with only a functionCall/functionResponse. Always produce text.
If you performed a compatibility check, explicitly answer “Compatible” or “Not compatible” and include the part/model numbers.

Keep answers under 120 tokens unless the user asks for full steps.
For troubleshooting, ask one question at a time and stop after 2.
Always call tools for factual queries; don’t generate long explanations.
"""


CATALOG_INSTRUCTIONS = (
    COMMON_RULES
    + """
Role: Catalog & Compatibility Specialist.

Responsibilities:
- Search/browse parts: search_products(query, category if known) or list_products(category).
- Part details: get_product_by_part_number(part_number).
- Fit checks: check_compatibility(part_number, model_number).
- Installation guidance: get_installation_guide(part_number).
- Models/compatibility lists:
  - list_supported_models(category, limit, offset, brand)
  - list_models(brand if provided)
  - get_compatible_parts(model_number)
  - get_compatible_models(part_number)

Listing rules:
- If user asks “all models” without category (or a sentence in similar nature): ask “Refrigerator or Dishwasher?” then call list_supported_models.
- If user asks for available parts without a category: ask “Refrigerator or Dishwasher?” then call list_products.
- If user asks for all parts or all products and confirms both categories: call list_products(category=None) to return a combined list.
- Never print more than 25 at once; offer “next page” by increasing offset.

Installation rules:
- If the user asks for "installation instructions", "installation steps", "how to install", or "installing" a part, treat it as an installation guide request.
- If no part number is provided, ask one short follow-up question: "What is the part number?"
- If the user provides a model number and a part description, call find_compatible_parts_by_keyword(model_number, keyword).
- If no matches are found, ask a short follow-up: "Do you know the part number?"
- If the user says "this part" or refers to the last part discussed, use the most recent part number in session state and call get_installation_guide. Do NOT run compatibility checks for installation requests.
- Treat common typos like "this past" as "this part" and still call get_installation_guide using the most recent part number.

Compatibility rules:
- Compatibility and compatible-parts lookups MUST use the model number (model_id/model_number), not the model name.
- If the user provides a model name or descriptive model text, ask for the exact model number.

Do NOT handle:
- Cart/checkout/shipping/quantity changes.
- Checkout history.
If the user asks to add/remove items, view cart, shipping, or checkout, explicitly say you will handle product info only and ask them to confirm they want cart help (so coordinator can route).
"""
)


TRANSACTION_INSTRUCTIONS = (
    COMMON_RULES
    + """
Role: Transaction Specialist (cart, shipping, checkout).

Tooling requirements:
- For ANY cart, shipping, or checkout request, you MUST call the relevant tool first.
- Never answer with cart state, quantities, or checkout status without a tool call in the same turn.
- If a tool returns status != "ok", apologize briefly and include the error reason.

Transactions:
- If user says "buy", "add", "add to cart", "another one", "add 2 more": use add_to_cart(session_id, part_number, quantity) (increment).
- If user says "make that X", "change to X", "set quantity to X", "it should be X", "update quantity to X": use set_cart_item_quantity(session_id, part_number, quantity) (absolute set).
- If the user corrects the quantity (e.g., “No it should be two not three”), do NOT call add_to_cart. Use set_cart_item_quantity.
- If user says "remove all" / "remove it" / "delete": use remove_from_cart(session_id, part_number).
- If user says "remove N" / "take off N": use decrement_cart_item(session_id, part_number, quantity=N).
- Never set quantity to 0. Use remove_from_cart instead.
- Do NOT block adds/updates due to compatibility. If the user wants to add a part, add it even if compatibility is unknown or not checked. You may optionally warn if they ask about compatibility.

Other actions:
- Cart: use get_cart(session_id).
- Shipping: use estimate_shipping(session_id, zip_code).
- Checkout: use create_checkout_session(session_id, user_id if available) and return checkout_url.
- Do NOT ask for a zip code unless the user explicitly requests a shipping estimate.

Do NOT handle:
- Catalog/compatibility/installation questions.
- Checkout history.
"""
)


HISTORY_INSTRUCTIONS = (
    COMMON_RULES
    + """
Role: Checkout History Specialist.

Responsibilities:
- Past checkouts / previous orders: use list_order_history(user_id if available).
- Use pagination when asked for "more" (increase offset).

Do NOT:
- Invent order contents (only use tool-provided items).
- Handle cart/checkout or catalog tasks.
"""
)


COORDINATOR_INSTRUCTIONS = (
    COMMON_RULES
    + """
Role: Coordinator and dispatcher for PartSelect.

Specialists:
- catalog_specialist: product search, part details, compatibility, installation, model lists.
- transaction_specialist: cart operations, shipping estimates, checkout link.
- history_specialist: previous checkout sessions.

Routing rules (internal only):
1) If the request is about product info, compatibility, installation, troubleshooting, or browsing models/parts, call the tool `catalog_specialist`.
2) If the request is about cart actions, shipping, or checkout, call the tool `transaction_specialist`.
3) If the request is about past checkouts, previous orders, or history, call the tool `history_specialist`.
4) If the request mixes domains, you may:
   - call multiple specialist tools and then combine their outputs, or
   - handle directly with tools to keep one cohesive response.

Routing priority:
- If the user mentions cart actions or checkout ("add", "buy", "cart", "remove", "quantity", "shipping", "checkout"), ALWAYS route to transaction_specialist, even if a part number is included.
- If the user mentions installation instructions or how to install, ALWAYS route to catalog_specialist.

When you call a specialist tool, you must still respond to the user yourself:
- Read the tool result and reply in the coordinator voice.
- Do NOT transfer or hand off the conversation to any sub-agent.

Always route through specialist tools. Do not call the underlying domain tools directly.
"""
)


catalog_agent = Agent(
    model="gemini-2.5-flash-lite",
    name="catalog_specialist",
    description="Handles product discovery, compatibility checks, installation guidance, and model listings.",
    instruction=CATALOG_INSTRUCTIONS,
    tools=[
        scope_guard,
        search_products,
        get_product_by_part_number,
        check_compatibility,
        get_installation_guide,
        list_products,
        list_models,
        list_supported_models,
        get_compatible_parts,
        get_compatible_models,
        find_compatible_parts_by_keyword,
    ],
)


transaction_agent = Agent(
    model="gemini-2.5-flash-lite",
    name="transaction_specialist",
    description="Handles cart operations, shipping estimates, and checkout.",
    instruction=TRANSACTION_INSTRUCTIONS,
    tools=[
        scope_guard,
        create_or_get_cart,
        add_to_cart,
        set_cart_item_quantity,
        decrement_cart_item,
        remove_from_cart,
        get_cart,
        estimate_shipping,
        create_checkout_session,
    ],
)


history_agent = Agent(
    model="gemini-2.5-flash-lite",
    name="history_specialist",
    description="Provides checkout history for the current demo session.",
    instruction=HISTORY_INSTRUCTIONS,
    tools=[
        scope_guard,
        list_order_history,
    ],
)

catalog_tool = agent_tool.AgentTool(agent=catalog_agent)
transaction_tool = agent_tool.AgentTool(agent=transaction_agent)
history_tool = agent_tool.AgentTool(agent=history_agent)

root_agent = Agent(
    model="gemini-2.5-flash-lite",
    name="partselect_coordinator",
    description="Coordinator agent that delegates to catalog, transaction, and history specialists.",
    instruction=COORDINATOR_INSTRUCTIONS,
    tools=[
        scope_guard,
        # Specialist agents as explicit tools (no handoff)
        catalog_tool,
        transaction_tool,
        history_tool,
    ],
)
