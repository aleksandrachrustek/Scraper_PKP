import pandas as pd

INPUT_FILE = "pociagi_clean.csv"

print("ANALIZA DANYCH")
print("=" * 80)

df = pd.read_csv(INPUT_FILE)

print(f"\nLiczba rekordów: {len(df):,}")
print("\nTRAKCJA")
print(df["trakcja"].value_counts())
print("\nTYP SKŁADU")
print(df["typ_skladu"].value_counts())
print("\nTYPY POCIĄGÓW")
print(df["typ_pociagu"].value_counts())
print("\nLATA")
print(df["rok"].value_counts().sort_index())
print("\nMIĘDZYNARODOWE")
print(df["czy_miedzynarodowy"].value_counts())

print("\nTOP 20 STACJI STARTOWYCH")
top_start = (
    df["stacja_poczatkowa"]
    .value_counts()
    .head(20)
)
print(top_start)

print("\nTOP 20 STACJI KOŃCOWYCH")
top_end = (
    df["stacja_koncowa"]
    .value_counts()
    .head(20)
)
print(top_end)

print("\nTOP 30 STACJI OGÓŁEM")
station_usage = pd.concat([
    df["stacja_poczatkowa"],
    df["stacja_koncowa"]
])
top_stations = station_usage.value_counts().head(30)
print(top_stations)

print("\nTOP HUBY KOLEJOWE")
hubs = pd.concat([
    df["stacja_poczatkowa"],
    df["stacja_koncowa"]
])
print(
    hubs.value_counts()
    .head(25)
)

print("\nTOP 30 RELACJI")
top_routes = (
    df["relacja"]
    .value_counts()
    .head(30)
)
print(top_routes)

print("\nRELACJE OBECNE PRZEZ NAJWIĘCEJ LAT")
route_years = (
    df.groupby("relacja")["rok"]
    .nunique()
    .sort_values(ascending=False)
)
print(route_years.head(50))

print("\nTOP 20 JEDNOSTEK")
top_units = (
    df["jednostka"]
    .value_counts()
    .head(20)
)
print(top_units)

print("\nJEDNOSTKI OBSŁUGUJĄCE NAJWIĘCEJ RELACJI")
versatile = (
    df.groupby("jednostka")["relacja"]
    .nunique()
    .sort_values(ascending=False)
)
print(versatile.head(20))

print("\nTOP JEDNOSTKI W KAŻDYM ROKU")
for year in sorted(df["rok"].dropna().unique()):
    print("\n" + "=" * 50)
    print(f"ROK {int(year)}")
    print("=" * 50)
    print(
        df[df["rok"] == year]["jednostka"]
        .value_counts()
        .head(10)
    )

print("\nPRĘDKOŚCI")
print(df["predkosc_maks_kmh"].describe())
print("\nNajczęstsze prędkości:")
print(
    df["predkosc_maks_kmh"]
    .value_counts()
    .head(20)
)

print("\nLICZBA WAGONÓW")
print(df["liczba_wagonow"].describe())
print("\nNajczęstsze długości składów:")
print(
    df["liczba_wagonow"]
    .value_counts()
    .head(20)
)

print("\nMASA POCIĄGÓW")
print(df["masa_t"].describe())

print("\nTOP 20 NAJDŁUŻSZYCH SKŁADÓW")
cols = [
    "numer_pociagu",
    "jednostka",
    "liczba_wagonow",
    "masa_t",
    "relacja"
]
print(
    df.sort_values(
        "liczba_wagonow",
        ascending=False
    )[cols]
    .head(20)
)

print("\nTOP 20 NAJCIĘŻSZYCH SKŁADÓW")
print(
    df.sort_values(
        "masa_t",
        ascending=False
    )[cols]
    .head(20)
)

print("\nTOP 20 NAJSZYBSZYCH POCIĄGÓW")
print(
    df.sort_values(
        "predkosc_maks_kmh",
        ascending=False
    )[[
        "numer_pociagu",
        "jednostka",
        "predkosc_maks_kmh",
        "relacja"
    ]]
    .head(20)
)

print("\nŚREDNIA PRĘDKOŚĆ WG TYPU POCIĄGU")
print(
    df.groupby("typ_pociagu")
    ["predkosc_maks_kmh"]
    .mean()
    .round(1)
    .sort_values(ascending=False)
)

print("\nŚREDNIA MASA WG TYPU POCIĄGU")
print(
    df.groupby("typ_pociagu")
    ["masa_t"]
    .mean()
    .round(0)
    .sort_values(ascending=False)
)

print("\nKRAJOWE VS MIĘDZYNARODOWE")
international_share = (
    df["czy_miedzynarodowy"]
    .mean()
    * 100
)
print(
    f"Międzynarodowe: {international_share:.1f}%"
)
print(
    f"Krajowe: {100 - international_share:.1f}%"
)

print("\nTOP RELACJE MIĘDZYNARODOWE")
print(
    df[
        df["czy_miedzynarodowy"]
    ]["relacja"]
    .value_counts()
    .head(30)
)

print("\nZMIANY TABORU W LATACH")
pivot = pd.crosstab(
    df["rok"],
    df["jednostka"]
)
interesting = [
    "EU07",
    "EP09",
    "EU44",
    "193",
    "EU160",
    "EU200",
    "ED160",
    "ED250"
]
existing = [
    x for x in interesting
    if x in pivot.columns
]
print(
    pivot[existing]
)

print("\nTYP POCIĄGU VS TRAKCJA")
print(
    pd.crosstab(
        df["typ_pociagu"],
        df["trakcja"]
    )
)

# EKSPORT

top_start.to_csv(
    "top_stacje_start.csv",
    header=["liczba_pociagow"]
)
top_end.to_csv(
    "top_stacje_koniec.csv",
    header=["liczba_pociagow"]
)
top_routes.to_csv(
    "top_relacje.csv",
    header=["liczba_pociagow"]
)
top_units.to_csv(
    "top_jednostki.csv",
    header=["liczba_pociagow"]
)
route_years.to_csv(
    "relacje_lata.csv",
    header=["liczba_lat"]
)

print("\n" + "=" * 80)
print("ZAPISANO ANALIZE")
