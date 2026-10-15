import streamlit as st
import os
import re
import io
import urllib.request
import json
from math import ceil
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

# Konfiguracja wyglądu strony internetowej
st.set_page_config(page_title="Sorcery TCG Proxy Generator", page_icon="🔮", layout="centered")

st.title("🔮 Sorcery TCG - Generator Proxy Online")
st.write("Wklej poniżej listę kart ze swojej talii. Narzędzie automatycznie pobierze grafiki w wysokiej rozdzielczości i przygotuje idealnie wyskalowany plik PDF formatu A4.")

# Pole tekstowe na stronie internetowej
decklist_input = st.text_area(
    "Wklej swoją listę kart (np. 1 Realm-Eater, 3 Fine Courser):",
    height=250,
    placeholder="1 Realm-Eater\n3 Fine Courser\n1 Ring of Morrigan\n4 Active Volcano"
)

def parse_input_text(text_block):
    """Przetwarza tekst z pola na słownik {nazwa_karty: ilość}"""
    decklist = {}
    lines = text_block.split('\n')
    for line in lines:
        line = line.strip()
        if not line or line.lower() in ['spellbook', 'atlas', 'avatar', 'maybeboard', 'collection']:
            continue
        match = re.match(r'^(\d+)\s+(.+)$', line)
        if match:
            quan = int(match.group(1))
            name = match.group(2).strip().lower()
            decklist[name] = decklist.get(name, 0) + quan
        else:
            name = line.lower()
            decklist[name] = decklist.get(name, 0) + 1
    return decklist

def get_card_image_url(card_name):
    """
    Format adresu URL do pobierania grafik z bazy Curiosa.
    Curiosa zapisuje pliki w formacie 'nazwa-karty.jpg', zamieniając spacje na myślniki.
    """
    clean_name = card_name.replace(' ', '-').replace('_', '-').replace("'", '').replace('!', '').lower()
    # Oficjalne repozytorium grafik Curiosa CDN
    return f"https://curiosa.io{clean_name}.jpg"

# Przycisk uruchamiający generowanie
if st.button("✨ Generuj arkusz PDF do druku", type="primary"):
    if not decklist_input.strip():
        st.error("❌ Najpierw wklej listę kart do pola tekstowego!")
    else:
        decklist = parse_input_text(decklist_input)
        
        # Wyświetlenie statusu pracy na ekranie
        status_text = st.empty()
        progress_bar = st.progress(0)
        
        # Przygotowanie pamięci RAM zamiast zapisu na dysku twardym
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=A4)
        
        card_width, card_height = 63.5 * mm, 88.9 * mm
        page_width, page_height = A4
        margin_x = (page_width - (3 * card_width)) / 2
        margin_y = (page_height - (3 * card_height)) / 2
        
        final_images = []
        total_cards = sum(decklist.values())
        current_card_index = 0
        
        # Pętla pobierająca grafiki prosto z sieci CDN
        for card_name, quantity in decklist.items():
            img_url = get_card_image_url(card_name)
            status_text.text(f"⏳ Pobieranie grafiki z internetu: {card_name}...")
            
            try:
                # Pobieranie obrazu prosto do pamięci podręcznej serwera
                req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req, timeout=5) as response:
                    img_data = response.read()
                    
                # Konwersja danych na obiekt PIL Image
                image_obj = PILImage.open(io.BytesIO(img_data))
                
                # Dodawanie wielokrotności karty do wydruku
                for _ in range(quantity):
                    final_images.append(image_obj)
                    
            except Exception as e:
                st.warning(f"⚠️ Nie znaleziono grafiki online dla: '{card_name}'. Karta zostanie pominięta.")
            
            current_card_index += 1
            progress_bar.progress(min(current_card_index / len(decklist), 1.0))
            
        if not final_images:
            st.error("❌ BŁĄD: Nie udało się pobrać grafik dla żadnej z wpisanych kart.")
        else:
            status_text.text("✍️ Układanie kart w siatce PDF...")
            cards_per_page = 9
            
            # Tworzenie stron w dokumencie PDF
            for index, img_obj in enumerate(final_images):
                pos = index % cards_per_page
                col = pos % 3
                row = 2 - (pos // 3)
                
                x = margin_x + (col * card_width)
                y = margin_y + (row * card_height)
                
                # Rysowanie pobranego z sieci obrazka na dokumencie PDF
                c.drawInlineImage(img_obj, x, y, width=card_width, height=card_height)
                
                # Jasnoszara obwódka ułatwiająca wycinanie
                c.setStrokeColorRGB(0.7, 0.7, 0.7)
                c.setLineWidth(0.2)
                c.rect(x, y, card_width, card_height, stroke=1, fill=0)
                
                if pos == 8 and index < len(final_images) - 1:
                    c.showPage()
                    
            c.save()
            pdf_buffer.seek(0)
            
            status_text.empty()
            progress_bar.empty()
            st.success(f"✅ Sukces! Wygenerowano arkusz zawierający {len(final_images)} kart.")
            
            # Przycisk pobierania pliku przez przeglądarkę
            st.download_button(
                label="📥 Pobierz gotowy PDF",
                data=pdf_buffer,
                file_name="sorcery_proxies_online.pdf",
                mime="application/pdf",
                use_container_width=True
            )
