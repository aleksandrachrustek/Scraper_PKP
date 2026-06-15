import pandas as pd
import numpy as np
import re

INPUT_FILE = "pociagi.csv"
OUTPUT_FILE = "pociagi_clean.csv"

print("Wczytywanie danych...")
df = pd.read_csv(INPUT_FILE)

print(f"Wczytano {len(df)} rekordów")

# DUPLIKATY
before = len(df)
df = df.drop_duplicates()
print(f"Usunięto {before - len(df)} pełnych duplikatów")

# CZYSZCZENIE STACJI
def clean_station_start(text):
    if pd.isna(text):
        return np.nan
    text = str(text)
    prefixes = [
        "Relacja:",
        "Kursuje:",
        "Obiegi:",
        "Info:",
        "Obowiązuje:"
    ]
    for p in prefixes:
        text = text.replace(p, "")
    text = re.sub(r"\s+", " ", text)

    return text.strip()

def clean_station_end(text):
    if pd.isna(text):
        return np.nan
    text = str(text)
    text = re.sub(r"\(\d{1,2}:\d{2}/\d{1,2}:\d{2}\)", "", text)
    parts = [x.strip() for x in text.split(" - ")]
    if len(parts) > 0:
        return parts[-1]

    return text.strip()

if "stacja_poczatkowa" in df.columns:
    df["stacja_poczatkowa"] = df["stacja_poczatkowa"].apply(
        clean_station_start
    )
if "stacja_koncowa" in df.columns:
    df["stacja_koncowa"] = df["stacja_koncowa"].apply(
        clean_station_end
    )

# NORMALIZACJA STACJI
station_map = {
    "Warszawa Wsch.": "Warszawa Wschodnia",
    "Warszawa Zach.": "Warszawa Zachodnia",
    "Warszawa Centr.": "Warszawa Centralna",
    "Krakow Gl.": "Kraków Główny",
    "Poznan Gl.": "Poznań Główny",
    "Wroclaw Gl.": "Wrocław Główny",
    "Gdynia Gl.": "Gdynia Główna",
}

station_map.update({
    "Praha hl. n.": "Praha hl.n.",
    "Praha hl.n": "Praha hl.n.",
    "Dnipro Hl": "Dnipro Hl.",
    "Kyiv Pas.": "Kyiv - Pas.",
})

for col in ["stacja_poczatkowa", "stacja_koncowa"]:
    if col in df.columns:
        df[col] = df[col].replace(station_map)

# KLASYFIKACJA TABORU
def classify_unit(unit):
    if pd.isna(unit):
        return ("nieznana", "nieznany")
    unit = str(unit).upper().strip()
    emu_patterns = [
        "ED160", "ED161", "ED250",
        "ED74", "ED72",
        "EN57", "EN71", "EN76",
        "EN77", "EN96", "EN97",
        "FLIRT", "DART", "ELF",
        "IMPULS"
    ]
    electric_patterns = [
        "193",
        "EU07", "EP07", "EP08", "EP09",
        "EU44", "EU160", "EU200",
        "ET41", "ET42",
        "X4EA", "CD_X4EA",
        "DB_X4EA", "BALTICX4EA",
        "WL10", "HRCS2",
        "SD85"
    ]
    diesel_patterns = [
        "SU42", "SU45", "SU46",
        "SU160", "SU4210",
        "SM42", "ST44",
        "M62", "754", "SN84"
    ]
    for p in emu_patterns:
        if p in unit:
            return ("elektryczna", "zespol_trakcyjny")
    for p in electric_patterns:
        if p in unit:
            return ("elektryczna", "lokomotywa")
    for p in diesel_patterns:
        if p in unit:
            return ("spalinowa", "lokomotywa")

    return ("nieznana", "nieznany")


classified = df["jednostka"].apply(classify_unit)
df["trakcja"] = classified.apply(lambda x: x[0])
df["typ_skladu"] = classified.apply(lambda x: x[1])


# CZYSZCZENIE MASY
if "masa_t" in df.columns:
    df["masa_t"] = pd.to_numeric(
        df["masa_t"],
        errors="coerce"
    )
    invalid_high = (df["masa_t"] > 1500).sum()
    df.loc[
        df["masa_t"] > 1500,
        "masa_t"
    ] = np.nan
    invalid_low = (
        (df["masa_t"] < 100)
        & df["masa_t"].notna()
    ).sum()
    df.loc[
        (df["masa_t"] < 100)
        & df["masa_t"].notna(),
        "masa_t"
    ] = np.nan

    print(f"Usunięto {invalid_high} mas >1500 t")
    print(f"Usunięto {invalid_low} mas <100 t")


# ROK
def extract_year(value):
    if pd.isna(value):
        return 2026
    try:
        return int(float(value))
    except:
        return 2026


if "okres_rozkładowy" in df.columns:
    df["rok"] = df["okres_rozkładowy"].apply(
        extract_year
    )


# RELACJA
df["relacja"] = (
    df["stacja_poczatkowa"].fillna("")
    + " -> "
    + df["stacja_koncowa"].fillna("")
)

# MIĘDZYNARODOWE
foreign_keywords = [
    "WIEN",
    "PRAHA",
    "BERLIN",
    "BUDAPEST",
    "OSTRAVA",
    "BRNO",
    "GRAZ",
    "MÜNCHEN",
    "MUNCHEN",
    "FRANKFURT",
    "KYIV",
    "DNIPRO",
    "ODESSA"
]

def is_international(row):
    txt = (
        str(row["stacja_poczatkowa"])
        + " "
        + str(row["stacja_koncowa"])
    ).upper()

    return any(
        keyword in txt
        for keyword in foreign_keywords
    )

df["czy_miedzynarodowy"] = df.apply(
    is_international,
    axis=1
)

# Najczęstsze artefakty
station_fixes = {
    "Pas.": "Kyiv - Pas.",
    "Hl.": "Dnipro Hl.",
}
df["stacja_koncowa"] = df["stacja_koncowa"].replace(station_fixes)
df["stacja_poczatkowa"] = df["stacja_poczatkowa"].replace(station_fixes)


# ZAPIS

df.to_csv(
    OUTPUT_FILE,
    index=False,
    encoding="utf-8-sig"
)

print("\nPODSUMOWANIE")
print(f"Liczba rekordów: {len(df)}")
print("\nTRAKCJA:")
print(df["trakcja"].value_counts())
print("\nTYP SKŁADU:")
print(df["typ_skladu"].value_counts())
print("\nTOP 20 STACJI START:")
print(df["stacja_poczatkowa"].value_counts().head(20))
print("\nTOP 20 STACJI KONIEC:")
print(df["stacja_koncowa"].value_counts().head(20))
print(f"\nZapisano.")