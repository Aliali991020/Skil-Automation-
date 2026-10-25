"""Stripe — frictionless conversion (Module 3).

Creates checkout links for qualified leads (course $497, coaching $2,800/mo,
brand deals $25,000). Simulation mode returns fake checkout URLs; no money is
ever moved without explicit human approval of the lead conversion.
"""

from __future__ import annotations

import os
from typing import Any

from ..activity import log
from ..config import PRODUCTS, STRIPE_CHECKOUT_BASE_URL
from .base import IntegrationBase


class Stripe(IntegrationBase):
    name = "stripe"

    def __init__(self, api_key: str | None = None) -> None:
        super().__init__(api_key or os.getenv("STRIPE_API_KEY"))

    def create_checkout(self, product_key: str, lead_id: int, success_url: str | None = None) -> dict[str, Any]:
        """Create a checkout session/link for a qualified lead."""
        product = PRODUCTS.get(product_key, PRODUCTS["course"])
        action = "stripe_checkout"
        detail = f"product={product_key} lead_id={lead_id} amount={product['price']}"

        if not self.configured:
            url = f"{STRIPE_CHECKOUT_BASE_URL}sim_{product_key}_{lead_id}"
            log(self.name, action, "simulated", f"{detail} -> {url}")
            return {
                "checkout_url": url,
                "session_id": f"sim_sess_{lead_id}",
                "product": product,
                "amount_cents": product["price"] * 100,
                "currency": product["currency"],
                "simulated": True,
            }

        def live_call():
            import requests

            resp = requests.post(
                "https://api.stripe.com/v1/checkout/sessions",
                auth=(self.api_key, ""),
                data={
                    "mode": "payment" if product_key != "coaching" else "subscription",
                    "line_items[0][price_data][currency]": product["currency"],
                    "line_items[0][price_data][product_data][name]": product["name"],
                    "line_items[0][price_data][unit_amount]": product["price"] * 100,
                    "line_items[0][quantity]": 1,
                    "success_url": success_url or "https://example.com/success",
                    "cancel_url": success_url or "https://example.com/cancel",
                    "metadata[lead_id]": str(lead_id),
                },
                timeout=60,
            )
            resp.raise_for_status()
            return resp.json()

        try:
            data = self.call_with_retry(action, live_call)
            log(self.name, action, "ok", f"{detail}")
            return {
                "checkout_url": data.get("url", ""),
                "session_id": data.get("id", ""),
                "product": product,
                "amount_cents": data.get("amount_total", product["price"] * 100),
                "currency": data.get("currency", product["currency"]),
                "simulated": False,
            }
        except Exception as exc:  # noqa: BLE001
            log(self.name, action, "error", f"{detail}: {exc}")
            raise

    def health(self) -> dict[str, Any]:
        return {"service": self.name, "configured": self.configured, "mode": self.mode}
