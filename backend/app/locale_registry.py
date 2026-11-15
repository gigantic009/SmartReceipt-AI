"""Locale hints for parsing; these are not legal tax rule packs."""
from dataclasses import dataclass

@dataclass(frozen=True)
class LocaleProfile:
    country_code: str
    display_name: str
    default_currency: str | None
    decimal_separator: str
    grouping_separator: str
    tax_families: tuple[str, ...]
    languages: tuple[str, ...]

PROFILES = {
 "IN": LocaleProfile("IN","India","INR",".",",",("GST","CGST","SGST","IGST","CESS"),("en","hi","bn")),
 "US": LocaleProfile("US","United States","USD",".",",",("Sales Tax","Local Tax","Hospitality Tax"),("en","es","zh")),
 "GB": LocaleProfile("GB","United Kingdom","GBP",".",",",("VAT",),("en",)),
 "DE": LocaleProfile("DE","Germany","EUR",",",".",("Umsatzsteuer","VAT"),("de",)),
 "FR": LocaleProfile("FR","France","EUR",","," ",("TVA","VAT"),("fr",)),
 "JP": LocaleProfile("JP","Japan","JPY",".",",",("Consumption Tax",),("ja",)),
 "CN": LocaleProfile("CN","China","CNY",".",",",("VAT","增值税"),("zh",)),
 "AU": LocaleProfile("AU","Australia","AUD",".",",",("GST",),("en",)),
 "AE": LocaleProfile("AE","United Arab Emirates","AED",".",",",("VAT",),("ar","en")),
}
def get_locale_profile(country_code: str | None) -> LocaleProfile | None:
    return PROFILES.get(country_code or "")
