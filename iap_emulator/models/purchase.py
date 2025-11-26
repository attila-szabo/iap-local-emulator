"""Purchase models - one-time product purchases and subscriptions.

Represents active purchases and their state.
"""

from enum import IntEnum
from typing import Optional
from pydantic import BaseModel, Field


class PurchaseState(IntEnum):
    """Purchase state for one-time products."""

    PURCHASED = 0  # Purchase completed
    CANCELED = 1  # Purchase canceled
    PENDING = 2  # Purchase pending


class ConsumptionState(IntEnum):
    """Consumption state for one-time products."""

    NOT_CONSUMED = 0  # Not yet consumed
    CONSUMED = 1  # Consumed


class AcknowledgementState(IntEnum):
    """Acknowledgement state."""

    NOT_ACKNOWLEDGED = 0  # Not yet acknowledged
    ACKNOWLEDGED = 1  # Acknowledged


class ProductPurchaseRecord(BaseModel):
    """Internal record for one-time product purchase."""

    token: str = Field(..., description="Unique purchase token")
    product_id: str = Field(..., description="Product ID")
    package_name: str = Field(..., description="Android package name")
    user_id: str = Field(..., description="User identifier")

    # Purchase state
    purchase_state: PurchaseState = Field(default=PurchaseState.PURCHASED, description="Purchase state")
    consumption_state: ConsumptionState = Field(
        default=ConsumptionState.NOT_CONSUMED, description="Consumption state"
    )
    acknowledgement_state: AcknowledgementState = Field(
        default=AcknowledgementState.NOT_ACKNOWLEDGED, description="Acknowledgement state"
    )

    # Timestamps
    purchase_time_millis: int = Field(..., description="Purchase time (Unix millis)")

    # Order info
    order_id: str = Field(..., description="Unique order ID")
    price_amount_micros: int = Field(..., description="Price paid in micros")
    price_currency_code: str = Field(default="USD", description="Currency code")

    # Developer payload (optional custom data)
    developer_payload: Optional[str] = Field(None, description="Developer-specified payload")

    def set_purchase_state(self, new_state: PurchaseState, reason: Optional[str] = None) -> None:
        """Change purchase state and log the transition.

        Args:
            new_state: New purchase state
            reason: Reason for state change
        """
        from iap_emulator.state_logger import log_purchase_state_change

        old_state = self.purchase_state
        if old_state != new_state:
            self.purchase_state = new_state
            log_purchase_state_change(
                token=self.token,
                product_id=self.product_id,
                old_state=old_state.name,
                new_state=new_state.name,
                reason=reason,
                user_id=self.user_id,
            )

    def set_consumption_state(self, new_state: ConsumptionState) -> None:
        """Change consumption state and log the transition.

        Args:
            new_state: New consumption state
        """
        from iap_emulator.state_logger import log_consumption_change

        old_state = self.consumption_state
        if old_state != new_state:
            self.consumption_state = new_state
            log_consumption_change(
                token=self.token,
                product_id=self.product_id,
                old_state=old_state.name,
                new_state=new_state.name,
                user_id=self.user_id,
            )

    def consume(self) -> None:
        """Mark purchase as consumed."""
        self.set_consumption_state(ConsumptionState.CONSUMED)

    def acknowledge(self) -> None:
        """Mark purchase as acknowledged."""
        old_state = self.acknowledgement_state
        if old_state != AcknowledgementState.ACKNOWLEDGED:
            self.acknowledgement_state = AcknowledgementState.ACKNOWLEDGED

    class Config:
        json_schema_extra = {
            "example": {
                "token": "emulator_product_xyz789...",
                "product_id": "com.example.premium_unlock",
                "package_name": "com.example.secureapp",
                "user_id": "user-456",
                "purchase_state": PurchaseState.PURCHASED,
                "consumption_state": ConsumptionState.NOT_CONSUMED,
                "acknowledgement_state": AcknowledgementState.NOT_ACKNOWLEDGED,
                "purchase_time_millis": 1700000000000,
                "order_id": "GPA.9876-5432-1098-76543",
                "price_amount_micros": 4990000,
                "price_currency_code": "USD",
            }
        }
