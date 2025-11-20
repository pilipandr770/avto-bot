# file: app/scrapers/mobile_de_client.py

import logging
from typing import Optional
import time

import requests

logger = logging.getLogger(__name__)


class MobileDeClient:
    """
    Простий клієнт для mobile.de, який:
    - маскується під браузер (User-Agent, Accept-Language, Referer);
    - використовує сесію з cookies;
    - акуратно обробляє 403/429.
    """

    BASE_REFERER = "https://www.mobile.de/"

    def __init__(self, timeout: int = 15):
        self.session = requests.Session()
        self.timeout = timeout

        # Мінімально правдоподібні заголовки браузера
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;"
                    "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
                ),
                "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
                "Connection": "keep-alive",
            }
        )

    def fetch(self, url: str, *, referer: Optional[str] = None) -> Optional[str]:
        """
        Повертає HTML сторінки як текст або None, якщо статус не 200.

        :param url: фінальний URL (https://suchen.mobile.de/fahrzeuge/details.html?...).
        :param referer: опціональний referer, якщо хочеш підставляти
                        оригінальний URL з email.
        """
        headers = {}
        if referer:
            headers["Referer"] = referer
        else:
            headers["Referer"] = self.BASE_REFERER

        try:
            resp = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                headers=headers,
            )
        except requests.RequestException as exc:
            logger.warning("Mobile.de request failed for %s: %s", url, exc)
            return None

        # Якщо сайт просить "повільніше"
        if resp.status_code == 429:
            logger.warning("Mobile.de rate-limited (429) for %s", url)
            # Можна додати backoff, якщо потрібно
            time.sleep(5)
            return None

        if resp.status_code == 403:
            logger.error("Mobile.de returned 403 Forbidden for %s", url)
            # тут можна додати логіку сповіщення/фолбек
            return None

        if resp.status_code != 200:
            logger.warning(
                "Mobile.de bad status code %s for %s",
                resp.status_code,
                url,
            )
            return None

        return resp.text