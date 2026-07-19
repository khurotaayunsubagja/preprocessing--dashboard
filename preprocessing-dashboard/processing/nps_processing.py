def calculate_nps(series):

    clean_series = series.dropna()

    promoters = clean_series[
        clean_series >= 9
    ].count()

    passives = clean_series[
        (clean_series >= 7) &
        (clean_series <= 8)
    ].count()

    detractors = clean_series[
        clean_series <= 6
    ].count()

    total = clean_series.count()

    if total == 0:

        return {
            "Promoters %": 0,
            "Passives %": 0,
            "Detractors %": 0,
            "NPS": 0
        }

    promoter_pct = round(
        (promoters / total) * 100,
        2
    )

    passive_pct = round(
        (passives / total) * 100,
        2
    )

    detractor_pct = round(
        (detractors / total) * 100,
        2
    )

    nps_score = round(
        promoter_pct - detractor_pct,
        2
    )

    return {
        "Promoters %": promoter_pct,
        "Passives %": passive_pct,
        "Detractors %": detractor_pct,
        "NPS": nps_score
    }