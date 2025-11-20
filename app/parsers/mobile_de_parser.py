# file: app/parsers/mobile_de_parser.py

import logging
from typing import Optional

from app.scrapers.mobile_de_client import MobileDeClient

logger = logging.getLogger(__name__)

client = MobileDeClient()


def parse_mobile_de(final_url: str, *, email_url: Optional[str] = None):
    """
    final_url – це вже 'final url https://suchen.mobile.de/fahrzeuge/details.html?...'
    email_url – початковий click/news URL з листа, який можна передати як Referer.
    """

    html = client.fetch(final_url, referer=email_url)
    if html is None:
        logger.debug("Skipping URL %s, no HTML fetched", final_url)
        return None

    # TODO: твоя існуюча логіка розбору HTML mobile.de
    # наприклад:
    # soup = BeautifulSoup(html, "html.parser")
    # витягуєш фото, ціну, модель, і т.д.

    return ...