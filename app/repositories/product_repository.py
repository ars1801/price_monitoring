from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Product


class ProductRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def upsert(self, *, name: str, brand: str | None) -> Product:
        # Один Product может иметь несколько ProductSource в разных магазинах.
        product = self._db.scalar(select(Product).where(Product.name == name))
        if product:
            if brand and product.brand != brand:
                product.brand = brand
            return product
        
        product = Product(name=name, brand=brand)
        self._db.add(product)
        self._db.flush()
        return product

    def get_or_create(self, *, name: str, brand: str | None) -> Product:
        return self.upsert(name=name, brand=brand)
    
    def get_by_id(self, *, product_id: int) -> Product | None:
        return self._db.get(Product, product_id)