from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product, ProductSource, Source


class ProductSourceRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def get_or_create(
        self,
        *,
        product: Product,
        source: Source,
        product_url: str,
        category: str | None,
    ) -> ProductSource:
        product_source = self._db.scalar(
            select(ProductSource).where(
                ProductSource.source_id == source.id,
                ProductSource.product_url == product_url,
            )
        )
        if product_source:
            if category and product_source.category != category:
                product_source.category = category
            return product_source

        product_source = ProductSource(
            product=product,
            source=source,
            product_url=product_url,
            category=category,
            is_active=True,
        )
        self._db.add(product_source)
        self._db.flush()
        return product_source