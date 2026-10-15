import streamlit as st
import os
import re
import io
import urllib.request
import requests
from math import ceil
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

st.set_page_config(page_title="Sorcery TCG Public Proxy Generator", page_icon="🔮", layout="centered")

st.title("🔮 Sorcery TCG - Generator z Publicznego Dysku")
st.write("Wklej listę kart. Aplikacja przeszuka publiczne grafiki wydawcy Sorcery, zignoruje numerację plików (np. `001_`) oraz wersje foil (`_f`), generując idealny plik PDF A4.")

decklist_input = st.text_area(
    "Wklej swoją listę kart (np. 1 Realm-Eater, 2 Pudge Butcher):",
    height=250,
    placeholder="1 Realm-Eater\n2 Pudge Butcher\n1 Ring of Morrigan"
)

# -------------------------------------------------------------------------
# Identyfikator publicznego folderu Google Drive wydawcy gry Sorcery
FOLDER_ID = "17IrJkRGmIU9fDSTU2JQEU9JlFzb5liLJ"
# -------------------------------------------------------------------------

@st.cache_data(ttl=600)
def fetch_and_clean_gdrive_files(folder_id):
    """Pobiera listę plików z publicznego Dysku Google i oczyszcza ich nazwy z prefiksów oraz foil"""
    files_map = {}
    # Bezpieczne wywołanie oficjalnego publicznego punktu API Google Drive
    url = "https://googleapis.com"
    params = {
        'q': f"'{folder_id}' in parents and trashed = false",
        'maxResults': '1000',
        'fields': 'files(id,name)'
    }
    try:
        response = requests.get(url, params=params, timeout=12)
        if response.status_code == 200:
            data = response.json()
            for item in data.get('files', []):
                name = item.get('name', '').strip().lower()
                fid = item.get('id', '')
                
                # Usuwamy rozszerzenie pliku (np. .png, .jpg)
                base_name, _ = os.path.splitext(name)
                
                # --- BLOKADA WERSJI FOIL (_f) ---
                if base_name.endswith('_f') or base_name.endswith('-f'):
                    continue
                
                # --- IGNOROWANIE NUMERACJI (np. 001_) ---
                # Jeśli nazwa zaczyna się od cyfr i podkreślenia, odcinamy ten początek
                clean_file_name = re.sub(r'^\d+_\s*', '', base_name)
                
                # Zapisujemy w mapie: {oczyszczona_nazwa_pliku: id_pliku_gdrive}
                files_map[clean_file_name] = fid
        else:
            st.error(f"Google Drive API zwróciło status: {response.status_code}")
    except Exception as e:
        st.error(f"Błąd sieciowy podczas pobierania spisu plików: {e}")
    return files_map

def parse_input_text(text_block):
    """Parser: rozbija linie, izoluje cyfry ilości i wyciąga czyste nazwy kart"""
    decklist = {}
    for line in text_block.split('\n'):
        line = line.strip()
        if not line or line.lower() in ['spellbook', 'atlas', 'avatar', 'maybeboard', 'collection', 'deck history']:
            continue
            
        match = re.match(r'^(\d+)\s+(.+)\$', line)
        if match:
            quan = int(match.group(1))
            name = match.group(2).strip().lower()
            decklist[name] = decklist.get(name, 0) + quan
        else:
            name = line.lower()
            decklist[name] = decklist.get(name, 0) + 1
    return decklist

def find_best_gdrive_match(card_name, files_map):
    """Szuka dopasowania w zindeksowanym folderze na podstawie słów kluczowych"""
    # Oczyszczamy nazwę karty wpisaną przez użytkownika ze znaków specjalnych
    clean_card = card_name.replace('-', ' ').replace('_', ' ').replace("'", '').replace('!', '')
    words = clean_card.split()
    if not words:
        return None
        
    for filename_key, file_id in files_map.items():
        # Zamieniamy podkreślenia i myślniki w nazwie pliku na spacje, by ułatwić porównanie słów
        normalized_filename = filename_key.replace('_', ' ').replace('-', ' ')
        if all(word in normalized_filename for word in words):
            return file_id
    return None

if st.button("✨ Generuj arkusz PDF prosto z Dysku Google", type="primary"):
    if not decklist_input.strip():
        st.error("❌ Najpierw wklej listę kart do pola tekstowego!")
    else:
        with st.spinner("🔍 Łączę się z Dysku Google i indeksuję grafiki..."):
            files_map = fetch_and_clean_gdrive_files(FOLDER_ID)
            
        if not files_map:
            st.error("❌ Nie udało się zczytać struktury plików z Dysku Google.")
        else:
            decklist = parse_input_text(decklist_input)
            
            status_text = st.empty()
            progress_bar = st.progress(0)
            
            pdf_buffer = io.BytesIO()
            c = canvas.Canvas(pdf_buffer, pagesize=A4)
            
            card_width, card_height = 63.5 * mm, 88.9 * mm
            page_width, page_height = A4
            margin_x = (page_width - (3 * card_width)) / 2
            margin_y = (page_height - (3 * card_height)) / 2
            
            final_images = []
            current_card_index = 0
            
            for card_name, quantity in decklist.items():
                status_text.text(f"⏳ Szukam i pobieram z Drive: '{card_name}' (x{quantity})...")
                
                # Elastyczne wyszukiwanie dopasowania z pominięciem "001_"
                drive_file_id = find_best_gdrive_match(card_name, files_map)
                
                if drive_file_id:
                    download_url = f"https://google.com{drive_file_id}"
                    try:
                        req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req, timeout=12) as response:
                            img_data = response.read()
                            
                        image_obj = PILImage.open(io.BytesIO(img_data))
                        for _ in range(quantity):
                            final_images.append(image_obj)
                    except Exception as e:
                        st.warning(f"⚠️ Serwer Google zablokował transfer dla pliku karty: '{card_name}'.")
                else:
                    st.warning(f"⚠️ Nie zlokalizowano żadnej grafiki dla karty '{card_name}' w katalogu.")
                
                current_card_index += 1
                progress_bar.progress(min(current_card_index / len(decklist), 1.0))
                
            if not final_images:
                st.error("❌ BŁĄD: Żaden plik graficzny nie został pomyślnie pobrany.")
            else:
                status_text.text("✍️ Konstruowanie pliku PDF...")
                cards_per_page = 9
                
                for index, img_obj in enumerate(final_images):
                    pos = index % cards_per_page
                    col = pos % 3
                    row = 2 - (pos // 3)
                    
                    x = margin_x + (col * card_width)
                    y = margin_y + (row * card_height)
                    
                    c.drawInlineImage(img_obj, x, y, width=card_width, height=card_height)
                    c.setStrokeColorRGB(0.7, 0.7, 0.7)
                    c.setLineWidth(0.2)
                    c.rect(x, y, card_width, card_height, stroke=1, fill=0)
                    
                    if pos == 8 and index < len(final_images) - 1:
                        c.showPage()
                        
                c.save()
                pdf_buffer.seek(0)
                
                status_text.empty()
                progress_bar.empty()
                st.success(f"✅ Gotowe! Pomyślnie ułożono {len(final_images)} kart.")
                
                st.download_button(
                    label="📥 Pobierz gotowy PDF",
                    data=pdf_buffer,
                    file_name="sorcery_proxies_drive.pdf",
                    mime="application/pdf",
                    use_container_width=True
                )
