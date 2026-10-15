import streamlit as st
import os
import re
import io
import urllib.request
from math import ceil
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

st.set_page_config(page_title="Sorcery TCG Public Proxy Generator", page_icon="🔮", layout="centered")

st.title("🔮 Sorcery TCG - Generator z Publicznego Dysku")
st.write("Wklej listę kart. Aplikacja pobierze standardowe grafiki (całkowicie ignorując numerację plików np. `001_` oraz wersje foil `_f`) i wygeneruje idealnie wyskalowany plik PDF A4.")

decklist_input = st.text_area(
    "Wklej swoją listę kart (np. 1 Realm-Eater, 2 Pudge Butcher):",
    height=250,
    placeholder="1 Realm-Eater\n2 Pudge Butcher\n1 Ring of Morrigan"
)

def parse_input_text(text_block):
    """Parser: rozbija linie, izoluje cyfry ilości i wyciąga czyste nazwy kart"""
    decklist = {}
    lines = text_block.split('\n')
    for line in lines:
        line = line.strip()
        # Pomijanie nagłówków sekcji z kreatorów talii
        if not line or line.lower() in ['spellbook', 'atlas', 'avatar', 'maybeboard', 'collection', 'deck history']:
            continue
            
        # Niezawodny regex: szuka cyfry na początku linii i oddziela ją od nazwy karty
        match = re.match(r'^(\d+)\s+(.+)\$', line)
        if match:
            quan = int(match.group(1))
            name = match.group(2).strip().lower()
            decklist[name] = decklist.get(name, 0) + quan
        else:
            name = line.lower()
            decklist[name] = decklist.get(name, 0) + 1
    return decklist

if st.button("✨ Generuj arkusz PDF z Dysku Sorcery", type="primary"):
    if not decklist_input.strip():
        st.error("❌ Najpierw wklej listę kart do pola tekstowego!")
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
            # Czyszczenie wpisanej nazwy karty pod format wyszukiwania sieciowego
            clean_name = card_name.replace(' ', '-').replace('_', '-').replace("'", '').replace('!', '').strip().lower()
            
            # --- AUTOMATYCZNA BLOKADA WERSJI FOIL (_f) ---
            # Jeśli użytkownik dopisał końcówkę foil w tekście, program ją odcina by wymusić pobranie wersji standard
            if clean_name.endswith('-f') or clean_name.endswith('_f'):
                clean_name = clean_name[:-2]
                
            status_text.text(f"⏳ Pobieranie standardowej grafiki dla: {card_name} (Sztuk: {quantity})...")
            
            # Bezpośrednie odpytanie zindeksowanego serwera plików (CDN lustra dysku wydawcy)
            # Serwer ten automatycznie ignoruje prefiksy liczbowe typu 001_, mapując czyste nazwy
            target_url = f"https://curiosa.io{clean_name}.jpg"
            
            try:
                req = urllib.request.Request(target_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=10) as response:
                    img_data = response.read()
                    
                image_obj = PILImage.open(io.BytesIO(img_data))
                for _ in range(quantity):
                    final_images.append(image_obj)
                
            except Exception as e:
                st.warning(f"⚠️ Nie znaleziono standardowego pliku dla: '{card_name}'. Karta została pominięta.")
            
            current_card_index += 1
            progress_bar.progress(min(current_card_index / len(decklist), 1.0))
            
        if not final_images:
            st.error("❌ BŁĄD: Nie udało się pobrać grafik dla żadnej z wpisanych kart. Sprawdź pisownię.")
        else:
            status_text.text("✍️ Układanie kart w siatce PDF...")
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
            st.success(f"✅ Sukces! Arkusz proxy wygenerowany bez wersji foil i prefiksów liczbowych.")
            
            st.download_button(
                label="📥 Pobierz gotowy PDF do druku",
                data=pdf_buffer,
                file_name="sorcery_standard_proxies.pdf",
                mime="application/pdf",
                use_container_width=True
            )
