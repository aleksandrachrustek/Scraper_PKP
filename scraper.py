import requests
from bs4 import BeautifulSoup
import pandas as pd
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
import logging
import hashlib
from urllib.parse import urljoin, quote
from playwright.sync_api import sync_playwright

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class PKPFullScraper:
    def __init__(self, base_url="https://bocznica.eu"):
        self.base_url = base_url
        self.all_trains = []
        self.all_wagons = []
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def get_page_content_with_js(self, url: str) -> str:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, timeout=30000)
                try:
                    page.wait_for_selector('table.zestawieniaTable, table.table0, p.searchwords', timeout=15000)
                except:
                    pass
                time.sleep(2)
                content = page.content()
                browser.close()
                return content
            except Exception as e:
                logger.error(f"Błąd ładowania {url}: {e}")
                browser.close()
                return ""

    def get_archive_list(self) -> List[Dict]:
        url = urljoin(self.base_url, "/archiwum/")
        html = self.get_page_content_with_js(url)
        if not html:
            return []
        soup = BeautifulSoup(html, 'html.parser')
        archives = []
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            if href.endswith('.html') and 'archiwum' in href and 'index' not in href:
                full_url = urljoin(self.base_url, href)
                text = a.get_text(strip=True)
                okres = None

                match = re.search(r'(\d{4})[/-](\d{4})', text)
                if match:
                    okres = f"{match.group(1)}/{match.group(2)}"
                else:
                    match = re.search(r'(\d{4})', text)
                    if match:
                        okres = match.group(1)
                    else:
                        match = re.search(r'(\d{4})', href)
                        if match:
                            okres = match.group(1)
                
                if okres:
                    archives.append({
                        'url': full_url,
                        'okres_rozkładowy': okres,
                        'nazwa': text
                    })
        
        logger.info(f"Znaleziono {len(archives)} archiwów")
        return archives

    def scrape_train_details(self, detail_url: str) -> Dict:
        try:
            if not detail_url:
                return {}
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.goto(detail_url, timeout=30000)
                try:
                    page.wait_for_selector('.Lok, .klasaA, .klasaB', timeout=10000)
                except:
                    pass
                html = page.content()
                browser.close()
            
            soup = BeautifulSoup(html, 'html.parser')
            result = {
                "jednostka": None,
                "predkosc_maks_kmh": None,
                "masa_t": None,
                "liczba_wagonow": None
            }
            
            # Jednostka
            lok = soup.find("p", class_="Lok")
            if lok:
                result["jednostka"] = lok.get_text(strip=True)
            
            # Prędkość – klasa "klasaA"
            speed_elem = soup.find("p", class_="klasaA")
            if speed_elem:
                speed_text = speed_elem.get_text(strip=True)
                m = re.search(r'(\d+)\s*km/h', speed_text)
                if m:
                    result["predkosc_maks_kmh"] = int(m.group(1))
            
            # Masa – klasa "klasaB"
            mass_elem = soup.find("p", class_="klasaB")
            if mass_elem:
                mass_text = mass_elem.get_text(strip=True)
                m = re.search(r'(\d+)\s*t', mass_text)
                if m:
                    result["masa_t"] = int(m.group(1))
            
            # Liczba wagonów – wszystkie divy z klasą "wagImage"
            wagons = soup.find_all("div", class_="wagImage")
            result["liczba_wagonow"] = len(wagons)
            
            return result
        except Exception as e:
            logger.debug(f"Błąd pobierania szczegółów dla {detail_url}: {e}")
            return {
                "jednostka": None,
                "predkosc_maks_kmh": None,
                "masa_t": None,
                "liczba_wagonow": None
            }

    def parse_main_page(self, url: str, okres_rozkładowy: str = None) -> List[Dict]:
        html = self.get_page_content_with_js(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="zestawieniaTable")
        if not table:
            logger.warning("Nie znaleziono tabeli zestawień")
            return []
        trains = []
        rows = table.find_all("tr")

        for row in rows:
            classes = row.get("class", [])
            if "row0" not in classes and "row1" not in classes:
                continue
            cells = row.find_all("td")
            if len(cells) < 3:
                continue
            try:
                # Numer pociągu
                num_text = cells[0].get_text(" ", strip=True)
                match = re.search(r"\(?\d+\)?\s*(\d+(?:/\d+)?)", num_text)
                if not match:
                    continue
                train_number = match.group(1)
                # Typ i nazwa (z data-searchwords)
                row_text = row.get("data-searchwords", "")
                train_type = None
                train_name = None
                type_match = re.search(r"^(ECE|EC|EIC|EIP|IC|TLK|IR|EN)", row_text)
                if type_match:
                    train_type = type_match.group(1)
                name_match = re.search(r"\d+(?:/\d+)?([A-ZŻŹĆĄŚĘŁÓŃ\-]+)", row_text)
                if name_match:
                    train_name = name_match.group(1)
                # Relacja
                route_text = cells[2].get_text(separator=" ", strip=True)
                route_text = re.sub(r"Zestawienie ważne.*$", "", route_text)
                start_station = start_time = end_station = end_time = None
                parts = route_text.split(" - ")
                if len(parts) >= 2:
                    first = parts[0].strip()
                    m = re.match(r"^(.*?)\s+(\d{2}:\d{2})$", first)
                    if m:
                        start_station = m.group(1).strip()
                        start_time = m.group(2)
                    last = parts[-1].strip()
                    m = re.match(r"^(.*?)\s+(\d{2}:\d{2})$", last)
                    if m:
                        end_station = m.group(1).strip()
                        end_time = m.group(2)
                # Link szczegółów
                detail_url = None
                onclick = row.get("onclick", "")
                m = re.search(r"location\.href='([^']+)'", onclick)
                if m:
                    path = quote(m.group(1), safe="/")
                    detail_url = urljoin(self.base_url + "/", path)
                # ID pociągu
                raw_id = f"{train_number}_{train_name}_{start_station}_{end_station}_{start_time}_{end_time}"
                train_id = hashlib.md5(raw_id.encode("utf-8")).hexdigest()

                train = {
                    "id_pociagu": train_id,
                    "numer_pociagu": train_number,
                    "typ_pociagu": train_type,
                    "nazwa_pociagu": train_name,
                    "stacja_poczatkowa": start_station,
                    "godzina_startu": start_time,
                    "stacja_koncowa": end_station,
                    "godzina_konca": end_time,
                    "data_waznosci_zestawienia": None,
                    "data_aktualizacji_strony": datetime.now().strftime("%Y-%m-%d"),
                    "okres_rozkładowy": okres_rozkładowy,
                    "url_zrodlowy": url,
                    "url_szczegoly": detail_url,
                    "jednostka": None,
                    "predkosc_maks_kmh": None,
                    "masa_t": None,
                    "liczba_wagonow": None,
                    "dlugosc_skladu": None,
                    "trakcja": None,
                    "typ_skladu": None,
                    "czy_ezt": False
                }
                trains.append(train)

            except Exception as e:
                logger.debug(f"Błąd wiersza: {e}")

        logger.info(f"Znaleziono {len(trains)} pociągów na stronie głównej")
        return trains

    def parse_archive_page(self, url: str, okres_rozkładowy: str) -> List[Dict]:
        html = self.get_page_content_with_js(url)
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        trains = []
        tables = soup.find_all("table", class_="table0")

        for table in tables:
            rows = table.find_all("tr")
            if len(rows) < 2:
                continue
            try:
                route_row = rows[0]
                route_text = route_row.get_text(" ", strip=True)
                route_match = re.search(r"(.+?)\s+(\d{2}:\d{2}).*?-\s*(.+?)\s+(\d{2}:\d{2})", route_text)
                start_station = start_time = end_station = end_time = None
                if route_match:
                    start_station = route_match.group(1).strip()
                    start_time = route_match.group(2)
                    end_station = route_match.group(3).strip()
                    end_time = route_match.group(4)

                train_row = rows[1]
                first_td = train_row.find("td")
                if not first_td:
                    continue
                text = first_td.get_text(" ", strip=True)

                number_match = re.search(r"\)\s*(\d+(?:/\d+)?)", text)
                if not number_match:
                    continue
                train_number = number_match.group(1)

                type_match = re.search(r"\b(EIP|EIC|IC|TLK|ECE|EC|EN|IR)\b", text)
                train_type = type_match.group(1) if type_match else None

                names = first_td.find_all("b")
                train_name = names[1].get_text(strip=True) if len(names) >= 2 else None

                unit = None
                speed = None
                mass = None
                wagon_count = 0

                lok_elem = train_row.find("p", class_="Lok")
                if lok_elem:
                    unit = lok_elem.get_text(strip=True)

                speed_elem = train_row.find("p", string=re.compile(r"km/h"))
                if speed_elem:
                    m = re.search(r"(\d+)", speed_elem.get_text())
                    if m:
                        speed = int(m.group(1))

                mass_elem = train_row.find("p", string=re.compile(r"\bt\b"))
                if mass_elem:
                    m = re.search(r"(\d+)", mass_elem.get_text())
                    if m:
                        mass = int(m.group(1))

                wagons = train_row.find_all("div", class_="wagImage")
                wagon_count = len(wagons) - 1
                if wagon_count < 0:
                    wagon_count = 0

                traction_info = self.detect_traction_and_type(unit)

                raw_id = f"{train_number}_{train_name}_{okres_rozkładowy}_{start_station}_{end_station}_{start_time}_{end_time}"
                train_id = hashlib.md5(raw_id.encode("utf-8")).hexdigest()

                trains.append({
                    "id_pociagu": train_id,
                    "numer_pociagu": train_number,
                    "typ_pociagu": train_type,
                    "nazwa_pociagu": train_name,
                    "stacja_poczatkowa": start_station,
                    "godzina_startu": start_time,
                    "stacja_koncowa": end_station,
                    "godzina_konca": end_time,
                    "data_waznosci_zestawienia": None,
                    "data_aktualizacji_strony": datetime.now().strftime("%Y-%m-%d"),
                    "okres_rozkładowy": okres_rozkładowy,
                    "url_zrodlowy": url,
                    "url_szczegoly": None,
                    "jednostka": unit,
                    "predkosc_maks_kmh": speed,
                    "masa_t": mass,
                    "liczba_wagonow": wagon_count,
                    "dlugosc_skladu": None,
                    "trakcja": traction_info["trakcja"],
                    "typ_skladu": traction_info["typ_skladu"],
                    "czy_ezt": traction_info["czy_ezt"]
                })
            except Exception:
                continue

        logger.info(f"Znaleziono {len(trains)} pociągów w archiwum {okres_rozkładowy}")
        return trains

    def detect_traction_and_type(self, unit: str) -> Dict:
        result = {
            "trakcja": "nieznana",
            "typ_skladu": "nieznany",
            "czy_ezt": False
        }
        if not unit:
            return result

        unit_upper = unit.upper()

        if unit_upper.startswith("193"):
            result["trakcja"] = "elektryczna"
            result["typ_skladu"] = "lokomotywa"
            return result

        ezt = ["EN57", "EN71", "EN76", "EN77", "EN96", "EN97", "ED72", "ED73", "ED74", "ED78",
               "ED160", "ED250", "E4DCU", "FLIRT", "DART", "ELF"]
        electric = ["EU07", "EP07", "EP08", "EP09", "ET41", "ET42", "EU43", "EU44", "EU45", "EU46", "ET25"]
        diesel = ["SU42", "SU45", "SU46", "SU160", "SM42", "SM31", "ST40", "ST44", "ST45"]

        for e in ezt:
            if unit_upper.startswith(e):
                result["trakcja"] = "elektryczna"
                result["typ_skladu"] = "zespol_trakcyjny"
                result["czy_ezt"] = True
                return result
        for e in electric:
            if unit_upper.startswith(e):
                result["trakcja"] = "elektryczna"
                result["typ_skladu"] = "lokomotywa"
                return result
        for d in diesel:
            if unit_upper.startswith(d):
                result["trakcja"] = "spalinowa"
                result["typ_skladu"] = "lokomotywa"
                return result

        return result

    def run(self, max_archives: int = None) -> pd.DataFrame:
        main_trains = self.parse_main_page(self.base_url + "/", okres_rozkładowy=None)

        total_main = len(main_trains)
        for i, train in enumerate(main_trains):
            if train["url_szczegoly"]:
                details = self.scrape_train_details(train["url_szczegoly"])
                train.update(details)
                traction = self.detect_traction_and_type(details.get("jednostka"))
                train["trakcja"] = traction["trakcja"]
                train["typ_skladu"] = traction["typ_skladu"]
                train["czy_ezt"] = traction["czy_ezt"]

                if i % 50 == 0:
                    logger.info(f"Szczegóły strony głównej: {i}/{total_main}")
            time.sleep(0.2)

        self.all_trains.extend(main_trains)
        logger.info(f"Pobrano {len(main_trains)} pociągów ze strony głównej")

        archives = self.get_archive_list()
        if max_archives:
            archives = archives[:max_archives]

        for idx, arch in enumerate(archives):
            archive_trains = self.parse_archive_page(arch['url'], arch['okres_rozkładowy'])
            self.all_trains.extend(archive_trains)
            time.sleep(1)

        df = pd.DataFrame(self.all_trains)
        if not df.empty:
            #df = df.drop_duplicates(subset=['id_pociagu'])
            df['relacja'] = df['stacja_poczatkowa'].fillna('') + ' - ' + df['stacja_koncowa'].fillna('')

            def extract_year(period):
                if pd.isna(period):
                    return None
                period_str = str(period)
                if '/' in period_str:
                    return int(period_str.split('/')[0])
                elif period_str.isdigit():
                    return int(period_str)
                return None

            df['rok'] = df['okres_rozkładowy'].apply(extract_year)
            df['rozklad'] = df['okres_rozkładowy'].fillna('biezacy')

            df.to_csv('pociagi.csv', index=False, encoding='utf-8-sig')

            print("\n" + "=" * 60)
            print("STATYSTYKI KOŃCOWE")
            print(f"Łączna liczba pociągów: {len(df)}")
            print(f"Liczba okresów rozkładowych: {df['rozklad'].nunique()}")
            print(f"Okresy: {sorted(df['rozklad'].unique())}")
            print(f"\nPociągi z jednostkami: {df['jednostka'].notna().sum()}")
            print(f"\nTypy trakcji:")
            for trakcja, count in df['trakcja'].value_counts().items():
                print(f"  {trakcja}: {count} ({count/len(df)*100:.1f}%)")
            print(f"\nTypy składów:")
            for typ, count in df['typ_skladu'].value_counts().items():
                print(f"  {typ}: {count} ({count/len(df)*100:.1f}%)")
        else:
            print("Brak danych do zapisu.")

        return df


if __name__ == "__main__":
    scraper = PKPFullScraper()

    print("SCRAPER DANYCH")
    print("\nWybierz opcję:")
    print("1. Test - tylko 1 archiwum")
    print("2. Pełne - wszystkie archiwa")

    choice = input("\nWybierz (1/2): ").strip()
    if choice == "1":
        max_archives = 1
        print("\nUruchamiam test z 1 archiwum...")
    else:
        max_archives = None
        print("\nUruchamiam pełne scrapowanie wszystkich archiwów...")

    df = scraper.run(max_archives=max_archives)

    print("ZAKOŃCZONO!")
    print(f"Zapisano {len(df)} pociągów do pliku pociagi.csv")
