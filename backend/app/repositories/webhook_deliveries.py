from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.webhook_delivery import WebhookDelivery


class WebhookDeliveryAlreadyProcessedError(Exception):
    def __init__(self, existing: WebhookDelivery):
        self.existing = existing
        super().__init__(f"Webhook delivery already processed: {existing.delivery_id}")


class WebhookDeliveryRepository:
    def __init__(self, db: Session):
        self.db = db

    def is_processed(self, delivery_id: str) -> bool:
        return self.db.get(WebhookDelivery, delivery_id) is not None

    def get_by_delivery_id(self, delivery_id: str) -> WebhookDelivery | None:
        return self.db.get(WebhookDelivery, delivery_id)

    def record(
        self,
        delivery_id: str,
        *,
        event_type: str,
        outcome: str,
        action: str | None = None,
        repository: str | None = None,
        task_id: int | None = None,
    ) -> WebhookDelivery:
        existing = self.get_by_delivery_id(delivery_id)
        if existing:
            raise WebhookDeliveryAlreadyProcessedError(existing)

        delivery = WebhookDelivery(
            delivery_id=delivery_id,
            event_type=event_type,
            action=action,
            repository=repository,
            task_id=task_id,
            outcome=outcome,
        )
        self.db.add(delivery)
        try:
            self.db.commit()
        except IntegrityError:
            self.db.rollback()
            existing = self.get_by_delivery_id(delivery_id)
            if existing:
                raise WebhookDeliveryAlreadyProcessedError(existing) from None
            raise
        self.db.refresh(delivery)
        return delivery
