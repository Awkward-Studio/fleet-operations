import datetime
from dataclasses import dataclass

from django.db import models
from django.utils import timezone

from .models import RateBookStatus, RateBookType, RatePackage


class RateResolutionError(Exception):
    pass


class AmbiguousRateError(RateResolutionError):
    pass


@dataclass(frozen=True)
class RateResolution:
    package: RatePackage
    trace: list[dict]
    precedence: tuple[int, int, int]

    def as_dict(self):
        return {
            "rate_book_id": self.package.rate_book_id,
            "rate_package_id": self.package.id,
            "precedence": list(self.precedence),
            "trace": self.trace,
        }


def _booking_date(value):
    if isinstance(value, str):
        try:
            value = datetime.datetime.fromisoformat(value)
        except ValueError as exc:
            raise RateResolutionError("Invalid pickup_datetime format.") from exc
    if isinstance(value, datetime.datetime):
        return value.date() if timezone.is_naive(value) else timezone.localtime(value).date()
    if isinstance(value, datetime.date):
        return value
    raise RateResolutionError("pickup_datetime must be a date, datetime, or ISO datetime string.")


def _normalise(value):
    return (value or "").strip().lower()


def resolve_rate(
    *,
    booking_type,
    pickup_datetime,
    pickup_city,
    vehicle_category,
    duty_type,
    contract_id=None,
    customer_id=None,
    ota_source="",
    drop_city="",
):
    """Resolve a single package and return the complete, deterministic match trace."""

    booking_date = _booking_date(pickup_datetime)
    city = _normalise(pickup_city)
    destination = _normalise(drop_city)
    category = _normalise(vehicle_category)
    source = (ota_source or "").strip().upper()
    channel_order = {
        RateBookType.CORPORATE: 300,
        RateBookType.OTA: 200,
        RateBookType.PUBLIC: 100,
    }

    books = models.Q(rate_book__book_type=RateBookType.PUBLIC)
    if contract_id:
        books |= models.Q(
            rate_book__book_type=RateBookType.CORPORATE,
            rate_book__contract_id=contract_id,
        )
    elif customer_id:
        books |= models.Q(
            rate_book__book_type=RateBookType.CORPORATE,
            rate_book__contract__customer_id=customer_id,
        )
    if source:
        books |= models.Q(
            rate_book__book_type=RateBookType.OTA,
            rate_book__ota_source__iexact=source,
        )

    candidates = (
        RatePackage.objects.select_related("rate_book")
        .filter(
            books,
            rate_book__status=RateBookStatus.ACTIVE,
            rate_book__effective_start__lte=booking_date,
            duty_type=duty_type,
        )
        .filter(
            models.Q(rate_book__effective_end__isnull=True)
            | models.Q(rate_book__effective_end__gte=booking_date)
        )
        .filter(models.Q(city="") | models.Q(city__iexact=city))
        .filter(models.Q(vehicle_category="") | models.Q(vehicle_category__iexact=category))
        .filter(models.Q(route_from="") | models.Q(route_from__iexact=city))
        .filter(models.Q(route_to="") | models.Q(route_to__iexact=destination))
    )

    ranked = []
    for package in candidates:
        book = package.rate_book
        route_specificity = 0
        if package.route_from or package.route_to:
            route_specificity = 30
        elif package.city:
            route_specificity = 20
        elif package.zone:
            route_specificity = 10
        applicability_specificity = route_specificity + (1 if package.vehicle_category else 0)
        rank = (channel_order[book.book_type], applicability_specificity, book.priority)
        ranked.append((rank, package))

    if not ranked:
        raise RateResolutionError(
            f"No active rate package for booking_type='{booking_type}', city='{pickup_city}', "
            f"category='{vehicle_category}', duty_type='{duty_type}'."
        )

    ranked.sort(key=lambda item: (item[0], item[1].rate_book_id, item[1].id), reverse=True)
    winning_rank = ranked[0][0]
    winners = [package for rank, package in ranked if rank == winning_rank]
    trace = [
        {
            "rate_book_id": package.rate_book_id,
            "rate_book_code": package.rate_book.code,
            "rate_book_version": package.rate_book.version,
            "rate_package_id": package.id,
            "rate_package_code": package.code,
            "channel": package.rate_book.book_type,
            "precedence": list(rank),
            "selected": rank == winning_rank and len(winners) == 1,
        }
        for rank, package in ranked
    ]
    if len(winners) != 1:
        ids = ", ".join(str(package.id) for package in winners)
        raise AmbiguousRateError(
            f"Ambiguous equal-precedence rate packages ({ids}) for the supplied pricing inputs."
        )
    return RateResolution(package=winners[0], trace=trace, precedence=winning_rank)
