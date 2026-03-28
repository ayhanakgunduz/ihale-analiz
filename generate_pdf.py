
from fpdf import FPDF
import os

def create_guide():
    pdf = FPDF()
    pdf.add_page()
    
    font_main = 'Helvetica' # Standard font
        
    pdf.set_font(font_main, 'B', 16)
    pdf.cell(0, 10, 'Ihale Analiz Parametreleri Teknik Rehberi', ln=True, align='C')
    pdf.ln(10)

    pdf.set_font(font_main, '', 11)
    intro = (
        "Bu dokuman, ihale tekliflerinin istatistiksel analizinde kullanilan temel parametrelerin "
        "aciklamasini, hesaplama yontemlerini ve ihale sonuclari uzerindeki etkilerini icermektedir."
    )
    pdf.multi_cell(0, 8, intro)
    pdf.ln(5)
    
    text_content = [
        ("1. Z-Skoru (Z-Score) Analizi", [
            "- Anlami: Bir teklif degerinin grup ortalamasindan kac standart sapma uzaklikta oldugunu belirtir.",
            "- Formul: Z = (Teklif - Ortalama) / Standart Sapma",
            "- Onerilen Aralik: 1.5 - 3.0. En yaygin kullanimi 2.0'dir (verinin %95'ini kapsar).",
            "- Etkisi: Z-Skoru yukseldikce sadece uc degerler yakalanir. Dusurulurse analiz daha hassas olur."
        ]),
        ("2. IQR Carpani (Interquartile Range)", [
            "- Anlami: Verinin orta %50'lik dilimini (Q1 ve Q3) temel alarak bir 'guvenli bolge' olusturur.",
            "- Formul: Alt Sinir = Q1 - (Katsayi * IQR), Ust Sinir = Q3 + (Katsayi * IQR)",
            "- Onerilen Aralik: 1.0 - 3.0. Standart deger 1.5'tir (Tukey Citi).",
            "- Etkisi: Bu yontem, tekliflerin birbirine cok yakin oldugu ancak bir-iki teklifin cok uzak oldugu durumlarda en iyi sonucu verir."
        ]),
        ("3. k-Degeri (Asiri Dusuk Teklif Sorgulama)", [
            "- Anlami: Bir teklifin 'birim maliyetin altinda' veya 'aciklanamayacak kadar dusuk' olup olmadigini belirlemek icin kullanilan emniyet katsayisidir.",
            "- Formul: Sorgulama Siniri = Ortalama - (k * Standart Sapma)",
            "- Onerilen Aralik: 0.3 - 1.0. Yaygin kullanim 0.5'tir.",
            "- Etkisi: k faktoru arttikca limit asagi cekilir ve tekliflerin 'asiri dusuk' olarak isaretlenmesi zorlasir."
        ])
    ]

    for title, points in text_content:
        pdf.set_font(font_main, 'B', 13)
        pdf.cell(0, 10, title, ln=True)
        pdf.set_font(font_main, '', 11)
        for pt in points:
            pdf.multi_cell(0, 7, pt)
        pdf.ln(5)

    pdf.set_font(font_main, 'B', 12)
    pdf.cell(0, 10, "Genel Degerlendirme:", ln=True)
    pdf.set_font(font_main, '', 11)
    pdf.multi_cell(0, 7, (
        "Eger ihale verileriniz duzenli ve birbirine yakinsa Z-Skoru (2.0) tercih edilmelidir. "
        "Ancak firmalar arasinda ucurum varsa ve ortalama yaniltici oluyorsa IQR (1.5) daha dogru sonuc verir. "
        "Asiri dusuk teklifleri tespit etmek icin k=0.5 katsayisi en ideal baslangic noktasidir."
    ))

    pdf.output("Ihale_Parametre_Rehberi.pdf")

if __name__ == "__main__":
    create_guide()
