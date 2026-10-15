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

st.set_page_config(page_title="Sorcery TCG Direct Drive Generator", page_icon="🔮", layout="centered")

st.title("🔮 Sorcery TCG - Generator z Dysku Google")
st.write("Aplikacja analizuje Twój publiczny folder Google Drive, wyciąga z niego czyste grafiki i buduje z nich arkusz PDF A4.")

# -------------------------------------------------------------------------
# 🧲 MIEJSCE NA TWÓJ LINK DO DYSKU GOOGLE
# Wklej tutaj swój link do udostępnionego publicznie folderu z grafikami:
LINK_DO_DYSKU = "https://drive.google.com/drive/folders/17IrJkRGmIU9fDSTU2JQEU9JlFzb5liLJ"
# -------------------------------------------------------------------------

decklist_input = st.text_area(
    "Wklej swoją listę kart (np. 1 Realm-Eater, 2 Pudge Butcher):",
    height=250,
    placeholder="1 Realm-Eater\n2 Pudge Butcher\n1 Ring of Morrigan"
)

def extract_folder_id(url):
    """Wyciąga unikalne ID folderu Google Drive z linku"""
    match = re.search(r'/folders/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    return None

@st.cache_data(ttl=600)
def fetch_all_files_from_gdrive(folder_id):
    """Pobiera spis nazw i identyfikatorów ID plików z publicznego katalogu Google Drive"""
    files_map = {}
    if not folder_id:
        return files_map
    
    # Publiczne API Google Drive pozwalające zindeksować zawartość bez kluczy autoryzacyjnych OAuth
    url = f"https://googleapis.com'{folder_id}'+in+parents+and+trashed=false&maxResults=1000&fields=files(id,name)"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for item in data.get('files', []):
                name = item.get('name', '').strip().lower()
                fid = item.get('id', '')
                
                # --- BLOKADA WERSJI FOIL (_f) ---
                # Jeśli plik na dysku zawiera w nazwie końcówkę foil, całkowicie go ignorujemy
                base_name, _ = os.path.splitext(name)
                if base_name.endswith('_f') or base_name.endswith('-f'):
                    continue
                    
                files_map[name] = fid
        else:
            st.error(f"Google Drive API zwróciło błąd statusu: {response.status_code}")
    except Exception as e:
        st.error(f"Błąd sieciowy indeksowania dysku: {e}")
    return files_map

def parse_input_text(text_block):
    """Niezawodny parser: rozbija linie, izoluje cyfry i wyciąga czyste nazwy kart"""
    decklist = {}
    for line in text_block.split('\n'):
        line = line.strip()
        if not line or line.lower() in ['spellbook', 'atlas', 'avatar', 'maybeboard']:
            continue
            
        # Wyłapuje cyfry na początku linii (np. "2 pudge butcher" lub "1 pudge")
        match = re.match(r'^(\d+)\s+(.+)$', line)
        if match:
            quan = int(match.group(1))
            name = match.group(2).strip().lower()
            decklist[name] = decklist.get(name, 0) + quan
        else:
            name = line.lower()
            decklist[name] = decklist.get(name, 0) + 1
    return decklist

def find_best_gdrive_match(card_name, files_map):
    """Elastyczne wyszukiwanie: dopasowuje plik z Dysku Google zawierający słowa kluczowe"""
    clean_card = card_name.replace('-', ' ').replace('_', ' ').replace("'", '').replace('!', '')
    words = clean_card.split()
    if not words:
        return None
        
    for filename_key, file_id in files_map.items():
        # Sprawdzamy czy nazwa pliku na dysku zawiera w sobie wszystkie człony nazwy karty
        if all(word in filename_key for word in words):
            return file_id
    return None

if st.button("✨ Generuj arkusz PDF prosto z Dysku Google", type="primary"):
    if not decklist_input.strip():
        st.error("❌ Najpierw wklej listę kart do pola tekstowego!")
    else:
        folder_id = extract_folder_id(LINK_DO_DYSKU)
        if not folder_id:
            st.error("❌ Wklejony w kodzie LINK_DO_DYSKU jest niepoprawny!")
        else:
            # Uruchomienie wyszukiwania i indeksowania struktury dysku
            with st.spinner("🔍 Indeksuję zawartość folderu Google Drive..."):
                files_map = fetch_all_files_from_gdrive(folder_id)
                
            if not files_map:
                st.error("❌ Nie udało się zczytać struktury plików z Dysku Google. Upewnij się, że folder ma uprawnienia 'Każda osoba mająca link może wyświetlać'.")
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
                    
                    # Wyszukiwanie pliku w mapie zintegrowanego folderu
                    drive_file_id = find_best_gdrive_match(card_name, files_map)
                    
                    if drive_file_id:
                        # Bezpośredni strumień pobierania pliku binarnego z Google Drive uc API
                        download_url = f"https://drive.google.com/uc?export=download&id={drive_file_id}"
                        try:
                            req = urllib.request.Request(download_url, headers={'User-Agent': 'Mozilla/5.0'})
                            with urllib.request.urlopen(req, timeout=12) as response:
                                img_data = response.read()
                                
                            image_obj = PILImage.open(io.BytesIO(img_data))
                            for _ in range(quantity):
                                final_images.append(image_obj)
                            print(f"Pobrano pomyślnie z Drive: {card_name}")
                        except Exception as e:
                            st.warning(f"⚠️ Serwer Google zablokował transfer pobierania dla pliku karty: '{card_name}'.")
                    else:
                        st.warning(f"⚠️ Nie zlokalizowano żadnej grafiki dla karty '{card_name}' w Twoim folderze.")
                    
                    current_card_index += 1
                    progress_bar.progress(min(current_card_index / len(decklist), 1.0))
                    
                if not final_images:
                    st.error("❌ BŁĄD: Żaden plik graficzny nie został wygenerowany. Upewnij się, że nazwy kart pokrywają się z nazwami na Dysku.")
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
