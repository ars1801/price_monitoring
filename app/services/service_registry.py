from app.core.config import get_settings
from app.services.price_alert_service import PriceAlertService
from app.services.scrapper_service import ScraperService
from app.services.telegram_notifier import TelegramNotifier

scraper_service = ScraperService()
settings = get_settings()
telegram_notifier = TelegramNotifier(settings=settings)
price_alert_service = PriceAlertService(settings=settings, notifier=telegram_notifier)